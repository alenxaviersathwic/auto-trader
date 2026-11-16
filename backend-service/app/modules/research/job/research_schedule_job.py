"""
Research Engine on its own: once shortly after start-up, then every RESEARCH_AUTO_INTERVAL_MIN minutes, but only
  * inside RESEARCH_AUTO_WINDOW (IST, default 07:00-23:30: covers pre-open through the MCX close)
  * when no research run is already active
  * when system usage (system/service/system_load.py) is below RESEARCH_AUTO_MAX_LOAD_PCT (default 50%), so a busy
    trading desk (many sessions, many running trades) never competes with a research run
A skipped turn is not retried early: the next interval tick checks again. The last decision is kept for
GET /research/schedule. A finished scheduled run raises a RESEARCH notification.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config.settings import settings
from app.core.db.session import async_session_factory
from app.core.events import notify as nt
from app.core.logging.logger import logger
from app.core.scheduler.scheduler import get_scheduler

_IST = ZoneInfo("Asia/Kolkata")
JOB_ID, STARTUP_JOB_ID = "research-auto", "research-auto-startup"
_last: dict[str, Any] = {"at": None, "trigger": None, "ran": False, "reason": "not checked yet"}


def _in_window(now: datetime, window: str) -> bool:
    try:
        start, end = (x.strip() for x in window.split("-"))
        hm = now.strftime("%H:%M")
        return start <= hm <= end
    except ValueError:
        return True  # a malformed window never blocks research


def decide(now: datetime, usage: dict[str, Any], active_run: bool) -> tuple[bool, str]:
    """(run?, why). Pure: the job feeds it the clock, the load snapshot and whether a run is active."""
    if not settings.RESEARCH_AUTO_ENABLED:
        return False, "automatic research is switched off (RESEARCH_AUTO_ENABLED)"
    if not _in_window(now, settings.RESEARCH_AUTO_WINDOW):
        return False, f"outside {settings.RESEARCH_AUTO_WINDOW} IST"
    if active_run:
        return False, "a research run is already in progress"
    limit = settings.RESEARCH_AUTO_MAX_LOAD_PCT
    if usage["usagePct"] >= limit:
        return False, (f"system busy: {usage['usagePct']:.0f}% used (CPU {usage['cpuPct']}%, app {usage['appPct']:.0f}%) "
                       f">= {limit:g}%")
    return True, f"system at {usage['usagePct']:.0f}% (< {limit:g}%)"


async def _notify_when_done(run_id: int, task: asyncio.Task | None) -> None:
    if task is None:
        return
    try:
        await task
    except BaseException:  # noqa: BLE001 -- cancelled or failed: the run row records why
        pass
    from app.modules.research.service.run_service import run_service

    async with async_session_factory() as s:
        st = await run_service.get_current_status(s)
    state = (st or {}).get("state", "DONE")
    await nt.notify(nt.RESEARCH, f"Research run #{run_id} {str(state).lower()}",
                    "Scheduled research refreshed the underlyings the scanners work from.",
                    severity="info" if state == "COMPLETED" else "warning", link="/research")


async def run_if_idle(trigger: str = "INTERVAL") -> dict[str, Any]:
    from app.modules.research.service.run_service import run_service
    from app.modules.system.service.system_load import snapshot

    now = datetime.now(_IST)
    usage = snapshot()
    try:
        async with async_session_factory() as s:
            active = await run_service.get_active_run_id(s) is not None
            ok, why = decide(now, usage, active)
            run_id = None
            if ok:
                run_id = await run_service.start_run(scope=["INDEX", "COMMODITY"],
                                                     params={"windowHours": 24, "topN": 5},
                                                     trigger_source="SCHEDULER", session=s)
                asyncio.create_task(_notify_when_done(run_id, run_service._active_task))
    except Exception as e:  # noqa: BLE001
        ok, why, run_id = False, f"failed to start: {type(e).__name__}: {e}", None
    _last.update(at=now.isoformat(), trigger=trigger, ran=ok, reason=why, runId=run_id, usage=usage)
    logger.info(f"[RESEARCH_AUTO] {trigger}: {'started run #' + str(run_id) if ok else 'skipped'} -- {why}")
    return dict(_last)


def status() -> dict[str, Any]:
    job = get_scheduler().get_job(JOB_ID)
    nxt = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {"enabled": settings.RESEARCH_AUTO_ENABLED, "intervalMinutes": settings.RESEARCH_AUTO_INTERVAL_MIN,
            "maxLoadPct": settings.RESEARCH_AUTO_MAX_LOAD_PCT, "window": settings.RESEARCH_AUTO_WINDOW,
            "nextRunAt": nxt, "last": dict(_last)}


def register_research_schedule() -> None:
    """Start-up run after RESEARCH_AUTO_STARTUP_DELAY_S (the rest of start-up settles first) + the interval job."""
    sch = get_scheduler()
    sch.add_job(run_if_idle, "interval", minutes=settings.RESEARCH_AUTO_INTERVAL_MIN, id=JOB_ID,
                replace_existing=True, kwargs={"trigger": "INTERVAL"}, max_instances=1, coalesce=True)
    sch.add_job(run_if_idle, "date", run_date=datetime.now(_IST) + timedelta(seconds=settings.RESEARCH_AUTO_STARTUP_DELAY_S),
                id=STARTUP_JOB_ID, replace_existing=True, kwargs={"trigger": "STARTUP"})
