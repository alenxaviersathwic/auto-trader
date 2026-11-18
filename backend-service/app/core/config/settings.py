from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "ordergrid"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL async connection URL (pgvector supported)
    DATABASE_URL: str = "postgresql+asyncpg://autotrader:autotrader_secret@localhost:5432/autotrader"

    # Master encryption key (32 bytes or 32-char string for AES-GCM)
    MASTER_ENCRYPTION_KEY: str = "autotrader_master_secret_key_32b!"

    # APScheduler timezone
    SCHEDULER_TIMEZONE: str = "Asia/Kolkata"

    # CORS origins
    CORS_ORIGINS: List[str] = ["*"]

    # Research Engine, LLM & Embeddings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    # Local LLM (Ollama). One model is loaded on this machine, so calls are queued (LLM_MAX_CONCURRENCY) instead of
    # fighting for it; "thinking" is off (qwen3 otherwise writes a long hidden reasoning pass on every call); the model
    # stays loaded for LLM_KEEP_ALIVE between calls; LLM_NUM_CTX caps the context (smaller = faster prompt reading).
    OLLAMA_MODEL: str = "qwen3:8b"
    # Short tasks (index notes, research claims) use this model when it is installed, else OLLAMA_MODEL.
    # Faster option: `ollama pull qwen3:4b` and set LLM_FAST_MODEL=qwen3:4b.
    LLM_FAST_MODEL: str = "qwen3:4b"
    LLM_THINK: bool = False
    LLM_KEEP_ALIVE: str = "30m"
    LLM_NUM_CTX: int = 4096
    LLM_MAX_CONCURRENCY: int = 1
    LLM_RESEARCH_TIMEOUT_S: float = 45.0  # includes waiting in the queue behind another call
    EMBEDDING_DIMENSION: int = 768
    SEARXNG_BASE_URL: str = "http://localhost:8080"
    MCP_RESEARCH_TOKEN: str = "mcp_research_secret_token_123"
    MCP_CONFIRM_SECRET: str = "mcp_confirm_secret_key_32b_hex!"

    # Broker order safety (SEBI retail-algo framework, mandatory from 1 Apr 2026; Upstox API rules)
    # Upstox rejects plain MARKET / SL-M orders from the API since 11 Mar 2026 (UDAPI1158) unless they carry
    # market_protection: -1 = automatic band, 1-25 = % band.
    UPSTOX_MARKET_PROTECTION: int = -1
    # Self-built algos must identify themselves on every order (X-Algo-Name header).
    UPSTOX_ALGO_NAME: str = "auto-trader"
    # Stay well under Upstox's 10 orders/s unregistered-algo limit (and the exchange 10 OPS registration bar).
    ORDER_MAX_PER_SEC: int = 5
    # Entry: marketable LIMIT at the planned price + this many ticks (never chase further). 0.05 = one tick.
    ENTRY_LIMIT_BUFFER_TICKS: int = 2
    # An entry LIMIT not (fully) filled within this many seconds is cancelled: no chasing, no stale resting orders.
    ENTRY_FILL_TIMEOUT_S: float = 3.0

    # Opportunity ranking: CODE = rank by the code baseline (default); LLM = the local model selects.
    # When CODE, the LLM still runs in SHADOW (its pick is logged for A/B) if OPPORTUNITY_LLM_SHADOW is true.
    OPPORTUNITY_RANKER: str = "CODE"
    OPPORTUNITY_LLM_SHADOW: bool = False  # off 13 Nov 2026: no side/paper modes, live flow only
    # 18 Nov 2026: the backend starts the scanners at 09:14 IST and iterates them itself (job/scanner_job.py), so
    # scanning no longer waits for someone to open a session page -- the 09:20-09:35 FII_OPEN_DRIVE window was missed
    # on every day of 11-18 Nov because the first scan came at 09:42-12:06. False = the old browser-driven loop only.
    OPPORTUNITY_BACKEND_LOOP: bool = True

    # Institutional overlays (11 Nov 2026 review). Both are COMPUTED and logged always; they only change trading when
    # enabled, after their validation scripts pass (gamma: scripts/validate_gamma_regime.py t > 2; positioning: A/B).
    GAMMA_ROUTER_ENABLED: bool = False
    POSITIONING_OVERLAY_ENABLED: bool = False
    # 12 Nov 2026 institutional research filters (opportunity_finder/service/institutional_filters.py): comma list of the
    # ones validated on the real-data replay (both halves positive). They only ADD entry requirements.
    # Balanced live configuration: protect against false noise breakouts, restrict to active intraday market hours,
    # and require trend efficiency on short-side trades, without choking the system out of normal market trading.
    INSTITUTIONAL_FILTERS: str = "NIFTY_NOISE_STRICT,ENTRY_10_1430,PE_EXTRA"
    # 17 Nov 2026: which candle fires a setup -- "5m" (completed 5-min bar), "1m_trigger" (the 1-min close that
    # completes the 5-min pattern), "1m" (patterns on 1-min candles); 5m / 15m confirm (setups.tf_agreement)
    SIGNAL_TIMEFRAME: str = "5m"
    COMMODITY_DESK_ENABLED: bool = True  # sub-agents + LLM head trader on MCX scans (modules/commodity_desk)
    MOVE_WATCH_ENABLED: bool = True  # sudden-move news sub-agent on every scanned underlying
    # FII_OPEN_DRIVE opening trade (fii_open.py); "" = off. 17 Nov 2026: all three indices (replay, live pipeline,
    # May-Nov: NIFTY +17.9k / +23.8k, SENSEX +16.2k / +23.1k, BANKNIFTY -1.8k / +27.3k per half)
    FII_OPEN_CODES: str = "NIFTY,BANKNIFTY,SENSEX"
    # 17 Nov 2026: no NEW index entries from this IST time (setups.last_entry_block); open trades keep running and
    # commodities are not affected. "" = off. Replay: 14:00-15:00 entries were 47 trades, 26% wins, -9.4k / -15.0k
    # per half -- "14:00" tested better (+158k vs +134k); the user chose 15:00.
    INDEX_LAST_ENTRY_TIME: str = "15:00"
    # Research Engine on its own: at start-up, then every N minutes while system usage is below the limit
    RESEARCH_AUTO_ENABLED: bool = True
    RESEARCH_AUTO_INTERVAL_MIN: int = 30
    RESEARCH_AUTO_MAX_LOAD_PCT: float = 50.0
    RESEARCH_AUTO_WINDOW: str = "07:00-23:30"  # IST
    RESEARCH_AUTO_STARTUP_DELAY_S: int = 60
    # app load capacity (system/service/system_load.py): session loops + session scanners + trade pilots
    SYSTEM_APP_CAPACITY: int = 12

    # Autopsy guards (modules/autopsy): False = proposed, you apply them; True = applied as soon as proposed
    AUTOPSY_AUTO_APPLY_GUARDS: bool = False
    # 18 Nov 2026 research review: a fixed % cap silently removed the one validated setup (FII_OPEN_DRIVE, Rs 4.0-4.7k
    # risk per lot vs Rs 4k at Rs 1L: all 18 signals of 18 Sep-17 Nov skipped). "SETUP:PCT,..." lets a named setup
    # risk up to PCT % of capital on ONE lot, as the session's first trade of the day only (nothing lost or committed
    # yet), so the day's worst case on such a day is PCT % instead of maxLossPercentage. Empty = off.
    SETUP_RISK_BUDGET: str = "FII_OPEN_DRIVE:5"
    MAX_ONE_LOT_RISK_PCT: float = 4.0  # one lot may risk up to this % of session capital when 0.5% buys < 1 lot (4% = Rs 2,000 at Rs 50k, set 13 Nov 2026)

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
