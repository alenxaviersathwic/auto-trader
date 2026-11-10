"""Per-underlying daily guardrails (service/guardrails.py)."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.modules.opportunities.service import guardrails as g

NOW = datetime(2026, 11, 9, 9, 0, tzinfo=UTC)


def row(side="CE", mins_ago=60, outcome="PENDING", resolved_mins_ago=None, strategy=None, realized_pnl=None):
    return SimpleNamespace(optionType=side, createdAt=NOW - timedelta(minutes=mins_ago), outcome=outcome,
                           resolvedAt=None if resolved_mins_ago is None else NOW - timedelta(minutes=resolved_mins_ago),
                           strategy=strategy, realizedPnl=realized_pnl)


def pick(side):
    return {"id": f"X-{side}", "side": side}


def test_nothing_today_keeps_everything():
    assert g.apply([], [pick("CE"), pick("PE")], NOW) == ([pick("CE"), pick("PE")], None)


def test_daily_cap():
    today = [row(mins_ago=100 + i) for i in range(g.MAX_PER_DAY)]
    kept, why = g.apply(today, [pick("PE")], NOW)
    assert kept == [] and "daily cap" in why
    kept, why = g.apply(today[:-1], [pick("CE"), pick("PE")], NOW)
    assert len(kept) == 1


def test_two_stops_in_a_row_pause_then_release():
    today = [row(mins_ago=90, outcome="STOP_HIT", resolved_mins_ago=40),
             row("PE", mins_ago=60, outcome="STOP_HIT", resolved_mins_ago=10)]
    kept, why = g.apply(today, [pick("PE")], NOW)
    assert kept == [] and "2 stops" in why
    today[1].resolvedAt = NOW - timedelta(minutes=g.LOSS_PAUSE_MIN + 1)
    assert g.apply(today, [pick("PE")], NOW)[0] == [pick("PE")]
    today[0].outcome = "TARGET_HIT"  # a win in between: no pause
    today[1].resolvedAt = NOW - timedelta(minutes=5)
    assert g.apply(today, [pick("PE")], NOW)[0] == [pick("PE")]


def test_same_side_cooldown():
    today = [row("CE", mins_ago=2)]
    kept, why = g.apply(today, [pick("CE"), pick("PE")], NOW)
    assert kept == [pick("PE")] and "CE cooldown" in why
    today[0].createdAt = NOW - timedelta(minutes=g.SIDE_COOLDOWN_MIN + 1)
    assert g.apply(today, [pick("CE")], NOW)[0] == [pick("CE")]


def test_daily_drawdown_stop_blocks_once_today_net_breaches_limit():
    today = [row(mins_ago=120, outcome="STOP_HIT", resolved_mins_ago=100, realized_pnl=-1800),
             row("PE", mins_ago=80, outcome="STOP_HIT", resolved_mins_ago=60, realized_pnl=-1900)]
    kept, why = g.apply(today, [pick("CE")], NOW, max_daily_loss=3000)
    assert kept == [] and "daily drawdown" in why
    # same two trades, a looser limit: not breached, so the pick survives (modulo the unrelated side cooldown)
    today[1].createdAt = NOW - timedelta(minutes=g.SIDE_COOLDOWN_MIN + 1)
    kept, why = g.apply(today, [pick("PE")], NOW, max_daily_loss=10000)
    assert kept == [pick("PE")] and why is None


def test_setup_demoted_after_enough_net_negative_recent_trades():
    recent = [row(mins_ago=0, outcome="STOP_HIT", strategy="FAILED_BREAK_RECLAIM", realized_pnl=-500)
              for _ in range(g.SETUP_DEMOTE_MIN_N)]
    p = {"id": "X-CE", "side": "CE", "setup": "FAILED_BREAK_RECLAIM"}
    kept, why = g.apply([], [p], NOW, recent=recent)
    assert kept == [] and "demoted" in why
    # fewer than SETUP_DEMOTE_MIN_N trades: too small a sample to demote on, so it still fires
    kept, why = g.apply([], [p], NOW, recent=recent[: g.SETUP_DEMOTE_MIN_N - 1])
    assert kept == [p] and why is None
    # a different setup on the same recent history is unaffected
    other = {"id": "X-PE", "side": "PE", "setup": "NOISE_BREAKOUT"}
    kept, why = g.apply([], [other], NOW, recent=recent)
    assert kept == [other] and why is None
