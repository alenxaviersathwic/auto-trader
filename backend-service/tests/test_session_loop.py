"""MANUAL session loop: sizing rules, pick lifecycle, Trade Lock and risk limits. No DB: fake repos."""

import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.exception.app_exceptions import ConflictException
from app.modules.sessions.entity.session_pick_entity import SessionPick
from app.modules.sessions.entity.trading_session_entity import TradingSession
from app.modules.sessions.service import session_sizing as sz
from app.modules.sessions.service.session_loop_service import SessionLoopService

NOW = lambda: datetime.now(UTC)  # noqa: E731
TODAY = lambda: datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()  # noqa: E731


class FakeDb:
    async def flush(self):
        pass


class FakeSessions:
    def __init__(self, s):
        self.s = s

    async def get_by_id(self, db, sid):
        return self.s if self.s.id == sid else None


class FakePicks:
    def __init__(self):
        self.rows: list[SessionPick] = []

    async def open_picks(self, db, sid):
        return [p for p in self.rows if p.sessionId == sid and p.pickState in ("OFFERED", "LOCKED")]

    async def offered_opportunity_ids(self, db, sid):
        return {p.opportunityId for p in self.rows if p.sessionId == sid}

    async def save(self, db, p):
        p.id = len(self.rows) + 1
        p.createdAt = NOW()
        self.rows.append(p)
        return p

    async def get_by_id(self, db, pid):
        return next((p for p in self.rows if p.id == pid), None)


class FakeOpps:
    def __init__(self, items=None):
        self.items = items or []

    price: float | None = 101.5

    async def saved_candidates(self, db, codes, max_age):
        self.max_age = max_age
        return [o for o in self.items if o["underlyingCode"] in codes]

    async def live_premium(self, db, instrument_key):
        return self.price


def opp(i=1, **kw):
    base = {"id": i, "ref": f"OP-NIFTY-{i}", "underlyingCode": "NIFTY", "optionType": "CE", "strike": 25000.0,
            "expiry": "2026-11-12", "entry": 100.0, "stop": 96.5, "target": 110.0, "confidence": 78, "rewardRisk": 2.86,
            "strategy": "ORB", "reasons": ["a"], "risks": ["b"], "instrumentKey": "NSE_FO|1", "exchange": "NSE",
            "lotUnits": 65, "profitMarginPct": 10.0, "createdAt": (NOW() - timedelta(seconds=10)).isoformat(),
            "validUntil": (NOW() + timedelta(minutes=5)).isoformat()}
    base.update(kw)
    return base


def make(items=None, **sess):
    s = TradingSession(
        name="t", tradeDate=TODAY(), userId=1, capital=100000, maxLossPercentage=3, scope="INDEX",
        underlyings=["NIFTY"], commodityItems=[], sessionType="MANUAL", routeThroughUpstox=False,
        sessionStatus="ACTIVE", realizedPnl=0, haltedAt=None, haltReason=None,
    )
    s.id = 7
    for k, v in sess.items():
        setattr(s, k, v)
    picks = FakePicks()
    return SessionLoopService(FakeSessions(s), picks, FakeOpps(items or [opp()])), s, picks


def run(coro):
    return asyncio.run(coro)


# ───────────────────────── sizing ─────────────────────────
def test_entry_ceiling_keeps_min_reward_risk():
    p = sz.entry_ceiling(100.0, 96.5, 110.0)
    assert p >= 100.0 and (110.0 - p) / (p - 96.5) >= sz.MIN_RR_AT_ENTRY - 0.02
    assert sz.entry_ceiling(100.0, 99.99, 100.01) == 100.0  # never below the entry itself


def test_usage_follows_win_probability_from_minimum_to_maximum():
    cap = sz.capital_state(100000, 3, 0, [])  # loss budget 3000 -> 13 lots by risk, 15 by cash: max 13 lots
    sizes = {c: sz.size_candidate(opp(confidence=c), cap)[0] for c in (40, 50, 65, 78, 90, 100)}
    assert sizes[40].lots == 1 and sizes[50].lots == 1  # a coin-flip or worse: minimum quantity / money
    assert sizes[100].lots == 13  # 100% sure: the most the loss budget (and cash) allow
    lots = [sizes[c].lots for c in (40, 50, 65, 78, 90, 100)]
    assert lots == sorted(lots) and len(set(lots)) >= 5  # monotonic: more sure -> more money
    assert sizes[100].capitalRequired > sizes[65].capitalRequired > sizes[50].capitalRequired
    assert sizes[78].winProbPct == 78.0 and 0 < sizes[78].usagePct < sizes[100].usagePct
    assert sizes[78].riskAmount == sizes[78].lots * 65 * 3.5


