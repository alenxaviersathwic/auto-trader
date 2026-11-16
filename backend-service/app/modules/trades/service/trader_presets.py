"""
The two Traders of `auto-trader` (`trader_presets.py`).

A Trader is (1) the setups it is allowed to take and (2) how it manages the position once entered.

  FIB_GOLDEN_TRADER     takes ONLY `FIB_GOLDEN_POCKET` (opportunities/service/fib_pocket.py): a pullback into the
                        0.50-0.618 retracement of a real impulse swing, and only when the option chain (OI) and the
                        futures volume both confirm it. Manages the trade along the Fibonacci extensions.
  FLOW_MOMENTUM_TRADER  takes everything else the engine allows (noise breakout, inside bar, FII open drive, late-day
                        momentum, VWAP / range entries inside an active breakout). Manages the trade with the R-trail
                        momentum exit (menu_builder.MOMO_EXIT) or the step guard.

Until 16 Nov 2026 there were three presets (FIB_GOLDEN / ORB_WAVE / FLOW_VWAP). The last two are merged into
FLOW_MOMENTUM_TRADER; `normalize_trader_code()` maps the old codes so stored sessions and trades keep working.
"""
from typing import Any

TRADER_FIB_GOLDEN = "FIB_GOLDEN_TRADER"
TRADER_FLOW_MOMENTUM = "FLOW_MOMENTUM_TRADER"

ALL_PRESET_TRADER_CODES: tuple[str, ...] = (TRADER_FIB_GOLDEN, TRADER_FLOW_MOMENTUM)

LEGACY_TRADER_CODES: dict[str, str] = {
    "ORB_WAVE_TRADER": TRADER_FLOW_MOMENTUM,
    "FLOW_VWAP_TRADER": TRADER_FLOW_MOMENTUM,
}

FIB_SETUP = "FIB_GOLDEN_POCKET"
_FIB_KEYWORDS = ("fib", "golden pocket", "golden-pocket", "retracement")

TRADER_PRESETS: list[dict[str, Any]] = [
    {
        "code": TRADER_FIB_GOLDEN,
        "name": "Fib Golden-Pocket Trader",
        "shortLabel": "FIB + OI + VOL",
        "badgeColor": "cyan",
        "methodology": "0.50-0.618 pullback of an impulse swing, confirmed by option-chain OI and futures volume",
        "entryLogic": (
            "Finds an impulse swing of at least 3 ATR on the 5-minute chart, waits for the pullback into the "
            "0.50-0.618 pocket and a 5-minute close turning back with the swing. Enters only when the option chain "
            "confirms (OI wall behind the stop, no OI wall blocking the target) and volume confirms (quiet pullback, "
            "active turn bar)."
        ),
        "trailLogic": (
            "Stop behind the 0.786 retracement. Waits for 80% of the move to the swing high before locking half the "
            "profit, then steps the target to the 1.272 and 1.618 extensions while momentum holds."
        ),
        "strategies": ["FIB_GOLDEN_POCKET"],
    },
    {
        "code": TRADER_FLOW_MOMENTUM,
        "name": "Flow & Momentum Trader",
        "shortLabel": "FLOW + MOMENTUM",
        "badgeColor": "green",
        "methodology": "Noise-area breakouts and institutional flow, held with an R-multiple trail (no fixed target)",
        "entryLogic": (
            "Takes the engine's breakout and flow setups: noise breakout, inside bar, FII open drive, late-day "
            "momentum, plus VWAP pullback / range breakout / gap-and-go inside an active breakout on the same side."
        ),
        "trailLogic": (
            "Momentum setups: stop to breakeven at +1.5R, then trail 2R under the peak, no fixed target. Other "
            "entries: step guard (+30% of the move locked at 50% progress, +50% at 80%)."
        ),
        "strategies": [
            "NOISE_BREAKOUT",
            "INSIDE_BAR",
            "FII_OPEN_DRIVE",
            "LATE_DAY_MOMENTUM",
            "VWAP_PULLBACK",
            "RANGE_BREAKOUT",
            "GAP_GO",
        ],
    },
]

_PRESET_BY_CODE: dict[str, dict[str, Any]] = {p["code"]: p for p in TRADER_PRESETS}


def normalize_trader_code(code: str | None) -> str | None:
    """Current trader code for `code` (old three-trader codes are mapped), or None when it is not a trader code."""
    if not code:
        return None
    c = LEGACY_TRADER_CODES.get(code, code)
    return c if c in _PRESET_BY_CODE else None


def normalize_trader_codes(codes: list[str] | None) -> list[str]:
    """De-duplicated current codes in preset order; an empty / unknown list means both traders."""
    wanted = {normalize_trader_code(c) for c in (codes or [])}
    out = [c for c in ALL_PRESET_TRADER_CODES if c in wanted]
    return out or list(ALL_PRESET_TRADER_CODES)


def get_trader_preset(code: str | None) -> dict[str, Any]:
    """Preset metadata for `code` (old codes accepted); unknown codes fall back to the Flow & Momentum trader."""
    return _PRESET_BY_CODE[normalize_trader_code(code) or TRADER_FLOW_MOMENTUM]


def assign_trader_for_opportunity(strategy: str | None, confidence: int = 70, reward_risk: float = 1.5) -> str:
    """Which trader owns an opportunity: the Fib trader for the Fib golden-pocket setup (by setup name, or a cited
    strategy that names it), the Flow & Momentum trader for everything else. `confidence` / `reward_risk` are kept
    for call compatibility; ownership no longer depends on them."""
    del confidence, reward_risk
    s = (strategy or "").strip()
    if s.upper() == FIB_SETUP or any(k in s.lower() for k in _FIB_KEYWORDS):
        return TRADER_FIB_GOLDEN
    return TRADER_FLOW_MOMENTUM
