"""
How finished trades change what the engine does next (pure functions, no I/O).

1. Setup scorecard (the "strategy" update, applied automatically)
   Per setup, over the last WINDOW_DAYS of autopsies (only trades after a manual resume count):
   closed trades, wins, net P&L, average R. A setup with at least PAUSE_MIN_TRADES closed trades and a net loss is
   PAUSED: the engine stops taking it. It comes back by itself when the losing trades age out of the window, or when
   you resume it. Win rate alone never pauses a setup: the momentum setups win rarely by design and pay through the
   few big winners, so only net P&L decides (the reference engine's quarantine also uses win rate < 40%).

2. Guards (the "rule" update)
   When the same failure tag shows up GUARD_MIN_REPEATS times for one setup inside the window, a guard is proposed.
   Each guard is a concrete restriction the engine enforces once applied:
     WITH_TREND_ONLY     (AGAINST_TREND)   the session skips this setup's against-trend picks
     NO_LATE_ENTRY       (LATE_ENTRY)      the engine stops signalling this setup in the last hour
     EARLIER_BREAKEVEN   (GAVE_BACK)       momentum trail moves the stop to breakeven at +1R instead of +1.5R
     MIN_TARGET_PCT      (FEES_ATE_PROFIT) the session skips this setup's picks whose target is below the value
   NEVER_WORKED has no guard: repeated, it is what pauses the setup through the scorecard.
"""
from datetime import datetime, timedelta
from statistics import median
from typing import Any

WINDOW_DAYS = 14
PAUSE_MIN_TRADES = 5
GUARD_MIN_REPEATS = 3
MOMENTUM_POLICIES = ("CORE", "MERGED")

GUARD_FOR_TAG: dict[str, str] = {
    "AGAINST_TREND": "WITH_TREND_ONLY",
    "LATE_ENTRY": "NO_LATE_ENTRY",
    "GAVE_BACK": "EARLIER_BREAKEVEN",
    "FEES_ATE_PROFIT": "MIN_TARGET_PCT",
}
GUARD_TEXT: dict[str, str] = {
    "WITH_TREND_ONLY": "Take {setup} only with the trend (skip picks marked against the trend).",
    "NO_LATE_ENTRY": "No new {setup} entries in the last {minutesToCloseMin} minutes of the session.",
    "EARLIER_BREAKEVEN": "{setup}: move the stop to breakeven at +{beR:g}R instead of +1.5R.",
    "MIN_TARGET_PCT": "{setup}: skip picks whose target is below +{minTargetPct:g}% of premium.",
}


def window_start(now: datetime, resumed_at: datetime | None = None) -> datetime:
    start = now - timedelta(days=WINDOW_DAYS)
    return max(start, resumed_at) if resumed_at else start


def scorecard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """`rows`: autopsies of ONE setup inside its window ({outcome, netPnl, rMultiple})."""
    n = len(rows)
    wins = sum(1 for r in rows if r["outcome"] == "WIN")
    net = round(sum(float(r["netPnl"]) for r in rows), 2)
    avg_r = round(sum(float(r["rMultiple"]) for r in rows) / n, 2) if n else 0.0
    paused = n >= PAUSE_MIN_TRADES and net < 0
    return {
        "closedTrades": n, "wins": wins, "losses": n - wins, "netPnl": net, "avgR": avg_r,
        "winRatePct": round(wins / n * 100, 1) if n else 0.0,
        "expectancy": round(net / n, 2) if n else 0.0,
        "status": "PAUSED" if paused else "ACTIVE",
        "statusReason": (f"{n} trades in {WINDOW_DAYS} days lost ₹{abs(net):,.0f} net (avg {avg_r:+.2f}R)"
                         if paused else None),
    }


def guard_params(guard_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if guard_type == "NO_LATE_ENTRY":
        return {"minutesToCloseMin": 60}
    if guard_type == "EARLIER_BREAKEVEN":
        return {"beR": 1.0}
    if guard_type == "MIN_TARGET_PCT":
        planned = [float(r["plannedTargetPct"]) for r in rows if r.get("plannedTargetPct")]
        return {"minTargetPct": round(1.5 * median(planned), 1) if planned else 15.0}
    return {}


def guard_proposals(setup: str, policy: str | None, rows: list[dict[str, Any]],
                    existing: set[str]) -> list[dict[str, Any]]:
    """Guards to propose for one setup. `rows` = its autopsies in the window ({id, tags, netPnl, plannedTargetPct});
    `existing` = guard types already proposed / applied / recently rejected for it."""
    out: list[dict[str, Any]] = []
    for tag, gtype in GUARD_FOR_TAG.items():
        if gtype in existing:
            continue
        if gtype == "EARLIER_BREAKEVEN" and policy not in MOMENTUM_POLICIES:
            continue  # only the momentum trail has a breakeven step to move
        hits = [r for r in rows if tag in (r.get("tags") or [])]
        if len(hits) < GUARD_MIN_REPEATS:
            continue
        params = guard_params(gtype, hits)
        out.append({
            "setup": setup, "guardType": gtype, "tag": tag, "params": params,
            "text": GUARD_TEXT[gtype].format(setup=setup, **params),
            "evidence": {"trades": len(hits), "tradeIds": [r["tradeId"] for r in hits],
                         "netPnl": round(sum(float(r["netPnl"]) for r in hits), 2), "windowDays": WINDOW_DAYS},
        })
    return out


# ───────────────────────── enforcement (read by the engine, the session loop and the trade pilot) ─────────────
def engine_block(view: dict[str, Any] | None, setup: str, minutes_to_close: int | None) -> str | None:
    """Why the live engine must not signal `setup`, from the learning view, or None."""
    if not view:
        return None
    paused = (view.get("paused") or {}).get(setup)
    if paused:
        return f"{setup} paused by its scorecard: {paused}"
    for g in (view.get("guards") or {}).get(setup, []):
        if g["guardType"] == "NO_LATE_ENTRY" and minutes_to_close is not None \
                and minutes_to_close < int(g["params"].get("minutesToCloseMin", 60)):
            return f"autopsy guard: no {setup} entries in the last {g['params'].get('minutesToCloseMin', 60)} minutes"
    return None


def pick_block(view: dict[str, Any] | None, setup: str | None, risks: list[Any] | None,
               target_pct: float | None) -> str | None:
    """Why the session must skip a saved opportunity of `setup`, or None."""
    if not view or not setup:
        return None
    paused = (view.get("paused") or {}).get(setup)
    if paused:
        return "setup paused by its scorecard"
    for g in (view.get("guards") or {}).get(setup, []):
        if g["guardType"] == "WITH_TREND_ONLY" and any(
                str(x).strip().lower().startswith("against the") for x in (risks or [])):
            return "autopsy guard: with the trend only"
        if g["guardType"] == "MIN_TARGET_PCT" and target_pct is not None \
                and target_pct < float(g["params"].get("minTargetPct", 0)):
            return "autopsy guard: target too small for the charges"
    return None


def trail_override(view: dict[str, Any] | None, setup: str | None, base: dict[str, float]) -> dict[str, float]:
    """Momentum trail for a running trade of `setup`, with an applied EARLIER_BREAKEVEN guard folded in."""
    if not view or not setup:
        return base
    for g in (view.get("guards") or {}).get(setup, []):
        if g["guardType"] == "EARLIER_BREAKEVEN":
            return {**base, "beR": min(base["beR"], float(g["params"].get("beR", base["beR"])))}
    return base