def test_sizing_is_capped_by_free_cash_and_by_the_loss_budget_never_by_a_trade_count():
    full = sz.size_candidate(opp(confidence=100), sz.capital_state(100000, 3, 0, []))[0]
    assert full.riskAmount <= 3000
    cash_poor = sz.capital_state(100000, 30, 0, [type("P", (), {"capitalRequired": 80000, "riskAmount": 10})()])
    z, _ = sz.size_candidate(opp(confidence=100), cash_poor)  # 20000 free -> 3 lots at 6500
    assert z.lots == 3 and z.capitalRequired <= 20000
    broke = sz.capital_state(100000, 3, 0, [type("P", (), {"capitalRequired": 95000, "riskAmount": 100})()])
    z2, why2 = sz.size_candidate(opp(), broke)
    assert z2 is None and why2 == "not enough free capital"
    assert not hasattr(sz, "MAX_TRADES_PER_SESSION") and not hasattr(sz, "MAX_TRADES_PER_STRATEGY")


def test_loss_budget_and_realised_loss_shrink_size():
    cap = sz.capital_state(100000, 3, -2800, [])  # 200 of the 3000 loss budget left
    assert cap.currentCapital == 97200 and cap.remainingLossBudget == 200
    z, why = sz.size_candidate(opp(confidence=100), cap)
    assert z is None and why == "loss budget below 1 lot"


# ───────────────────────── tick / session table ─────────────────────────
def test_tick_offers_every_fitting_opportunity_ranked_each_open_until_its_opportunity_expires():
    svc, _, picks = make([opp(1, confidence=60), opp(2, confidence=85), opp(3, confidence=72)])
    r1 = run(svc.tick(FakeDb(), 7))
    assert r1.state == "PICK_READY" and len(r1.picks) == 3
    assert [p.opportunityId for p in r1.picks] == [2, 3, 1]  # best expected net first
    assert all(290 <= p.secondsLeft <= 300 and p.stop < p.entry <= p.entryMax < p.target and p.lots >= 1 for p in r1.picks)
    r2 = run(svc.tick(FakeDb(), 7))
    assert [p.id for p in r2.picks] == [p.id for p in r1.picks] and len(picks.rows) == 3  # steady: no new rows


def test_each_row_expires_on_its_own_and_is_never_reoffered():
    svc, _, picks = make([opp(1, confidence=85), opp(2, confidence=72)])
    run(svc.tick(FakeDb(), 7))
    picks.rows[0].expiresAt = NOW() - timedelta(seconds=1)  # row 1: its opportunity expired without a lock
    r = run(svc.tick(FakeDb(), 7))
    assert picks.rows[0].pickState == "EXPIRED" and [p.opportunityId for p in r.picks] == [2]
    picks.rows[1].expiresAt = NOW() - timedelta(seconds=1)
    r = run(svc.tick(FakeDb(), 7))
    assert r.state == "WAITING" and r.picks == [] and r.scanned["excluded"] == {"already offered": 2}


def test_offer_lasts_as_long_as_its_opportunity_and_short_lived_ones_are_skipped():
    svc, _, _ = make([opp(1, validUntil=(NOW() + timedelta(seconds=12)).isoformat()), opp(2)])
    r = run(svc.tick(FakeDb(), 7))
    by_id = {p.opportunityId: p for p in r.picks}
    assert by_id[1].secondsLeft <= 12.01 and by_id[2].secondsLeft > 290
    svc2, _, _ = make([opp(1, validUntil=(NOW() + timedelta(seconds=3)).isoformat())])
    r2 = run(svc2.tick(FakeDb(), 7))
    assert r2.state == "WAITING" and r2.scanned["excluded"] == {"expires too soon": 1}


def test_table_shows_at_most_max_open_offers():
    svc, _, picks = make([opp(i) for i in range(1, sz.MAX_OPEN_OFFERS + 4)])
    r = run(svc.tick(FakeDb(), 7))
    assert len(r.picks) == sz.MAX_OPEN_OFFERS and r.scanned["excluded"]["table full"] == 3
    picks.rows[0].expiresAt = NOW() - timedelta(seconds=1)  # a free slot: the next waiting opportunity moves in
    r = run(svc.tick(FakeDb(), 7))
    assert len(r.picks) == sz.MAX_OPEN_OFFERS


def test_only_this_sessions_underlyings_and_no_candidates_waits():
    svc, _, _ = make([opp(1, underlyingCode="BANKNIFTY")])
    r = run(svc.tick(FakeDb(), 7))
    assert r.state == "WAITING" and r.picks == [] and r.scanned["candidates"] == 0


