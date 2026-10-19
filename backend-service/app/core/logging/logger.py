import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config.settings import settings
from app.core.logging.flow_context import LogFlowContext

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Foreground Colors
BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# High-Intensity / Bright
BRIGHT_BLACK = "\033[90m"  # Faint / Gray
BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class FlowIdFilter(logging.Filter):
    """
    Injects request-scoped flowId into every LogRecord for unified correlation.
    Matches trading-engine's [%X{flowId}] MDC pattern.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.flowId = LogFlowContext.get_flow_id()
        return True


class BeautifulTradingFormatter(logging.Formatter):
    """
    Precision ANSI color formatter matching trading-engine's console pattern:
    %clr(%d{yyyy-MM-dd HH:mm:ss.SSS}){faint} %levelColor([%-5level]) %clr([%X{flowId}]){magenta} %clr([%logger{36}]){cyan} %msg%n
    """

    LEVEL_MAP = {
        logging.DEBUG: f"{BRIGHT_BLACK}[DEBUG]{RESET}",
        logging.INFO: f"{GREEN}[INFO ]{RESET}",
        logging.WARNING: f"{YELLOW}[WARN ]{RESET}",
        logging.ERROR: f"{BOLD}{RED}[ERROR]{RESET}",
        logging.CRITICAL: f"{BOLD}{RED}[FATAL]{RESET}",
    }

    def format(self, record: logging.LogRecord) -> str:
        now = datetime.fromtimestamp(record.created)
        time_str = f"{BRIGHT_BLACK}{now.strftime('%Y-%m-%d %H:%M:%S')}.{int(record.msecs):03d}{RESET}"

        level_tag = self.LEVEL_MAP.get(record.levelno, f"[{record.levelname:<5}]")

        flow_id = getattr(record, "flowId", "") or ""
        flow_str = f"{MAGENTA}[{flow_id}]{RESET}" if flow_id else f"{BRIGHT_BLACK}[]{RESET}"

        logger_name = record.name
        if logger_name.startswith("app."):
            logger_name = logger_name[4:]
        if len(logger_name) > 36:
            logger_name = logger_name[-36:]
        name_str = f"{CYAN}[{logger_name}]{RESET}"

        message = record.getMessage()

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            message = f"{message}\n{record.exc_text}"

        return f"{time_str} {level_tag} {flow_str} {name_str} {message}"


class TradingFileFormatter(logging.Formatter):
    """
    Plain text formatter matching trading-engine's file pattern:
    %d{yyyy-MM-dd HH:mm:ss.SSS} [%-5level] [%X{flowId}] [%logger{36}] %msg%n
    """

    def format(self, record: logging.LogRecord) -> str:
        now = datetime.fromtimestamp(record.created)
        time_str = f"{now.strftime('%Y-%m-%d %H:%M:%S')}.{int(record.msecs):03d}"

        level_name = "WARN" if record.levelname == "WARNING" else record.levelname
        level_str = f"[{level_name:<5}]"

        flow_id = getattr(record, "flowId", "") or ""
        flow_str = f"[{flow_id}]" if flow_id else "[]"

        logger_name = record.name
        if logger_name.startswith("app."):
            logger_name = logger_name[4:]
        if len(logger_name) > 36:
            logger_name = logger_name[-36:]
        name_str = f"[{logger_name}]"

        message = record.getMessage()
        # Clean any ANSI codes for disk storage
        message = ANSI_ESCAPE_RE.sub("", message)

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            clean_exc = ANSI_ESCAPE_RE.sub("", record.exc_text)
            message = f"{message}\n{clean_exc}"

        return f"{time_str} {level_str} {flow_str} {name_str} {message}"


def resolve_logs_directory() -> Path:
    """
    Resolves the directory for daily log files.
    Prefers LOGS_DIR env, /app/logs (Docker), or workspace logs/ directory.
    """
    env_dir = os.getenv("LOGS_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Inside Docker container
    if os.path.exists("/app") and os.path.isdir("/app"):
        p = Path("/app/logs")
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Local development
    cwd = Path.cwd()
    if (cwd / "backend-service").exists():
        p = cwd / "logs"
    elif cwd.name == "backend-service" and (cwd.parent / "logs").exists():
        p = cwd.parent / "logs"
    else:
        p = cwd / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


class DailyRollingFileHandler(logging.FileHandler):
    """
    Daily rolling file appender matching trading-engine's TimeBasedRollingPolicy:
    File pattern: logs/%Y-%m-%d.log
    Retains last 30 days of logs.
    """

    def __init__(self, logs_dir: Path, max_history: int = 30, encoding: str = "utf-8"):
        self.logs_dir = logs_dir
        self.max_history = max_history
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{self.current_date}.log"
        super().__init__(str(log_file), mode="a", encoding=encoding)
        self._cleanup_old_logs()

    def _cleanup_old_logs(self) -> None:
        """Removes daily log files older than max_history days."""
        try:
            cutoff = (datetime.now() - timedelta(days=self.max_history)).strftime("%Y-%m-%d")
            for f in self.logs_dir.glob("????-??-??.log"):
                if f.stem < cutoff:
                    try:
                        f.unlink()
                    except OSError:
                        pass
        except Exception:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        """Checks if current date rolled over, rotates log file if needed, then emits."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.current_date:
            self.current_date = today
            new_file = self.logs_dir / f"{today}.log"
            self.close()
            self.baseFilename = os.path.abspath(str(new_file))
            self.stream = self._open()
            self._cleanup_old_logs()
        super().emit(record)


def setup_logging() -> None:
    """Configures application-wide trading terminal logging and daily rolling file logging."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to prevent duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    flow_filter = FlowIdFilter()

    # 1. Console Stream Handler with Beautiful Trading Formatter
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(BeautifulTradingFormatter())
    stream_handler.addFilter(flow_filter)
    root_logger.addHandler(stream_handler)

    # 2. Daily Rolling File Handler (logs/YYYY-MM-DD.log)
    logs_dir = resolve_logs_directory()
    file_handler = DailyRollingFileHandler(logs_dir=logs_dir, max_history=30)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(TradingFileFormatter())
    file_handler.addFilter(flow_filter)
    root_logger.addHandler(file_handler)

    # Silence excessively noisy internal libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = logging.getLogger("auto-trader")
