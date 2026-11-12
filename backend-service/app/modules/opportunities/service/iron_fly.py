"""
Expiry-day IRON FLY -- defined-risk premium selling, the archetype with the strongest evidence for Indian index options
(11 Nov 2026 research review, gap 6A). Pure functions; PAPER-ONLY until it passes edge_stats.promotion_verdict()
(>= 200 out-of-sample trades, deflated Sharpe > 0.95) on REAL option prices.

Why this and not more premium BUYING:
  * a volatility risk premium exists in NIFTY options: delta-neutral short straddles/strangles had positive mean
    returns 2019-2024, long-vol negative;
  * but the edge is thin and tail-heavy: 148 NIFTY expiries, ATM straddle sold 09:15 and held: 69% winners, mean only
    ~19% of premium kept, average loss -91 pts, worst -290 (Quintal Mind 2026) -- so ONLY with bought wings;
  * naive variants turn negative after costs (Quantsapp 2025-26) -> filters + cost check below are not optional.

Rules
  WHEN       the underlying's own series expires today (dte == 0), entry 09:45-10:45 IST, not on an event day
  FILTERS    VRP: ATM IV / Yang-Zhang realised vol >= MIN_VRP_RATIO; India VIX percentile inside VIX_PCTILE_RANGE
             and not rising; |gap| < MAX_GAP_PCT (big gaps are trend days: >0.5% gaps filled only 25%); price inside
             the noise area; no EXPANSION / TREND day-type bias; no scheduled macro event (event_calendar.py)
  BUILD      sell ATM CE + ATM PE, buy wings at ATM +- W, W = straddle credit rounded UP to the strike step
             (wings beyond the market's own expected move); a gap > SKEW_GAP_PCT widens the wing on the side gaps
             tend to come back through... no: the side large gap-ups breach most -- the PUT side -- by one step
  PRICES     sells at the BID, buys at the ASK (the spread is part of the trade); 4 legs -> 8 orders of costs
  ACCEPT     credit >= MIN_CREDIT_FRAC of the wing width, costs <= MAX_COST_FRAC of the credit
  EXIT       take profit when the fly can be bought back for (1 - TAKE_PROFIT_FRAC) x credit; stop when the loss
             reaches STOP_LOSS_FRAC x max loss or a 5-min spot close beyond a breakeven; time exit TIME_EXIT (before
             the last-hour gamma); never held to expiry
"""
import math
from dataclasses import asdict, dataclass
from datetime import datetime, time as dtime
from math import ceil
from typing import Any

from app.modules.opportunities.service.costs import EXCHANGE_TXN, STT_SELL

ENTRY_FROM, ENTRY_TO = dtime(9, 45), dtime(10, 45)
TIME_EXIT = dtime(14, 45)
MAX_GAP_PCT = 0.5
SKEW_GAP_PCT = 0.2
MIN_CREDIT_FRAC = 0.25
MAX_COST_FRAC = 0.15
TAKE_PROFIT_FRAC = 0.35
# 11 Nov 2026 institutional review (Strategy 1): only sell when implied volatility is above what the market is likely to
# realise (Nifty VRP positive on ~75% of days, median net edge ~+1.1 vol pts, fat left tail -- Agarwal, SSRN 2026)
MIN_VRP_RATIO = 1.10       # ATM implied vol / forecast realised vol (Yang-Zhang over RV_DAYS daily bars)
RV_DAYS = 20
MIN_IMPLIED_MOVE_RATIO = 1.15  # route N1: straddle / median realised range of the last 20 same-weekday expiry days
EXPIRY_RANGE_LOOKBACK = 20
VIX_PCTILE_RANGE = (20.0, 85.0)  # India VIX percentile over ~1 year: not too cheap to sell, not a panic
STOP_LOSS_FRAC = 0.50
BROKERAGE_PER_ORDER = 20.0
BLOCKING_TAGS = ("EVENT", "RBI", "BUDGET", "CPI", "FOMC", "RESULTS", "ELECTION")


