"""
Post-expiry drift (12 Nov 2026 institutional research N5): after NIFTY's weekly expiry the hedges written against
the expiring series come off and the index has tended to drift up into the next session (Quantsapp NIFTY long
Tue close -> Wed close: +Rs 1.29L, 51 trades, 59% win, PF 1.59 before costs, 1 Oct 2025 - 30 Sep 2026 -- vendor
evidence, small sample, 8 trades through a >1% fall lost Rs 1.06L). PAPER ONLY until our own real-price replay passes.

  WHEN       NIFTY's own expiry day, entry in the last ENTRY_WINDOW_MIN minutes before the close
  FILTERS    index close above the session VWAP; India VIX percentile below MAX_VIX_PCTILE; no event next session
  BUILD      bull call spread on the NEXT weekly expiry: buy |delta| ~0.6, sell |delta| ~0.3 (debit, defined risk)
  EXIT       next session at EXIT_BEFORE_CLOSE_MIN before the close, or when the spread has lost STOP_FRAC of the debit
  SIZE       1 lot; stop the module after 12 losing trades in the last 20
"""
from dataclasses import dataclass
from typing import Any

ENTRY_WINDOW_MIN = 15
EXIT_BEFORE_CLOSE_MIN = 20
MAX_VIX_PCTILE = 85.0
STOP_FRAC = 0.5
BUY_DELTA, SELL_DELTA = 0.6, 0.3
KILL_LOSSES, KILL_WINDOW = 12, 20
BROKERAGE_PER_ORDER = 20.0


@dataclass(frozen=True)
class Spread:
    expiry: str
    buyStrike: float
    sellStrike: float
    debit: float   # per unit: buy leg ask - sell leg bid
    lotUnits: int


def eligible(close: float, vwap: float | None, vix_pctile: float | None, next_day_event: bool) -> tuple[bool, list[str]]:
    why = []
    if vwap is None or close <= vwap:
        why.append(f"close {close:.1f} not above VWAP {vwap}")
    if vix_pctile is not None and vix_pctile >= MAX_VIX_PCTILE:
        why.append(f"India VIX percentile {vix_pctile} >= {MAX_VIX_PCTILE}")
    if next_day_event:
        why.append("macro event next session")
    return not why, why


def pick(strikes: list[dict[str, Any]], lot_units: int, expiry: str) -> Spread | None:
    """From [{strike, delta, bid, ask}] CE quotes of the next expiry: buy the strike nearest BUY_DELTA, sell nearest
    SELL_DELTA above it."""
    ok = [s for s in strikes if s.get("delta") and s.get("ask") and s.get("bid")]
    if not ok:
        return None
    buy = min(ok, key=lambda s: abs(abs(s["delta"]) - BUY_DELTA))
    sells = [s for s in ok if s["strike"] > buy["strike"]]
    if not sells:
        return None
    sell = min(sells, key=lambda s: abs(abs(s["delta"]) - SELL_DELTA))
    debit = round(buy["ask"] - sell["bid"], 2)
    if debit <= 0:
        return None
    return Spread(expiry, buy["strike"], sell["strike"], debit, lot_units)


def cost_rs(sp: Spread, exit_value: float) -> float:
    """4 orders (open + close both legs): brokerage, STT on the sold premium, exchange, GST, stamp -- rough."""
    turnover = (sp.debit * 2 + max(exit_value, 0) * 2) * sp.lotUnits
    brokerage = 4 * BROKERAGE_PER_ORDER
    exch = turnover * 0.00035
    gst = 0.18 * (brokerage + exch)
    stt = turnover / 2 * 0.0015
    return round(brokerage + exch + gst + stt + turnover / 2 * 0.00003, 2)


def pnl_rs(sp: Spread, exit_value: float) -> float:
    return round((exit_value - sp.debit) * sp.lotUnits - cost_rs(sp, exit_value), 2)


def killed(recent_pnls: list[float]) -> bool:
    w = recent_pnls[-KILL_WINDOW:]
    return sum(1 for p in w if p <= 0) >= KILL_LOSSES
