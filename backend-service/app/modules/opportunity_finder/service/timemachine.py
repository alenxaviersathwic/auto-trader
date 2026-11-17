"""
Time Machine: the odds of a trade plan, read from the underlying's own recent 5-minute bars.

Ported from the Day Trader skill's `trader-timemachine` (github.com/Jakeschincariol/day-trader-skill, MIT) and
adapted to this engine: NSE/MCX sessions, CE/PE (long/short on the underlying), and a horizon equal to the
opportunity's validity window, because that is the window the outcome checker grades.

Given a setup's chart plan on the UNDERLYING (entry = last completed 5-minute close, stop = invalidation level,
target = next key level or 2R) it answers one question: if the next N minutes play out like the same minutes of
the last ~60 sessions, how often does this plan hit the target first, the stop first, or neither?

  1. The pool.     Every past full session's 5-minute bar i, as (open, high, low, close) / bar i-1's close.
                   Today is never in the pool (candles_5m_history drops it).
  2. One replay.   Start at the entry. For each bar left in the horizon, draw a past bar from the same time of day
                   (+/- WINDOW bars) at random and scale it to the current price. Stop is checked before target:
                   a bar that touches both counts as the stop (conservative, same rule as the outcome checker).
  3. REPLAYS runs  give P(target first), P(stop first), P(neither), the average R and the average R of the
                   'neither' runs (price at the end of the horizon, in units of risk).
  4. The history.  The same plan, as % distances, walked over the REAL bars of every past session from the same
                   time of day. That is what actually happened, not a simulation.
  5. The lean.     A bigger target needs to win less often: break-even share of the side-hitting runs is 1/(1+R).
                   lean = P(target | a side was hit) - 1/(1+R). Within +/-5 points: a coin flip / break-even.

Same plan + same pool + same seed => the same numbers on every machine. Pure functions, no I/O, except the small
per-day pool cache in `pool_for()`.
"""
from __future__ import annotations

import math
import random
import statistics
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.logging.logger import logger

_IST = ZoneInfo("Asia/Kolkata")
BAR_MIN = 5
REPLAYS = 2000
SEED = 19
WINDOW = 2  # draw a past bar within +/- 2 bars (10 minutes) of the same time of day
MIN_SESSIONS = 20  # fewer full past sessions than this: no verdict, the opportunity is judged without it
COIN_FLIP = 0.05  # |lean| under 5 points: close to a coin flip / break-even
STRONG = 0.15  # |lean| of 15 points or more: strongly toward one side
DROP_LEAN = -0.05  # leaning toward the stop by 5 points or more: not an opportunity
MIN_SIDE_HITS = 0.15  # fewer than 15 % of replays hit any side: the horizon is too short to judge, no gate
HISTORY_DAYS = 90  # calendar days of 5-minute bars to fetch (~60 sessions)
RETRY_AFTER_FAIL_S = 600.0


def _minute(t: str) -> int:
    return int(t[11:13]) * 60 + int(t[14:16])


