"""Server-side session loop runner: starts from create, ticks on its own, serves a snapshot, stops cleanly."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import NotFoundException
from app.modules.sessions.engine.session_loop_runner import SessionLoopRunner
from app.modules.sessions.entity.trading_session_entity import TradingSession
from app.modules.sessions.schema.session_pick_schema import SessionCapitalResponse, SessionLoopResponse, SessionPickResponse
from app.modules.sessions.service.session_loop_service import SessionLoopService
from app.modules.sessions.service.trading_session_service import TradingSessionService
from tests.test_session_loop import TODAY, FakeDb

CAP = SessionCapitalResponse(capital=1, realizedPnl=0, currentCapital=1, committedPremium=0, availableCapital=1,
                             maxLossAmount=1, lossUsed=0, committedRisk=0, remainingLossBudget=1, lockedTrades=0)


class CountingDb(FakeDb):
    async def commit(self):
        self.committed = True


@asynccontextmanager
async def fake_factory():
    yield CountingDb()


def pick(expires_in: float) -> SessionPickResponse:
    now = datetime.now(UTC)
    return SessionPickResponse.model_construct(
        id=1, sessionId=1, pickState="OFFERED", expiresAt=now + timedelta(seconds=expires_in), secondsLeft=expires_in)


class FakeService:
    def __init__(self, states, pick_resp=None):
        self.states, self.calls, self.pick_resp = list(states), 0, pick_resp

    async def tick(self, db, sid):
        self.calls += 1
        if self.states[0] == "GONE":
            raise NotFoundException(message="gone")
        state = self.states[0] if len(self.states) == 1 else self.states.pop(0)
        return SessionLoopResponse(sessionId=sid, serverTime=datetime.now(UTC), state=state, message=state,
                                   picks=[self.pick_resp] if self.pick_resp else [], capital=CAP, scanned={})


def sess(**kw) -> TradingSession:
    s = TradingSession(name="t", tradeDate=TODAY(), userId=1, capital=1, maxLossPercentage=1, scope="INDEX",
                       underlyings=["NIFTY"], commodityItems=[], sessionType="MANUAL", routeThroughUpstox=False,
                       sessionStatus="ACTIVE", startAt=datetime.now(UTC) - timedelta(hours=1),
                       closeAt=datetime.now(UTC) + timedelta(hours=1))
    s.id, s.status = 3, EntityStatus.ACTIVE
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_eligibility():
    assert SessionLoopRunner.eligible(sess())
    assert not SessionLoopRunner.eligible(sess(sessionType="FULL_AUTO"))
    assert not SessionLoopRunner.eligible(sess(sessionStatus="CLOSED"))
    assert not SessionLoopRunner.eligible(sess(tradeDate="2020-01-01"))


def test_loop_ticks_by_itself_and_serves_a_live_countdown_snapshot():
    async def go():
        svc = FakeService(["PICK_READY"], pick(20))
        r = SessionLoopRunner(svc, fake_factory, tick_seconds=0.01)
        r.sync(sess())  # what the create-session API does
        assert r.is_running(3)
        await asyncio.sleep(0.1)
        assert svc.calls >= 3
        snap = r.snapshot(3)
        assert snap.state == "PICK_READY" and snap.picks[0].pickState == "OFFERED" and 0 < snap.picks[0].secondsLeft <= 20
        r.stop(3)
        await asyncio.sleep(0.02)
        assert not r.is_running(3) and r.snapshot(3) is None
    asyncio.run(go())


def test_snapshot_marks_an_unswept_offer_expired():
    async def go():
        r = SessionLoopRunner(FakeService(["PICK_READY"], pick(-1)), fake_factory, tick_seconds=0.01)
        r.start(3)
        await asyncio.sleep(0.05)
        assert r.snapshot(3).picks[0].pickState == "EXPIRED" and r.snapshot(3).picks[0].secondsLeft == 0
        await r.stop_all()
    asyncio.run(go())


def test_loop_ends_on_closed_session_or_deleted_row_and_sync_stops_ineligible():
    async def go():
        r = SessionLoopRunner(FakeService(["SESSION_CLOSED"]), fake_factory, tick_seconds=0.01)
        r.start(3)
        await asyncio.sleep(0.05)
        assert not r.is_running(3)
        r2 = SessionLoopRunner(FakeService(["GONE"]), fake_factory, tick_seconds=0.01)
        r2.start(4)
        await asyncio.sleep(0.05)
        assert not r2.is_running(4) and r2.snapshot(4) is None
        r3 = SessionLoopRunner(FakeService(["WAITING"]), fake_factory, tick_seconds=0.01)
        r3.sync(sess())
        assert r3.is_running(3)
        r3.sync(sess(sessionStatus="CLOSED"))
        await asyncio.sleep(0.02)
        assert not r3.is_running(3)
    asyncio.run(go())


def test_create_session_starts_the_loop_and_close_stops_it(monkeypatch):
    from app.modules.sessions import engine as engine_pkg
    from app.modules.sessions.schema.trading_session_schema import TradingSessionCreateRequest, TradingSessionUpdateRequest

    class Repo:
        async def save(self, db, e):
            e.id, e.status, e.createdAt = 11, EntityStatus.ACTIVE, datetime.now(UTC)
            return e

        async def get_by_id(self, db, sid):
            return self.row

    async def go():
        runner = SessionLoopRunner(FakeService(["WAITING"]), fake_factory, tick_seconds=0.01)
        monkeypatch.setattr(engine_pkg, "session_loop_runner", runner)
        repo = Repo()
        svc = TradingSessionService(repo)
        out = await svc.create(CountingDb(), TradingSessionCreateRequest(
            tradeDate=TODAY(), userId=1, capital=100000, maxLossPercentage=3, scope="INDEX", underlyings=["NIFTY"],
            sessionType="MANUAL", startTime="00:00", closeTime="23:59"))  # fixed hours: independent of the clock
        assert runner.is_running(out.id)
        await asyncio.sleep(0.05)
        repo.row = sess(id=out.id, createdAt=datetime.now(UTC))
        got = await svc.get_by_id(CountingDb(), out.id)
        assert got.loop is not None and got.loop.state == "WAITING"
        await svc.update(CountingDb(), out.id, TradingSessionUpdateRequest(sessionStatus="CLOSED"))
        await asyncio.sleep(0.02)
        assert not runner.is_running(out.id)
    asyncio.run(go())


def test_sse_subscribers_get_a_push_only_when_something_visible_changes():
    async def go():
        svc = FakeService(["WAITING"])
        r = SessionLoopRunner(svc, fake_factory, tick_seconds=0.01)
        q = r.subscribe(3)
        r.start(3)
        await asyncio.sleep(0.1)
        assert svc.calls >= 5 and q.qsize() == 1  # many identical ticks -> a single push
        first = q.get_nowait()
        assert first.state == "WAITING"
        svc.states = ["PICK_READY"]
        svc.pick_resp = pick(20)
        await asyncio.sleep(0.05)
        assert q.qsize() == 1 and q.get_nowait().state == "PICK_READY"
        r.stop(3)  # a stopped loop tells its clients (None) so the stream can end
        assert q.get_nowait() is None
        r.unsubscribe(3, q)
        assert 3 not in r._subs
    asyncio.run(go())


def test_sse_endpoint_streams_snapshot_then_updates_then_closed():
    from app.modules.sessions.controller import session_pick_controller as ctl
    from app.modules.sessions.engine import session_loop_runner as shared

    async def go():
        svc = FakeService(["WAITING"])
        runner = SessionLoopRunner(svc, fake_factory, tick_seconds=0.01)
        ctl.session_loop_runner = runner
        try:
            runner.start(3)
            await asyncio.sleep(0.05)
            gen = ctl._loop_events(3)
            first = await gen.__anext__()
            assert first.startswith("event: loop\ndata: ") and '"state":"WAITING"' in first
            svc.states = ["PICK_READY"]
            svc.pick_resp = pick(20)
            second = await asyncio.wait_for(gen.__anext__(), 1)
            assert '"state":"PICK_READY"' in second and "secondsLeft" in second
            runner.stop(3)
            assert (await asyncio.wait_for(gen.__anext__(), 1)).startswith("event: closed")
            await gen.aclose()
            assert 3 not in runner._subs
            # a session with no loop answers `closed` straight away instead of hanging
            idle = ctl._loop_events(99)
            assert (await idle.__anext__()).startswith("event: closed")
        finally:
            ctl.session_loop_runner = shared
    asyncio.run(go())
