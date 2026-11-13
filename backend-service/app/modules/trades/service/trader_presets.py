"""
Institutional Preset Traders (`trader_presets.py`).

Defines the 3 self-contained Specialist Traders for `auto-trader`. Each Trader combines:
  1. Opportunity Discovery / Strategy Filter (how it finds setups in the market)
  2. Live 1-Second Re-Analysis & SL/Target Step-Wave Brain (how it trails SL & steps Target)
"""
from typing import Any

TRADER_FIB_GOLDEN = "FIB_GOLDEN_TRADER"
TRADER_ORB_WAVE = "ORB_WAVE_TRADER"
TRADER_FLOW_VWAP = "FLOW_VWAP_TRADER"

ALL_PRESET_TRADER_CODES: tuple[str, ...] = (
    TRADER_FIB_GOLDEN,
    TRADER_ORB_WAVE,
    TRADER_FLOW_VWAP,
)

TRADER_PRESETS: list[dict[str, Any]] = [
    {
        "code": TRADER_FIB_GOLDEN,
        "name": "Fibonacci Golden-Pocket Trader",
        "shortLabel": "FIB GOLDEN",
        "badgeColor": "cyan",
        "methodology": "0.50–0.618 Golden Pocket Pullback + 1.272 / 1.618 Fib Extension Trail",
        "entryLogic": (
            "Detects an impulse swing (Swing Low → Swing High) aligned with trend bias and enters on a "
            "pullback into the 0.50–0.618 Golden Pocket with 1m candle confirmation."
        ),
        "trailLogic": (
            "Initial SL below 0.786 retracement. At 80% of 1.0 Swing High, locks SL at 0.618 (+50% move). "
            "When 1.0 Target is reached with volume, locks SL at 1.0 and steps Target to 1.272 Fib Extension, "
            "then 1.618 Golden Extension."
        ),
        "strategies": [
            "Fibonacci Golden Pocket",
            "EMA Pullback",
            "Supertrend",
            "Trend Pullback",
            "Multi-Timeframe Trend",
        ],
    },
    {
        "code": TRADER_ORB_WAVE,
        "name": "ORB & Momentum Wave Runner",
        "shortLabel": "ORB WAVE",
        "badgeColor": "green",
        "methodology": "15m Opening Range / Consolidation Breakout + Step-Wave Expansion (100 → 120 → 150)",
        "entryLogic": (
            "Scans for 15-minute Opening Range, FII Open Drive, or multi-bar box breakouts with "
            "volumeRatio >= 1.35x and expanding directional momentum."
        ),
        "trailLogic": (
            "Re-analyzes wave potential every second. When planned Target is 100 and live volume/momentum "
            "projects 150, locks SL at 75 (at 75–80% progress) and steps Target to 120, then locks SL at 100 "
            "and steps Target to 150."
        ),
        "strategies": [
            "ORB Breakout",
            "FII Open Drive",
            "Opening Range Breakout",
            "Volume Breakout",
            "Momentum Breakout",
            "Gamma Squeeze",
            "Bollinger Breakout",
        ],
    },
    {
        "code": TRADER_FLOW_VWAP,
        "name": "Institutional VWAP & OI Flow Trader",
        "shortLabel": "VWAP FLOW",
        "badgeColor": "blue",
        "methodology": "Session VWAP + Option Chain OI Wall Support + Fast Step-Guard Trail",
        "entryLogic": (
            "Identifies bounces off Session VWAP, 9-EMA, or CPR/Camarilla pivots backed by Put-writing "
            "support (for CE) or Call-writing resistance (for PE)."
        ),
        "trailLogic": (
            "Protects capital fast: at 50% target progress trails SL to +30% profit (above breakeven + fees); "
            "at 80% progress locks +50% profit and trails under 1m higher-low support."
        ),
        "strategies": [
            "VWAP Bounce",
            "VWAP Pullback",
            "CPR Bounce",
            "RSI Reversal",
            "OI Flow",
            "Iron Fly",
        ],
    },
]

_PRESET_BY_CODE: dict[str, dict[str, Any]] = {p["code"]: p for p in TRADER_PRESETS}


def get_trader_preset(code: str | None) -> dict[str, Any]:
    """Return the preset metadata dict for `code`, defaulting to `ORB_WAVE_TRADER`."""
    if code and code in _PRESET_BY_CODE:
        return _PRESET_BY_CODE[code]
    return _PRESET_BY_CODE[TRADER_ORB_WAVE]


def assign_trader_for_opportunity(strategy: str | None, confidence: int = 70, reward_risk: float = 1.5) -> str:
    """
    Maps a candidate setup's strategy / characteristics to one of the 3 Specialist Preset Traders:
      - `FIB_GOLDEN_TRADER`
      - `ORB_WAVE_TRADER`
      - `FLOW_VWAP_TRADER`
    """
    s = (strategy or "").strip().lower()
    if any(k in s for k in ("fib", "pullback", "ema", "supertrend", "golden", "swing")):
        return TRADER_FIB_GOLDEN
    if any(k in s for k in ("orb", "open drive", "fii", "breakout", "momentum", "gamma", "squeeze", "impulse")):
        return TRADER_ORB_WAVE
    if any(k in s for k in ("vwap", "cpr", "pivot", "rsi", "reversal", "oi", "flow", "iron", "bollinger")):
        return TRADER_FLOW_VWAP

    # Fallback by reward/risk & conviction profile
    if reward_risk >= 1.8:
        return TRADER_ORB_WAVE
    if confidence >= 78:
        return TRADER_FIB_GOLDEN
    return TRADER_FLOW_VWAP

