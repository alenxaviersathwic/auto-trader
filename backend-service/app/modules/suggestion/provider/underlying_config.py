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
    # MCX options liquidity is concentrated in crude, natural gas, gold, silver (G-LIQ-MCX-BASEMETAL
    # guardrail, Oct-2026 research). COPPER/ZINC options are too thin to clear the liquidity filters
    # most of the time, so they are routed to futures-only strategies instead of a chain fetch that
    # will reliably come back empty.
    optionsSupported: bool = True


# NOTE: lot sizes and close times below were verified against NSE/BSE circulars as of Oct 2026
# (NSE/FAOP/70616 cut NIFTY 75->65, FINNIFTY 65->60 effective 6 Jan 2026 weekly / 27 Jan 2026 monthly;
# NSE F&O close extended 15:30->15:40 effective 3 Aug 2026; BSE did not extend and stays at 15:30).
# NSE reviews lot sizes every March/September -- treat these as defaults and read the live instrument
# master each morning (see guardrail G-LOT-MASTER) rather than trusting this file long-term.
UNDERLYING_CONFIG: dict[str, UnderlyingConfig] = {
    "NIFTY": UnderlyingConfig("NIFTY", "INDEX", "NSE", "NSE_INDEX|Nifty 50", 65, 50, "09:15", "15:40", "NSE_BROAD"),
    "BANKNIFTY": UnderlyingConfig("BANKNIFTY", "INDEX", "NSE", "NSE_INDEX|Nifty Bank", 30, 100, "09:15", "15:40", "NSE_BANK"),
    "FINNIFTY": UnderlyingConfig("FINNIFTY", "INDEX", "NSE", "NSE_INDEX|Nifty Fin Service", 60, 50, "09:15", "15:40", "NSE_BANK"),
    "MIDCPNIFTY": UnderlyingConfig("MIDCPNIFTY", "INDEX", "NSE", "NSE_INDEX|NIFTY MID SELECT", 120, 25, "09:15", "15:40", "NSE_MID"),
    "SENSEX": UnderlyingConfig("SENSEX", "INDEX", "BSE", "BSE_INDEX|SENSEX", 20, 100, "09:15", "15:30", "NSE_BROAD"),
    "BANKEX": UnderlyingConfig("BANKEX", "INDEX", "BSE", "BSE_INDEX|BANKEX", 30, 100, "09:15", "15:30", "NSE_BANK"),
    # MCX option chains hang off a futures contract key that rolls monthly; set via env/config later.
    "CRUDEOIL": UnderlyingConfig("CRUDEOIL", "COMMODITY", "MCX", None, 100, 50, "09:00", "23:30"),
    "NATURALGAS": UnderlyingConfig("NATURALGAS", "COMMODITY", "MCX", None, 1250, 5, "09:00", "23:30"),
    "GOLD": UnderlyingConfig("GOLD", "COMMODITY", "MCX", None, 100, 100, "09:00", "23:30"),
    "SILVER": UnderlyingConfig("SILVER", "COMMODITY", "MCX", None, 30, 100, "09:00", "23:30"),
    "COPPER": UnderlyingConfig("COPPER", "COMMODITY", "MCX", None, 2500, 5, "09:00", "23:30", optionsSupported=False),
    "ZINC": UnderlyingConfig("ZINC", "COMMODITY", "MCX", None, 5000, 2.5, "09:00", "23:30", optionsSupported=False),
}


def get_config(code: str) -> UnderlyingConfig | None:
    return UNDERLYING_CONFIG.get(code.upper())


def is_market_open(cfg: UnderlyingConfig, now: datetime | None = None) -> bool:
    """Weekday and inside the exchange's trading hours (IST)."""
    now = now or datetime.now(ZoneInfo("Asia/Kolkata"))
    if now.weekday() >= 5:
        return False
    return cfg.open <= now.strftime("%H:%M") <= cfg.close