@dataclass(frozen=True)
class IronFly:
    underlying: str
    expiry: str
    atm: float
    callWing: float
    putWing: float
    credit: float            # per unit, after selling at bids / buying at asks
    maxLoss: float           # per unit: widest wing - credit
    lotUnits: int
    costRs: float            # round-trip charges for one lot, all 8 orders
    takeProfitAt: float      # buy back the fly at or below this (per unit)
    stopAt: float            # buy back the fly at or above this (per unit)
    legs: tuple              # (("SELL"|"BUY", "CE"|"PE", strike, price, instrumentKey), ...)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def eligible(a: dict[str, Any], now: datetime, tags: list[str] | None = None) -> tuple[bool, list[str]]:
    """(ok, reasons) from the live analysis dict (dte, levels.gapPct, vix.changePct, dayType, dayBias)."""
    why: list[str] = []
    if a.get("dte") != 0:
        why.append("not this underlying's expiry day")
    t = now.time()
    if not (ENTRY_FROM <= t <= ENTRY_TO):
        why.append(f"outside the {ENTRY_FROM:%H:%M}-{ENTRY_TO:%H:%M} entry window")
    gap = (a.get("levels") or {}).get("gapPct")
    if gap is None or abs(gap) >= MAX_GAP_PCT:
        why.append(f"gap {gap}% (needs a known gap below {MAX_GAP_PCT}%)")
    vix = (a.get("vix") or {}).get("changePct")
    if vix is not None and vix > 0:
        why.append(f"India VIX rising ({vix:+.1f}%)")
    kinds = {(a.get("dayType") or {}).get("type"), (a.get("dayBias") or {}).get("type")}
    if kinds & {"EXPANSION", "TREND"}:
        why.append("trend / expansion day: short gamma is the wrong side")
    vrp = a.get("vrpRatio")
    calm = a.get("impliedMoveRatio")
    # two routes (12 Nov 2026 institutional research N1): the VRP gate, OR "calmer than priced" -- today's ATM straddle
    # (the market's implied expiry-day move) >= MIN_IMPLIED_MOVE_RATIO x the median REALISED range of the last 20
    # same-weekday expiry days. Trailing RV over-states risk right after a shock week, when premium is richest.
    vrp_ok = vrp is not None and vrp >= MIN_VRP_RATIO
    calm_ok = calm is not None and calm >= MIN_IMPLIED_MOVE_RATIO
    if not (vrp_ok or calm_ok):
        why.append(f"VRP ratio {vrp} (needs >= {MIN_VRP_RATIO}) and implied/realised expiry move {calm} "
                   f"(needs >= {MIN_IMPLIED_MOVE_RATIO})")
    pct = a.get("vixPctile")
    if pct is None or not (VIX_PCTILE_RANGE[0] <= pct <= VIX_PCTILE_RANGE[1]):
        why.append(f"India VIX percentile {pct} outside {VIX_PCTILE_RANGE[0]:g}-{VIX_PCTILE_RANGE[1]:g}")
    if (a.get("noise") or {}).get("state") not in (None, "INSIDE"):
        why.append("price outside the noise area: trend day")
    hit = [x for x in (tags or []) if any(b in str(x).upper() for b in BLOCKING_TAGS)]
    if hit:
        why.append(f"event day ({', '.join(hit)})")
    return not why, why


