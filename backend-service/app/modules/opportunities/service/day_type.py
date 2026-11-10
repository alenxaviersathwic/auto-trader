"""
Day type: is today paying option BUYERS (expansion) or option SELLERS (pin)?  Pure functions.

Research behind it (docs/05 section 3d):
  * Zarattini, Aziz & Barbon (2024) "noise area": for each time of day, sigma = the average absolute move from the
    open at that time over the last 14 sessions. Inside  max(open, prevClose) x (1 + sigma) .. min(open, prevClose)
    x (1 - sigma)  the move is ordinary noise; outside it, intraday momentum has followed (US data; replicate here).
  * Baltussen et al. (JFE 2021): momentum on negative-gamma days, reversal on positive-gamma days. The dealer gamma
    SIGN cannot be read from NSE data, so the day type is inferred from what price/IV/OI are doing, not assumed.
  * SEBI FY26: ~88-90 % of individual option buyers lose; 0-DTE theta eats sideways premium. So trend/breakout
    setups and out-of-the-money strikes are only allowed on TREND / EXPANSION days.

  PIN        expiry within a day, price inside a tight OI box and inside the noise area, VIX not rising
             -> theta wins: only fades at the box edge / reclaims, ATM strikes
  RANGE      inside the noise area (default)            -> only reclaims and range setups, ATM strikes
  TREND      a 5-minute close outside the noise area    -> breakout / pullback setups with that side
  EXPANSION  TREND plus fuel: big gap, VIX rising, day range >= 80 % of the daily ATR, or price through an OI wall
"""
from typing import Any

NOISE_DAYS = 14
MIN_NOISE_DAYS = 8
PROXY_ATR_SHARE = 0.55  # mean |close - open| of a day is about 0.55 x its ATR; scaled by sqrt(time) inside the day
PIN_AFTER_MIN = 75  # no PIN call before 10:30 on a 09:15 open
PIN_BOX_MOVES = 2.0  # OI box (put wall .. call wall) no wider than 2 x the straddle-implied move
EXPANSION_GAP_ATR = 0.5
EXPANSION_VIX_PCT = 3.0
EXPANSION_RANGE_PCT = 80


def noise_sigma(sessions: list[tuple[str, dict[int, dict[str, Any]]]], slot: int, days: int = NOISE_DAYS) -> float | None:
    """Average |close(slot) / open(first bar) - 1| over the last `days` sessions ([(date, {slot: 5-min bar})])."""
    moves = []
    for _, d in sessions[-days:]:
        first, b = d.get(0), d.get(slot)
        if first and b and first["o"] > 0:
            moves.append(abs(b["c"] / first["o"] - 1))
    return sum(moves) / len(moves) if len(moves) >= MIN_NOISE_DAYS else None


def noise_proxy(daily_atr: float, ref: float, minutes_since_open: int, session_minutes: int) -> float | None:
    """Fallback when the 5-minute history is not available: daily ATR scaled by the square root of elapsed time."""
    if not daily_atr or not ref or session_minutes <= 0:
        return None
    f = min(1.0, max(minutes_since_open, 5) / session_minutes)
    return PROXY_ATR_SHARE * daily_atr / ref * f ** 0.5


def noise_area(day_open: float, prev_close: float | None, sigma: float, price: float) -> dict[str, Any]:
    hi_ref, lo_ref = max(day_open, prev_close or day_open), min(day_open, prev_close or day_open)
    upper, lower = hi_ref * (1 + sigma), lo_ref * (1 - sigma)
    state = "ABOVE" if price > upper else "BELOW" if price < lower else "INSIDE"
    return {"upper": round(upper, 2), "lower": round(lower, 2), "sigmaPct": round(sigma * 100, 3), "state": state}