@pytest.mark.parametrize("patch,state", [
    ({"sessionType": "SEMI_AUTO"}, "UNSUPPORTED_TYPE"),
    ({"sessionType": "FULL_AUTO"}, "UNSUPPORTED_TYPE"),
    ({"sessionStatus": "CLOSED"}, "SESSION_CLOSED"),
    ({"tradeDate": "2020-01-01"}, "SESSION_CLOSED"),
    ({"realizedPnl": -3000}, "HALTED"),
])
def test_session_gates(patch, state):
    svc, s, _ = make(**patch)
    r = run(svc.tick(FakeDb(), 7))
    assert r.state == state and r.picks == []
    if state == "HALTED":
        assert s.haltReason == "MAX_LOSS" and s.haltedAt is not None


# ───────────────────────── trade lock ─────────────────────────
def test_locking_one_row_refits_the_other_open_rows_to_the_money_left():
    svc, _, picks = make([opp(1, confidence=90), opp(2, confidence=70)])
    r0 = run(svc.tick(FakeDb(), 7))
    first, second = r0.picks
    assert first.opportunityId == 1 and second.lots > 1
    locked = run(svc.lock(FakeDb(), 7, first.id))
    assert locked.pickState == "LOCKED" and locked.lockedAt is not None and locked.secondsLeft == 0
    assert locked.lockedPrice == 101.5  # the item's current price at the moment of the lock
    assert run(svc.lock(FakeDb(), 7, first.id)).pickState == "LOCKED"  # idempotent
    r = run(svc.tick(FakeDb(), 7))
    assert r.capital.lockedTrades == 1 and r.capital.committedPremium == first.capitalRequired
    assert r.capital.availableCapital == 100000 - first.capitalRequired
    assert r.capital.remainingLossBudget == 3000 - first.riskAmount
    assert [p.opportunityId for p in r.picks] == [2]  # the locked row left the table; the other stays open
    refit = r.picks[0]
    assert refit.lots < second.lots and refit.capitalRequired <= r.capital.availableCapital
    assert refit.riskAmount <= r.capital.remainingLossBudget and refit.id == second.id


def test_a_row_that_no_longer_fits_after_another_lock_drops_off():
    svc, _, picks = make([opp(1, confidence=100), opp(2, confidence=100)])
    a, b = run(svc.tick(FakeDb(), 7)).picks
    run(svc.lock(FakeDb(), 7, a.id))  # 100% sure: takes (nearly) all the loss budget / cash
    r = run(svc.tick(FakeDb(), 7))
    still = [p for p in r.picks if p.id == b.id]
    assert all(p.riskAmount <= r.capital.remainingLossBudget for p in still)
    if not still:
        assert next(x for x in picks.rows if x.id == b.id).pickState == "EXPIRED"


def test_lock_after_the_opportunity_expired_is_rejected():
    svc, _, picks = make()
    p = run(svc.tick(FakeDb(), 7)).picks[0]
    picks.rows[0].expiresAt = NOW() - timedelta(milliseconds=1)
    with pytest.raises(ConflictException) as e:
        run(svc.lock(FakeDb(), 7, p.id))
    assert e.value.error["code"] == "PICK_EXPIRED" and picks.rows[0].pickState == "OFFERED"
    r = run(svc.tick(FakeDb(), 7))  # the tick sweeps it
    assert picks.rows[0].pickState == "EXPIRED" and r.state == "WAITING"
    with pytest.raises(ConflictException) as e2:
        run(svc.lock(FakeDb(), 7, p.id))
    assert e2.value.error["code"] == "PICK_NOT_OFFERED"


def test_lock_survives_a_missing_live_price():
    svc, _, picks = make()
    svc.opportunities.price = None
    p = run(svc.tick(FakeDb(), 7)).picks[0]
    locked = run(svc.lock(FakeDb(), 7, p.id))
    assert locked.pickState == "LOCKED" and locked.lockedPrice is None


def test_no_trade_limit_loss_budget_is_the_only_stop():
    # 12 minimum-size (50% sure) picks, all one strategy: no 6-per-session or 2-per-strategy cap any more
    svc, _, _ = make([opp(i, confidence=50) for i in range(1, 30)])
    for _ in range(12):
        r = run(svc.tick(FakeDb(), 7))
        assert r.state == "PICK_READY"
        pk = r.picks[0]
        assert pk.lots == 1
        run(svc.lock(FakeDb(), 7, pk.id))
    r = run(svc.tick(FakeDb(), 7))
    assert r.capital.lockedTrades == 12 and r.state == "PICK_READY"  # 12 x 227.5 = 2730 of 3000 used
    run(svc.lock(FakeDb(), 7, r.picks[0].id))  # 13th: 2957.5 used
    r = run(svc.tick(FakeDb(), 7))  # 42.5 left: not even one lot -> only now does the money stop it
    assert r.state == "WAITING" and r.picks == [] and r.capital.remainingLossBudget == 42.5
    assert "loss budget below 1 lot" in r.scanned["excluded"]


