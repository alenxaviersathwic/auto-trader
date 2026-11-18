"""Backend scanner loop (18 Nov 2026): starts the index scanners at 09:14 IST so the 09:20-09:35 FII_OPEN_DRIVE window
is covered, iterates RUNNING cards whose market is open, and never restarts a day the user stopped."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.core.exception.app_exceptions import ConflictException
from app.modules.opportunity_finder.job import scanner_job as sj

IST = ZoneInfo("Asia/Kolkata")
WED_0914 = datetime(2026, 11, 18, 9, 14, tzinfo=IST)


def test_auto_start_window():
    assert sj.should_auto_start(WED_0914, 0)
    assert not sj.should_auto_start(WED_0914.replace(hour=9, minute=13), 0)  # before 09:14
    assert not sj.should_auto_start(WED_0914.replace(hour=15, minute=10), 0)  # after the last entry time
    assert not sj.should_auto_start(datetime(2026, 11, 21, 10, 0, tzinfo=IST), 0)  # Saturday
    assert not sj.should_auto_start(WED_0914, 5)  # scanners already exist today (running or stopped)


def _wire(monkeypatch, masters: dict, started: list, iterated: list, busy: set):
    import app.modules.opportunity_finder.service.run_service as rs

    @asynccontextmanager
    async def session():
        yield None

    async def latest_for_day(_s, _d):
        return dict(masters)

    async def start(req, _s):
        started.append(req.indexCount)
        masters["NIFTY"] = SimpleNamespace(id=1, underlyingCode="NIFTY", underlyingType="INDEX", state="RUNNING")
        masters["SENSEX"] = SimpleNamespace(id=2, underlyingCode="SENSEX", underlyingType="INDEX", state="RUNNING")
        return {"started": True, "masters": [1, 2]}

    async def iterate(mid):
        if mid in busy:
            raise ConflictException("busy")
        iterated.append(mid)

    monkeypatch.setattr(sj, "async_session_factory", session)
    monkeypatch.setattr(sj.repo, "latest_for_day", latest_for_day)
    monkeypatch.setattr(rs.opportunity_run_service, "start", start)
    monkeypatch.setattr(rs.opportunity_run_service, "iterate", iterate)
    monkeypatch.setattr(sj, "is_market_open", lambda cfg: True)


def test_tick_starts_all_indices_then_iterates(monkeypatch):
    masters, started, iterated = {}, [], []
    _wire(monkeypatch, masters, started, iterated, busy={2})
    out = asyncio.run(sj.tick(WED_0914))
    assert started == [6]  # every index in Research, not only one session's
    assert iterated == [1] and out == {"iterated": 1, "skipped": 1, "running": 2}  # card 2 busy in a tab: skipped


def test_stopped_day_is_not_restarted(monkeypatch):
    masters = {"NIFTY": SimpleNamespace(id=1, underlyingCode="NIFTY", underlyingType="INDEX", state="STOPPED")}
    started, iterated = [], []
    _wire(monkeypatch, masters, started, iterated, busy=set())
    out = asyncio.run(sj.tick(WED_0914.replace(hour=10)))
    assert started == [] and iterated == [] and out["running"] == 0


def test_closed_market_is_not_iterated(monkeypatch):
    masters = {"GOLD": SimpleNamespace(id=9, underlyingCode="GOLD", underlyingType="COMMODITY", state="RUNNING"),
               "NIFTY": SimpleNamespace(id=1, underlyingCode="NIFTY", underlyingType="INDEX", state="RUNNING")}
    started, iterated = [], []
    _wire(monkeypatch, masters, started, iterated, busy=set())
    monkeypatch.setattr(sj, "is_market_open", lambda cfg: cfg.exchange == "MCX")  # evening: only MCX trades
    asyncio.run(sj.tick(WED_0914.replace(hour=18)))
    assert iterated == [9]
