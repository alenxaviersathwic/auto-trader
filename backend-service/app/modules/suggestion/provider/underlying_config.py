from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class UnderlyingConfig:
    """Per-underlying settings. Same engine code, different config (values are editable defaults)."""

    code: str
    type: str  # INDEX | COMMODITY
    exchange: str
    instrumentKey: str | None  # Upstox key of the spot index / MCX future; None => cannot fetch
    lotSize: int
    strikeStep: float
    open: str  # HH:MM IST
    close: str
    linkedGroup: str | None = None  # linked indices count as one pick group


UNDERLYING_CONFIG: dict[str, UnderlyingConfig] = {
    "NIFTY": UnderlyingConfig("NIFTY", "INDEX", "NSE", "NSE_INDEX|Nifty 50", 75, 50, "09:15", "15:30", "NSE_BROAD"),
    "BANKNIFTY": UnderlyingConfig("BANKNIFTY", "INDEX", "NSE", "NSE_INDEX|Nifty Bank", 30, 100, "09:15", "15:30", "NSE_BANK"),
    "FINNIFTY": UnderlyingConfig("FINNIFTY", "INDEX", "NSE", "NSE_INDEX|Nifty Fin Service", 65, 50, "09:15", "15:30", "NSE_BANK"),
    "MIDCPNIFTY": UnderlyingConfig("MIDCPNIFTY", "INDEX", "NSE", "NSE_INDEX|NIFTY MID SELECT", 120, 25, "09:15", "15:30", "NSE_MID"),
    "SENSEX": UnderlyingConfig("SENSEX", "INDEX", "BSE", "BSE_INDEX|SENSEX", 20, 100, "09:15", "15:30", "NSE_BROAD"),
    "BANKEX": UnderlyingConfig("BANKEX", "INDEX", "BSE", "BSE_INDEX|BANKEX", 30, 100, "09:15", "15:30", "NSE_BANK"),
    # MCX option chains hang off a futures contract key that rolls monthly; set via env/config later.
    "CRUDEOIL": UnderlyingConfig("CRUDEOIL", "COMMODITY", "MCX", None, 100, 50, "09:00", "23:30"),
    "NATURALGAS": UnderlyingConfig("NATURALGAS", "COMMODITY", "MCX", None, 1250, 5, "09:00", "23:30"),
    "GOLD": UnderlyingConfig("GOLD", "COMMODITY", "MCX", None, 100, 100, "09:00", "23:30"),
    "SILVER": UnderlyingConfig("SILVER", "COMMODITY", "MCX", None, 30, 100, "09:00", "23:30"),
    "COPPER": UnderlyingConfig("COPPER", "COMMODITY", "MCX", None, 2500, 5, "09:00", "23:30"),
    "ZINC": UnderlyingConfig("ZINC", "COMMODITY", "MCX", None, 5000, 2.5, "09:00", "23:30"),
}


def get_config(code: str) -> UnderlyingConfig | None:
    return UNDERLYING_CONFIG.get(code.upper())


def is_market_open(cfg: UnderlyingConfig, now: datetime | None = None) -> bool:
    """Weekday and inside the exchange's trading hours (IST)."""
    now = now or datetime.now(ZoneInfo("Asia/Kolkata"))
    if now.weekday() >= 5:
        return False
    return cfg.open <= now.strftime("%H:%M") <= cfg.close