def test_only_opportunities_from_the_last_30_seconds_are_read():
    svc, _, _ = make()
    run(svc.tick(FakeDb(), 7))
    assert svc.opportunities.max_age == 30 == sz.MAX_OPPORTUNITY_AGE_SECONDS


def test_lock_rechecks_capital():
    svc2, s2, picks2 = make([opp(1), opp(2)])
    # a pick offered earlier cannot be locked once the budget has been used up by other locks
    first = run(svc2.tick(FakeDb(), 7)).picks[0]
    picks2.rows.append(SessionPick(
        id=99, sessionId=7, opportunityId=500, pickState="LOCKED", capitalRequired=99000, riskAmount=100,
        underlyingCode="NIFTY", strategy="X"))
    with pytest.raises(ConflictException) as e:
        run(svc2.lock(FakeDb(), 7, first.id))
    assert e.value.error["code"] == "INSUFFICIENT_CAPITAL"


# ───────────────────────── trading hours ─────────────────────────
from app.modules.sessions.service import session_hours as hrs  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
D = "2026-11-05"


def ist(h, m, d=D):
    return datetime.fromisoformat(f"{d}T{h:02d}:{m:02d}:30").replace(tzinfo=_IST)


def test_default_start_is_now_from_0925_else_0915_and_close_is_1545():
    for now, want in [(ist(9, 24), "09:15"), (ist(8, 0), "09:15"), (ist(9, 25), "09:25"), (ist(11, 42), "11:42")]:
        start, close = hrs.resolve(D, None, None, now)
        assert start.astimezone(_IST).strftime("%H:%M") == want
        assert close.astimezone(_IST).strftime("%H:%M") == "15:45"
    # a session for another day always starts at the open
    assert hrs.default_start("2026-11-06", ist(11, 42)).astimezone(_IST).strftime("%H:%M") == "09:15"


def test_commodity_session_closes_at_2300_by_default():
    start, close = hrs.resolve(D, None, None, ist(9, 10), scope="COMMODITY")
    assert close.astimezone(_IST).strftime("%H:%M") == "23:00"
    _, idx_close = hrs.resolve(D, None, None, ist(9, 10), scope="INDEX")
    assert idx_close.astimezone(_IST).strftime("%H:%M") == "15:45"
    _, explicit = hrs.resolve(D, None, "21:30", ist(9, 10), scope="COMMODITY")
    assert explicit.astimezone(_IST).strftime("%H:%M") == "21:30"


def test_explicit_times_win_and_close_must_follow_start():
    start, close = hrs.resolve(D, "10:00", "14:30", ist(11, 0))
    assert (start.astimezone(_IST).strftime("%H:%M"), close.astimezone(_IST).strftime("%H:%M")) == ("10:00", "14:30")
    with pytest.raises(ValueError):
        hrs.resolve(D, "15:00", "14:00")
    with pytest.raises(ValueError):
        hrs.parse_hhmm("9:5")


def test_tick_waits_before_the_start_time_then_offers():
    svc, s, picks = make(startAt=NOW() + timedelta(minutes=30), closeAt=NOW() + timedelta(hours=5))
    r = run(svc.tick(FakeDb(), 7))
    assert r.state == "SCHEDULED" and r.picks == [] and picks.rows == [] and s.sessionStatus == "ACTIVE"
    s.startAt = NOW() - timedelta(seconds=1)
    assert run(svc.tick(FakeDb(), 7)).state == "PICK_READY"


def test_tick_closes_the_session_at_the_close_time_and_expires_open_offers():
    svc, s, picks = make(startAt=NOW() - timedelta(hours=1), closeAt=NOW() + timedelta(hours=1))
    assert run(svc.tick(FakeDb(), 7)).state == "PICK_READY" and picks.rows[0].pickState == "OFFERED"
    s.closeAt = NOW() - timedelta(seconds=1)
    r = run(svc.tick(FakeDb(), 7))
    assert r.state == "SESSION_CLOSED" and s.sessionStatus == "CLOSED" and s.closedAt is not None
    assert picks.rows[0].pickState == "EXPIRED"


def test_lock_is_refused_after_the_close_time():
    svc, s, picks = make(startAt=NOW() - timedelta(hours=1), closeAt=NOW() + timedelta(hours=1))
    p = run(svc.tick(FakeDb(), 7)).picks[0]
    s.closeAt = NOW() - timedelta(seconds=1)
    with pytest.raises(ConflictException) as e:
        run(svc.lock(FakeDb(), 7, p.id))
    assert e.value.error["code"] == "SESSION_HOURS_OVER"
