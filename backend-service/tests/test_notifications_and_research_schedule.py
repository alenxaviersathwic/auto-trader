"""Notifications (event bus -> hub -> stream) and the automatic research schedule. No DB, no network."""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.events import notify as nt
from app.core.events.event_bus import EventBus
from app.modules.notifications.schema.notification_schema import NotificationSearchFilter
from app.modules.notifications.service.notification_hub import NotificationHub
from app.modules.research.job import research_schedule_job as job
from app.modules.system.service.system_load import usage_pct

IST = ZoneInfo("Asia/Kolkata")


def test_notify_reaches_every_open_stream_through_the_event_bus(monkeypatch):
    bus, hub = EventBus(), NotificationHub()
    monkeypatch.setattr(nt, "event_bus", bus)
    import importlib

    monkeypatch.setattr(importlib.import_module("app.modules.notifications.service.notification_hub"), "event_bus", bus)
    hub.register()
    hub.register()  # idempotent: one subscription
    q1, q2 = hub.subscribe(), hub.subscribe()

    async def go():
        await nt.notify(nt.TRADE_EXITED, "Trade closed", "target hit", severity="success", session_id=7, trade_id=3,
                        link="/trades/3")
        await nt.notify(nt.NEW_SUGGESTION, "2 new setups", "best: NIFTY", session_id=8)

    asyncio.run(go())
    a, b = q1.get_nowait(), q1.get_nowait()
    assert (a.id, a.kind, a.tradeId, a.link) == (1, "TRADE_EXITED", 3, "/trades/3") and b.id == 2
    assert q2.qsize() == 2
    assert [n.id for n in hub.since(1)] == [2]
    page = hub.search(NotificationSearchFilter(page=0, limit=10, sessionId=7))
    assert page.totalItems == 1 and page.list[0].title == "Trade closed"
    hub.unsubscribe(q1)
    hub.publish({"kind": "RESEARCH", "title": "t", "body": "b", "severity": "info"})
    assert q1.qsize() == 0 and q2.qsize() == 3


def test_a_stalled_stream_never_blocks_producers():
    hub = NotificationHub()
    q = hub.subscribe()
    for i in range(250):
        hub.publish({"kind": "RESEARCH", "title": str(i), "body": "", "severity": "info"})
    assert q.qsize() == 200 and q.get_nowait().title == "50"  # oldest dropped, newest kept


def test_notify_never_raises(monkeypatch):
    class Broken:
        async def publish(self, *a):
            raise RuntimeError("bus down")

    monkeypatch.setattr(nt, "event_bus", Broken())
    asyncio.run(nt.notify(nt.TRADE_LOCKED, "x", "y"))


# ───────────────────────── system load + research schedule ─────────────────────────
def test_usage_is_the_busier_of_cpu_and_app_load():
    assert usage_pct(2.0, 8, 3, 12) == {"cpuPct": 25.0, "appPct": 25.0, "usagePct": 25.0}
    assert usage_pct(0.4, 8, 9, 12)["usagePct"] == 75.0  # quiet CPU, but 9 loops / trades running
    assert usage_pct(12.0, 8, 0, 12)["usagePct"] == 100.0  # capped
    assert usage_pct(None, None, 6, 12) == {"cpuPct": None, "appPct": 50.0, "usagePct": 50.0}


def test_research_runs_only_when_idle_enough_and_in_hours(monkeypatch):
    monkeypatch.setattr(job.settings, "RESEARCH_AUTO_ENABLED", True)
    monkeypatch.setattr(job.settings, "RESEARCH_AUTO_MAX_LOAD_PCT", 50.0)
    monkeypatch.setattr(job.settings, "RESEARCH_AUTO_WINDOW", "07:00-23:30")
    day = datetime(2026, 11, 17, 10, 0, tzinfo=IST)
    calm = {"usagePct": 20.0, "cpuPct": 20.0, "appPct": 8.0}
    busy = {"usagePct": 75.0, "cpuPct": 10.0, "appPct": 75.0}
    assert job.decide(day, calm, False)[0]
    ok, why = job.decide(day, busy, False)
    assert not ok and "system busy: 75% used" in why
    assert job.decide(day, {**calm, "usagePct": 50.0}, False)[0] is False  # at the limit is busy
    assert "already in progress" in job.decide(day, calm, True)[1]
    assert "outside" in job.decide(datetime(2026, 11, 17, 3, 0, tzinfo=IST), calm, False)[1]
    monkeypatch.setattr(job.settings, "RESEARCH_AUTO_ENABLED", False)
    assert "switched off" in job.decide(day, calm, False)[1]


def test_schedule_registers_startup_and_interval_jobs(monkeypatch):
    added = []

    class Sch:
        def add_job(self, fn, trigger, **kw):
            added.append((trigger, kw["id"], kw.get("minutes")))

    monkeypatch.setattr(job, "get_scheduler", lambda: Sch())
    job.register_research_schedule()
    assert ("interval", job.JOB_ID, job.settings.RESEARCH_AUTO_INTERVAL_MIN) in added
    assert any(t == "date" and i == job.STARTUP_JOB_ID for t, i, _ in added)