def round_levels(price: float, step: float) -> tuple[float, float]:
    """Nearest round numbers below / above price (stop orders cluster just beyond them: Osler 2005)."""
    below = (price // step) * step
    return below, below + step


def classify(a: dict[str, Any]) -> dict[str, Any]:
    """{type, side, reasons} from an analysis dict that already has noise / levels / oi / vix / dte."""
    noise = a.get("noise") or {}
    lv = a.get("levels") or {}
    oi = a.get("oi") or {}
    vix_chg = (a.get("vix") or {}).get("changePct")
    datr = a.get("dailyAtr") or 0
    spot = a.get("spot") or 0
    state = noise.get("state")
    if not state:
        return {"type": None, "side": None, "reasons": ["no noise area yet (needs the open and a daily ATR or history)"]}
    reasons: list[str] = []
    if state != "INSIDE":
        side = "CE" if state == "ABOVE" else "PE"
        edge = noise["upper"] if state == "ABOVE" else noise["lower"]
        reasons.append(f"5-min close {'above' if state == 'ABOVE' else 'below'} the noise area ({edge:.1f})")
        fuel: list[str] = []
        gap_pts = abs((lv.get("dayOpen") or 0) - (lv.get("pdc") or 0)) if lv.get("pdc") and lv.get("dayOpen") else 0
        if datr and gap_pts >= EXPANSION_GAP_ATR * datr:
            fuel.append(f"gap {gap_pts:.0f} pts >= {EXPANSION_GAP_ATR} daily ATR")
        if vix_chg is not None and vix_chg >= EXPANSION_VIX_PCT:
            fuel.append(f"India VIX {vix_chg:+.1f}%")
        if (a.get("rangeUsedPct") or 0) >= EXPANSION_RANGE_PCT:
            fuel.append(f"day range {a['rangeUsedPct']}% of the daily ATR")
        res, sup = oi.get("resistance"), oi.get("support")
        if spot and ((state == "ABOVE" and res and spot > res) or (state == "BELOW" and sup and spot < sup)):
            fuel.append("price through the OI wall")
        if fuel:
            return {"type": "EXPANSION", "side": side, "reasons": reasons + fuel}
        return {"type": "TREND", "side": side, "reasons": reasons}
    reasons.append(f"inside the noise area ({noise['lower']:.1f} - {noise['upper']:.1f})")
    dte = a.get("dte")
    res, sup = oi.get("resistance"), oi.get("support")
    move_pct = a.get("expectedMovePct")
    since = (a.get("session") or {}).get("minutesSinceOpen", 0)
    if dte is not None and dte <= 1 and since >= PIN_AFTER_MIN and res and sup and spot and sup <= spot <= res \
            and move_pct and (res - sup) <= PIN_BOX_MOVES * move_pct / 100 * spot and (vix_chg is None or vix_chg <= 0):
        return {"type": "PIN", "side": None,
                "reasons": reasons + [f"{dte} day(s) to expiry, inside the OI box {sup:.0f}-{res:.0f}, VIX not rising"]}
    return {"type": "RANGE", "side": None, "reasons": reasons}


_BIAS_RANK = {None: 0, "RANGE": 1, "PIN": 1, "TREND": 2, "EXPANSION": 3}
MIN_PERSIST_MIN = 15  # a NEW bias direction must survive this long before it sticks (see below)


def apply_bias(day_type: dict[str, Any], state: dict[str, Any] | None, minute: int) -> dict[str, Any]:
    """Make the day type STICKY across a session, but only once a new direction has proven itself.

    9 Nov/6 Nov 2026 post-mortem, two bugs in one:
    (1) `classify()` is recomputed from scratch every snapshot off a fixed open/prevClose anchor, so a normal
        pullback right after a TREND call reads back as RANGE for a few minutes -- reopening counter-trend
        RANGE/REVERSAL setups on a day that was, start to finish, running one way. Fix: `day_type_block()` checks
        this sticky `dayBias`, not the instantaneous `dayType`.
    (2) the first version of this function latched onto the FIRST TREND+ read unconditionally -- on BANKNIFTY,
        6 Nov 2026, a brief opening dip read TREND/PE for 14 minutes (09:20-09:34) before reverting; the real
        session trend was UP all day, but the sticky bias spent the whole morning confidently backing the wrong
        side, right through three losing trades, until EXPANSION/CE finally confirmed at 13:00. Fix: a direction
        change (no bias yet, or the opposite side) must hold for MIN_PERSIST_MIN minutes before it is promoted;
        a read that reverts before then is discarded, same as it always was pre-bias. Strengthening in place on
        the SAME side already held (TREND -> EXPANSION) needs no extra confirmation -- that direction already
        proved itself.

    `state` is whatever this function last returned for the same session (None at the open); read state["bias"]
    for the sticky {type, side, rank} dict `day_type_block()` checks. `minute` is minutes-since-midnight, used
    only to measure how long a candidate direction has held."""
    state = dict(state) if state else {}
    bias = state.get("bias")
    cur_type, cur_side = day_type.get("type"), day_type.get("side")
    cur_rank = _BIAS_RANK.get(cur_type, 0)
    if cur_rank < 2 or not cur_side:
        state["candSide"], state["bias"] = None, bias
        return state
    if bias and cur_side == bias.get("side"):
        if cur_rank > bias["rank"]:
            bias = {"type": cur_type, "side": cur_side, "rank": cur_rank}
        state["candSide"], state["bias"] = None, bias
        return state
    since = state.get("candSince", minute) if state.get("candSide") == cur_side else minute
    if minute - since >= MIN_PERSIST_MIN:
        bias, state["candSide"] = {"type": cur_type, "side": cur_side, "rank": cur_rank}, None
    else:
        state["candSide"], state["candSince"] = cur_side, since
    state["bias"] = bias
    return state