def _hhmm(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


# ───────────────────────── pool ─────────────────────────
def sessions_from_bars(bars: list[dict[str, Any]], open_hhmm: str) -> list[tuple[str, dict[int, dict[str, Any]]]]:
    """[(date, {slot: bar})] oldest first; slot 0 is the bar that opens the session."""
    open_min = _hhmm(open_hhmm)
    days: dict[str, dict[int, dict[str, Any]]] = {}
    for b in bars:
        slot = (_minute(b["t"]) - open_min) // BAR_MIN
        if slot < 0 or b["c"] <= 0:
            continue
        days.setdefault(b["t"][:10], {})[slot] = b
    return sorted(days.items())


def build_pool(sessions: list[tuple[str, dict[int, dict[str, Any]]]]) -> dict[int, list[tuple[float, float, float, float]]]:
    """pool[i] = every past session's bar i as ratios to bar i-1's close (only where both bars exist)."""
    pool: dict[int, list[tuple[float, float, float, float]]] = {}
    for _, d in sessions:
        for i, b in d.items():
            prev = d.get(i - 1)
            if i < 1 or not prev or prev["c"] <= 0:
                continue
            pc = prev["c"]
            pool.setdefault(i, []).append((b["o"] / pc, b["h"] / pc, b["l"] / pc, b["c"] / pc))
    return pool


def full_session_count(sessions: list[tuple[str, dict[int, dict[str, Any]]]], k: int, last: int) -> int:
    """Past sessions that have every bar from k to last (the ones the history can walk)."""
    return sum(1 for _, d in sessions if all(i in d for i in range(k, last + 1)))


# ───────────────────────── simulation ─────────────────────────
def simulate(pool: dict[int, list[tuple[float, float, float, float]]], entry: float, stop: float, target: float,
             k: int, last: int, long: bool, replays: int = REPLAYS, seed: int = SEED,
             window: int = WINDOW) -> dict[str, Any] | None:
    """Monte Carlo replays of bars k+1..last starting at `entry`. None when the pool cannot cover the horizon."""
    risk = (entry - stop) if long else (stop - entry)
    reward = (target - entry) if long else (entry - target)
    if risk <= 0 or reward <= 0 or last <= k:
        return None
    if any(not pool.get(i) for i in range(k + 1, last + 1)):
        return None
    r_target = reward / risk
    hi_slot = max(pool)
    rng = random.Random(seed)

    def draw(i: int) -> tuple[float, float, float, float]:
        j = i if window == 0 else min(hi_slot, max(1, i + rng.randint(-window, window)))
        return rng.choice(pool.get(j) or pool[i])

    n_t = n_s = 0
    rs: list[float] = []
    neither_rs: list[float] = []
    for _ in range(replays):
        p = entry
        outcome = None
        for i in range(k + 1, last + 1):
            _o, h, l, c = draw(i)
            hi, lo = p * h, p * l
            if long:
                if lo <= stop:
                    outcome = "stop"
                elif hi >= target:
                    outcome = "target"
            else:
                if hi >= stop:
                    outcome = "stop"
                elif lo <= target:
                    outcome = "target"
            if outcome:
                break
            p = p * c
        if outcome == "target":
            n_t += 1
            rs.append(r_target)
        elif outcome == "stop":
            n_s += 1
            rs.append(-1.0)
        else:
            r = ((p - entry) if long else (entry - p)) / risk
            r = max(-1.0, min(r_target, r))
            rs.append(r)
            neither_rs.append(r)
    return {
        "replays": replays, "seed": seed, "window": window, "barsAhead": last - k,
        "pTarget": round(n_t / replays, 4), "pStop": round(n_s / replays, 4),
        "pNeither": round((replays - n_t - n_s) / replays, 4),
        "avgR": round(statistics.mean(rs), 3),
        "avgRNeither": round(statistics.mean(neither_rs), 3) if neither_rs else 0.0,
        "rAtTarget": round(r_target, 2),
    }


def history(sessions: list[tuple[str, dict[int, dict[str, Any]]]], k: int, last: int, risk_pct: float,
            reward_pct: float, long: bool) -> dict[str, Any]:
    """The same plan (as % distances from the entry) on the REAL bars of every past session, from bar k's close."""
    t = s = n = 0
    rs: list[float] = []
    r_target = reward_pct / risk_pct if risk_pct > 0 else 0.0
    for _, d in sessions:
        if not all(i in d for i in range(k, last + 1)):
            continue
        e = d[k]["c"]
        stop = e * (1 - risk_pct / 100) if long else e * (1 + risk_pct / 100)
        tgt = e * (1 + reward_pct / 100) if long else e * (1 - reward_pct / 100)
        oc = None
        for i in range(k + 1, last + 1):
            b = d[i]
            if (b["l"] <= stop) if long else (b["h"] >= stop):
                oc = "stop"
                break
            if (b["h"] >= tgt) if long else (b["l"] <= tgt):
                oc = "target"
                break
        if oc == "target":
            t += 1
            rs.append(r_target)
        elif oc == "stop":
            s += 1
            rs.append(-1.0)
        else:
            n += 1
            cl = d[last]["c"]
            rs.append(max(-1.0, min(r_target, ((cl - e) if long else (e - cl)) / (e * risk_pct / 100))))
    return {"sessions": t + s + n, "target": t, "stop": s, "neither": n,
            "avgR": round(statistics.mean(rs), 3) if rs else None}


def lean(p_target: float, p_stop: float, r: float) -> tuple[float, float, float] | None:
    """(gap, share, breakEven): the target's share of the runs that hit a side, minus the share needed at R."""
    if p_target + p_stop <= 0:
        return None
    share, even = p_target / (p_target + p_stop), 1.0 / (1.0 + max(r, 0.01))
    return share - even, share, even


def verdict(mc: dict[str, Any]) -> str:
    lv = lean(mc["pTarget"], mc["pStop"], mc["rAtTarget"])
    if lv is None:
        return "No replay reached the target or the stop in the window: the price at the end decides every one"
    d, share, even = lv
    one_r = abs(mc["rAtTarget"] - 1.0) < 0.05
    if abs(d) < COIN_FLIP:
        head = "Close to a coin flip" if one_r else "Close to break-even"
    elif abs(d) < STRONG:
        head = "Leans toward the target" if d > 0 else "Leans toward the stop"
    else:
        head = "Strongly toward the target" if d > 0 else "Strongly toward the stop"
    return (f"{head}: at {mc['rAtTarget']:g}R the target must come first in {even * 100:.0f}% of the runs that hit a "
            f"side, it did in {share * 100:.0f}%")


def evaluate(sessions: list[tuple[str, dict[int, dict[str, Any]]]], pool: dict[int, list[tuple[float, float, float, float]]],
             entry: float, stop: float, target: float, long: bool, k: int, last: int) -> dict[str, Any] | None:
    """Odds + history + verdict for one plan, or None when there is not enough history to judge."""
    if full_session_count(sessions, k, last) < MIN_SESSIONS:
        return None
    mc = simulate(pool, entry, stop, target, k, last, long)
    if mc is None:
        return None
    risk_pct = abs(entry - stop) / entry * 100
    reward_pct = abs(target - entry) / entry * 100
    hist = history(sessions, k, last, risk_pct, reward_pct, long)
    lv = lean(mc["pTarget"], mc["pStop"], mc["rAtTarget"])
    mc.update({
        "entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2),
        "lean": round(lv[0], 4) if lv else None,
        "targetShare": round(lv[1], 4) if lv else None,
        "breakEven": round(lv[2], 4) if lv else None,
        "history": hist,
        "verdict": verdict(mc),
    })
    return mc


def judged(tm: dict[str, Any]) -> bool:
    """Enough replays hit a side for the lean to mean something (a short window mostly ends at 'neither')."""
    return tm.get("lean") is not None and (tm["pTarget"] + tm["pStop"]) >= MIN_SIDE_HITS


def edge_pct(tm: dict[str, Any], target_pct: float, stop_pct: float, cost_pct: float) -> float:
    """Average option-premium % per trade from the replay odds: target first pays target_pct, stop first costs
    stop_pct, 'neither' pays its average R in units of the premium stop (1R on the chart ~ the premium stop)."""
    return round(tm["pTarget"] * target_pct - tm["pStop"] * stop_pct
                 + tm["pNeither"] * tm["avgRNeither"] * stop_pct - cost_pct, 2)


def horizon(open_hhmm: str, close_hhmm: str, last_bar_t: str, valid_minutes: int) -> tuple[int, int]:
    """(k, last): k = slot of the last completed 5-minute bar (the entry bar), last = the slot the validity
    window ends in, never past the session's last bar."""
    open_min = _hhmm(open_hhmm)
    k = (_minute(last_bar_t) - open_min) // BAR_MIN
    close_slot = (_hhmm(close_hhmm) - open_min) // BAR_MIN - 1
    return k, min(close_slot, k + max(1, math.ceil(valid_minutes / BAR_MIN)))


# ───────────────────────── per-day pool cache ─────────────────────────
# key (instrument key) -> (IST date, sessions, pool) or (IST date, None, failed_at)
_cache: dict[str, tuple[str, Any, Any]] = {}


async def pool_for(key: str, open_hhmm: str, fetch) -> tuple[list, dict] | None:
    """Sessions + pool for an instrument, fetched once per IST day. `fetch(key)` returns the 5-minute bars.
    A failed fetch is not retried for RETRY_AFTER_FAIL_S so a bad token does not add a request per iteration."""
    if not key:
        return None
    today = datetime.now(_IST).date().isoformat()
    hit = _cache.get(key)
    if hit and hit[0] == today:
        if hit[1] is not None:
            return hit[1], hit[2]
        if time.monotonic() - hit[2] < RETRY_AFTER_FAIL_S:
            return None
    try:
        bars = await fetch(key)
    except Exception as e:  # the Time Machine sharpens a pick, it is never required
        logger.warning(f"[TIME_MACHINE] history for {key} unavailable: {type(e).__name__}: {e}")
        _cache[key] = (today, None, time.monotonic())
        return None
    sessions = sessions_from_bars(bars, open_hhmm)
    pool = build_pool(sessions)
    _cache[key] = (today, sessions, pool)
    logger.info(f"[TIME_MACHINE] {key}: {len(bars)} bars, {len(sessions)} sessions in the pool")
    return sessions, pool
