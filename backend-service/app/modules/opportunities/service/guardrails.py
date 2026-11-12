"""
Signal guardrails per underlying per day, so loosening the entry rules does not turn into noise.

SEBI's FY23 intraday study: 80 % of 'very frequent' traders lost money vs ~71 % overall; disciplined index traders
take a handful of quality setups a day. Applied to the picks of one iteration, before they are saved:

  DAILY_CAP        at most MAX_PER_DAY opportunities per underlying per IST day
  LOSS_PAUSE       the last two resolved picks were both STOP_HIT and the newer stop is < LOSS_PAUSE_MIN old:
                   nothing new until the pause ends (the market is not doing what the setups expect)
  SIDE_COOLDOWN    no second pick on the same side (CE/PE) within SIDE_COOLDOWN_MIN of the previous one
                   (9 Nov 2026: two BANKNIFTY CE picks 70 s apart, both stopped)
  SETUP_REPEAT     at most MAX_PER_SETUP picks of the SAME setup name AND SIDE per underlying per day: a PE
                   reclaim that fires 3-4 times on one choppy day is the SAME read being wrong repeatedly, not
                   3-4 independent opportunities. Keyed by side, not just name, so a good CE reclaim is never
                   capped out by unrelated PE reclaims earlier in the day (10 Nov 2026 review: NIFTY 9 Nov had
                   3 FAILED_BREAK_RECLAIM PE picks, -970/-1,212/-1,075, and 1 FAILED_BREAK_RECLAIM CE, +4,598 --
                   capping by name alone would have also blocked the CE winner)
  DAILY_DRAWDOWN   today's resolved rows (realizedPnl) have already lost MAX_DAILY_LOSS_RS or more: stop for the
                   rest of the day rather than trying to trade back to flat (10 Nov 2026 research review: SEBI
                   FY26 data + Freqtrade's MaxDrawdown protection -- a rolling loss limit, not a per-trade one)
  SETUP_DEMOTED    this (setup, side) has gone net-negative over its last SETUP_DEMOTE_LOOKBACK resolved trades
                   (min SETUP_DEMOTE_MIN_N of them): hold it out until a human re-enables it, rather than
                   re-tuning the same setup trade by trade (Freqtrade's LowProfitPairs analogue; this is a
                   practitioner heuristic, not a peer-reviewed significance test -- see 10 Nov 2026 research
                   review for why a real t-stat/DSR bar needs more trades than any one setup sees in weeks)
Pure function; the caller loads today's rows (`today`) and, for the last two checks, a longer lookback
(`recent`, `max_daily_loss`) -- both optional so older callers / backtests that don't track realizedPnl yet
keep working unchanged.
"""
from datetime import datetime, timedelta
from typing import Any

from app.modules.backtest.service.edge_stats import kill_verdict

MAX_PER_DAY = 4  # SEBI FY26: traders active on most days carry most of the losses; few, selective trades
MAX_PER_SETUP = 2  # a losing read repeated a 3rd/4th time is not a new opportunity
LOSS_PAUSE_MIN = 30
SIDE_COOLDOWN_MIN = 10
MAX_DAILY_LOSS_RS: float | None = None  # None = disabled; set per-underlying via params (rupee, one lot)
SETUP_DEMOTE_LOOKBACK = 10  # trades, not days -- a slow setup may take weeks to gather this many
SETUP_DEMOTE_MIN_N = 8  # below this, "net negative" is noise, not a verdict (see research review)
_RESOLVED = ("TARGET_HIT", "STOP_HIT", "EXPIRED")