def yang_zhang_vol(daily: list[dict[str, Any]], days: int = RV_DAYS) -> float | None:
    """Annualised Yang-Zhang volatility (%) from daily {o,h,l,c} bars (oldest first); None with too little data.
    Handles the overnight gap that close-to-close and Parkinson estimators mis-measure."""
    d = [b for b in daily if b.get("o") and b.get("h") and b.get("l") and b.get("c")][-(days + 1):]
    if len(d) < max(10, days // 2) + 1:
        return None
    o = [math.log(d[i]["o"] / d[i - 1]["c"]) for i in range(1, len(d))]
    c = [math.log(d[i]["c"] / d[i]["o"]) for i in range(1, len(d))]
    rs = [math.log(b["h"] / b["c"]) * math.log(b["h"] / b["o"]) + math.log(b["l"] / b["c"]) * math.log(b["l"] / b["o"])
          for b in d[1:]]
    n = len(o)

    def var(x: list[float]) -> float:
        m = sum(x) / len(x)
        return sum((v - m) ** 2 for v in x) / (len(x) - 1)

    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    v = var(o) + k * var(c) + (1 - k) * sum(rs) / n
    return round(math.sqrt(max(v, 0.0) * 252) * 100, 2)


def vrp_ratio(atm_iv_pct: float | None, daily: list[dict[str, Any]]) -> float | None:
    """ATM implied vol / Yang-Zhang realised vol. `atm_iv_pct` in percent (Upstox greeks iv, e.g. 13.8)."""
    rv = yang_zhang_vol(daily)
    if not atm_iv_pct or not rv:
        return None
    return round(atm_iv_pct / rv, 3)


def implied_move_ratio(straddle: float | None, past_expiry_ranges: list[float]) -> float | None:
    """ATM straddle (points) / median high-low range of past expiry days (points); None with < 8 past expiries."""
    r = sorted(x for x in past_expiry_ranges[-EXPIRY_RANGE_LOOKBACK:] if x and x > 0)
    if not straddle or len(r) < 8:
        return None
    mid = r[len(r) // 2] if len(r) % 2 else (r[len(r) // 2 - 1] + r[len(r) // 2]) / 2
    return round(straddle / mid, 3)


def percentile(value: float | None, history: list[float]) -> float | None:
    if value is None or len(history) < 60:
        return None
    return round(sum(1 for h in history if h <= value) / len(history) * 100, 1)


def _cost_rs(prices: list[float], lot_units: int, exchange: str, close_frac: float) -> float:
    """8 orders: open 4 legs, close 4 legs (closing value ~ close_frac of opening premium per leg)."""
    open_turn = sum(prices) * lot_units
    close_turn = open_turn * close_frac
    turnover = open_turn + close_turn
    brokerage = 8 * BROKERAGE_PER_ORDER
    exch = turnover * EXCHANGE_TXN.get(exchange, 0.00035)
    sebi = turnover * 1e-6
    gst = 0.18 * (brokerage + exch + sebi)
    stt = turnover / 2 * STT_SELL.get(exchange, 0.0015)  # roughly half the turnover is sell-side
    stamp = turnover / 2 * 0.00003
    return round(brokerage + exch + sebi + gst + stt + stamp, 2)


def build(chain: dict[str, Any], spot: float, step: float, lot_units: int, underlying: str, exchange: str,
          gap_pct: float | None = None) -> tuple[IronFly | None, str | None]:
    """The fly from a live chain ({expiry, strikes:[{strike, CE:{bid,ask,key}, PE:{...}}]}), or (None, why)."""
    rows = {float(r["strike"]): r for r in chain.get("strikes") or []}
    if not rows:
        return None, "empty chain"
    atm = min(rows, key=lambda k: abs(k - spot))
    a = rows[atm]
    ce_b, pe_b = a["CE"].get("bid") or 0, a["PE"].get("bid") or 0
    if ce_b <= 0 or pe_b <= 0:
        return None, "no bid on the ATM straddle"
    straddle = ce_b + pe_b
    w = ceil(straddle / step) * step
    call_w, put_w = atm + w, atm - w
    if gap_pct is not None and gap_pct >= SKEW_GAP_PCT:
        put_w -= step  # gap-ups breach the put side most often
    elif gap_pct is not None and gap_pct <= -SKEW_GAP_PCT:
        call_w += step
    if call_w not in rows or put_w not in rows:
        return None, f"wing strikes {put_w:.0f}/{call_w:.0f} not in the chain"
    cw_a, pw_a = rows[call_w]["CE"].get("ask") or 0, rows[put_w]["PE"].get("ask") or 0
    if cw_a <= 0 or pw_a <= 0:
        return None, "no ask on a wing"
    credit = round(straddle - cw_a - pw_a, 2)
    width = max(call_w - atm, atm - put_w)
    if credit <= 0 or credit < MIN_CREDIT_FRAC * width:
        return None, f"credit {credit:.1f} < {MIN_CREDIT_FRAC:.0%} of the {width:.0f}-pt wing"
    max_loss = round(width - credit, 2)
    cost = _cost_rs([ce_b, pe_b, cw_a, pw_a], lot_units, exchange, close_frac=0.6)
    if cost > MAX_COST_FRAC * credit * lot_units:
        return None, f"charges Rs {cost:.0f} > {MAX_COST_FRAC:.0%} of the Rs {credit * lot_units:.0f} credit"
    legs = (("SELL", "CE", atm, ce_b, a["CE"].get("key")), ("SELL", "PE", atm, pe_b, a["PE"].get("key")),
            ("BUY", "CE", call_w, cw_a, rows[call_w]["CE"].get("key")),
            ("BUY", "PE", put_w, pw_a, rows[put_w]["PE"].get("key")))
    return IronFly(underlying=underlying, expiry=chain.get("expiry", ""), atm=atm, callWing=call_w, putWing=put_w,
                   credit=credit, maxLoss=max_loss, lotUnits=lot_units, costRs=cost,
                   takeProfitAt=round(credit * (1 - TAKE_PROFIT_FRAC), 2),
                   stopAt=round(credit + STOP_LOSS_FRAC * max_loss, 2), legs=legs), None


def fly_value(prices: dict[tuple[str, float], float], fly: IronFly) -> float:
    """Cost to buy the fly back now (per unit): short legs' ask - long legs' bid, given {(CE|PE, strike): price}."""
    v = 0.0
    for act, side, strike, _px, _key in fly.legs:
        p = prices[(side, strike)]
        v += p if act == "SELL" else -p
    return v


def check_exit(fly: IronFly, value_now: float, now: datetime, spot_close_5m: float | None = None) -> str | None:
    """TAKE_PROFIT / STOP / BREAKEVEN / TIME, or None to keep holding. `spot_close_5m` = last completed 5-minute close:
    a close beyond a breakeven (ATM +- credit) means the market has left the fly's profit zone -- get out."""
    if value_now <= fly.takeProfitAt:
        return "TAKE_PROFIT"
    if value_now >= fly.stopAt:
        return "STOP"
    if spot_close_5m is not None and abs(spot_close_5m - fly.atm) > fly.credit:
        return "BREAKEVEN"
    if now.time() >= TIME_EXIT:
        return "TIME"
    return None


def pnl_rs(fly: IronFly, exit_value: float, lots: int = 1) -> float:
    """Net rupees for `lots` lots after all 8 orders' charges."""
    return round((fly.credit - exit_value) * fly.lotUnits * lots - fly.costRs * lots, 2)