def _demoted_setups(recent: list[Any]) -> set[tuple[str, str]]:
    """(setup, side) pairs whose last SETUP_DEMOTE_LOOKBACK resolved trades, each, are net <= 0 with at least
    SETUP_DEMOTE_MIN_N of them. `recent` should already be ordered oldest-first; only rows with a `realizedPnl`
    (rupee) and a `strategy` name count -- rows without it (older data, or a backtest that hasn't wired it in
    yet) are silently skipped, same as a missing `strategy` already is elsewhere in this module."""
    by_key: dict[tuple[str, str], list[float]] = {}
    for r in recent:
        name = getattr(r, "strategy", None)
        pnl = getattr(r, "realizedPnl", None)
        if not name or pnl is None:
            continue
        key = (name, r.optionType)
        by_key.setdefault(key, []).append(float(pnl))
    demoted = set()
    for key, pnls in by_key.items():
        window = pnls[-SETUP_DEMOTE_LOOKBACK:]
        if len(window) >= SETUP_DEMOTE_MIN_N and sum(window) <= 0:
            demoted.add(key)
        elif kill_verdict(pnls)[0]:
            # 11 Nov 2026 research review (gap 3): the statistical kill -- last 50 trades' expectancy below zero
            # at 90% one-sided confidence -- catches a slow bleed the 10-trade heuristic can miss
            demoted.add(key)
    return demoted


def apply(today: list[Any], picks: list[dict[str, Any]], now: datetime,
          max_per_day: int = MAX_PER_DAY, max_per_setup: int = MAX_PER_SETUP,
          max_daily_loss: float | None = MAX_DAILY_LOSS_RS, recent: list[Any] | None = None,
          ) -> tuple[list[dict[str, Any]], str | None]:
    """(kept picks, reason when something was held back). `today` = this underlying's rows created today.
    `max_daily_loss` (rupee, positive number) and `recent` (resolved rows over a longer lookback, for the
    per-setup demotion check) are both optional so existing callers are unaffected until they opt in."""
    if not picks:
        return picks, None
    if len(today) >= max_per_day:
        return [], f"daily cap: {len(today)} opportunities already today (max {max_per_day})"
    resolved = sorted((r for r in today if r.outcome in _RESOLVED and r.resolvedAt),
                      key=lambda r: r.resolvedAt)
    last2 = resolved[-2:]
    if len(last2) == 2 and all(r.outcome == "STOP_HIT" for r in last2) \
            and now - last2[-1].resolvedAt < timedelta(minutes=LOSS_PAUSE_MIN):
        until = last2[-1].resolvedAt + timedelta(minutes=LOSS_PAUSE_MIN)
        return [], f"paused after 2 stops in a row (until {until:%H:%M} UTC)"
    if max_daily_loss and resolved:
        today_net = sum(float(getattr(r, "realizedPnl", 0) or 0) for r in resolved)
        if today_net <= -abs(max_daily_loss):
            return [], f"daily drawdown stop: Rs {today_net:+,.0f} today (limit Rs -{abs(max_daily_loss):,.0f})"
    demoted = _demoted_setups(recent) if recent else set()
    last_by_side: dict[str, datetime] = {}
    for r in today:
        if r.optionType not in last_by_side or r.createdAt > last_by_side[r.optionType]:
            last_by_side[r.optionType] = r.createdAt
    setup_count: dict[tuple[str, str], int] = {}
    for r in today:
        name = getattr(r, "strategy", None)
        if name:
            key = (name, r.optionType)
            setup_count[key] = setup_count.get(key, 0) + 1
    held: list[str] = []
    repeat: list[str] = []
    demoted_hit: list[str] = []
    kept = []
    for p in picks:
        t = last_by_side.get(p["side"])
        if t and now - t < timedelta(minutes=SIDE_COOLDOWN_MIN):
            held.append(p["side"])
            continue
        name = p.get("setup") or p.get("strategy")
        key = (name, p["side"]) if name else None
        if key and key in demoted:
            demoted_hit.append(f"{name} {p['side']}")
            continue
        if key and setup_count.get(key, 0) >= max_per_setup:
            repeat.append(f"{name} {p['side']}")
            continue
        kept.append(p)
        if key:
            setup_count[key] = setup_count.get(key, 0) + 1
    kept = kept[: max(0, max_per_day - len(today))]
    if len(kept) < len(picks):
        bits = []
        if held:
            bits.append(f"{'/'.join(sorted(set(held)))} cooldown {SIDE_COOLDOWN_MIN} min")
        if repeat:
            bits.append(f"{'/'.join(sorted(set(repeat)))} already fired {max_per_setup}x today")
        if demoted_hit:
            bits.append(f"{'/'.join(sorted(set(demoted_hit)))} demoted: net negative over last "
                        f"{SETUP_DEMOTE_LOOKBACK} trades")
        return kept, "; ".join(bits) or "daily cap"
    return kept, None
