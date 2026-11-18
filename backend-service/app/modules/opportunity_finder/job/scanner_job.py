"""
Backend-driven opportunity scanning (18 Nov 2026).

Before: scanners started only when someone opened a session page, and only a browser tab iterated them. On every day
of 11-18 Nov the first NIFTY scan came at 09:42 or later, so FII_OPEN_DRIVE (entries 09:20-09:35; the system's best
setup in the replays) never fired live, and nothing was scanned while no tab was open.

Now, every LOOP_SECONDS (APScheduler interval job, one run at a time):
  1. auto-start  weekdays from 09:14 IST until the index close: if no INDEX scanner exists for today, start one for every
                 Research card (all indices, plus the Research commodities). A day on which the user already started
                 or STOPPED scanners is left alone -- Stop stays stopped.
  2. iterate     every RUNNING master of today whose market is open, one by one (the same iterate() the API runs; a
                 card a browser tab is iterating right now answers 409 and is skipped this round).
The browser loop (frontend opportunityLoopRunner) sees `backendLoop` in /masters/today and only refreshes the page.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.triggers.interval import IntervalTrigger

from app.core.config.settings import settings
from app.core.db.session import async_session_factory
from app.core.exception.app_exceptions import ConflictException
from app.core.logging.logger import logger
from app.core.scheduler.scheduler import get_scheduler
from app.modules.opportunity_finder.provider.underlying_config import get_config, is_market_open
from app.modules.opportunity_finder.repository.opportunity_repository import opportunity_master_repository as repo
from app.modules.opportunity_finder.schema.opportunity_schema import StartOpportunityRequest

_IST = ZoneInfo("Asia/Kolkata")
JOB_ID = "opportunities.scanner_loop"
LOOP_SECONDS = 20
AUTO_START_FROM = "09:14"  # one minute before the open: the first scan lands on the 09:15 bar
AUTO_START_UNTIL = "15:10"  # no new index entries after this anyway
_state = {"lastNote": None}


def _note(msg: str) -> None:
    if _state["lastNote"] != msg:  # log a repeated condition once, not every 20 seconds
        _state["lastNote"] = msg
        logger.info(f"[SCANNER_LOOP] {msg}")


def should_auto_start(now: datetime, index_masters_today: int) -> bool:
    hhmm = now.strftime("%H:%M")
    return now.weekday() < 5 and AUTO_START_FROM <= hhmm < AUTO_START_UNTIL and index_masters_today == 0


async def tick(now: datetime | None = None) -> dict[str, int]:
    from app.modules.opportunity_finder.service.run_service import _today, opportunity_run_service as svc

    now = (now or datetime.now(_IST)).astimezone(_IST)
    today = _today()
    async with async_session_factory() as s:
        masters = await repo.latest_for_day(s, today)
        index_today = sum(1 for m in masters.values() if m.underlyingType == "INDEX")
        if should_auto_start(now, index_today):
            res = await svc.start(StartOpportunityRequest(indexCount=6), s)
            if res.get("started"):
                logger.info(f"[SCANNER_LOOP] auto-started {len(res.get('masters') or [])} scanner(s) at "
                            f"{now:%H:%M} IST")
            else:
                _note(f"auto-start waiting: {res.get('message') or res.get('reason')}")
            masters = await repo.latest_for_day(s, today)
        running = [(m.id, m.underlyingCode) for m in masters.values() if m.state == "RUNNING"]
    done = skipped = 0
    for mid, code in running:
        cfg = get_config(code)
        if cfg is None or not is_market_open(cfg):
            continue
        try:
            await svc.iterate(mid)
            done += 1
        except ConflictException:
            skipped += 1  # a browser tab is iterating this card right now
        except Exception as e:  # noqa: BLE001 -- one card failing must not stop the others
            logger.warning(f"[SCANNER_LOOP] {code} iterate failed: {type(e).__name__}: {e}")
    return {"iterated": done, "skipped": skipped, "running": len(running)}


async def _run() -> None:
    try:
        await tick()
    except Exception as e:  # noqa: BLE001 -- e.g. the database restarting; the next tick retries
        logger.error(f"[SCANNER_LOOP] tick failed: {type(e).__name__}: {e}")


def register_scanner_job() -> None:
    if not settings.OPPORTUNITY_BACKEND_LOOP:
        logger.info("[SCANNER_LOOP] off (OPPORTUNITY_BACKEND_LOOP=false): scanners run from the browser only")
        return
    get_scheduler().add_job(_run, IntervalTrigger(seconds=LOOP_SECONDS, timezone=_IST), id=JOB_ID,
                            replace_existing=True, coalesce=True, max_instances=1, misfire_grace_time=LOOP_SECONDS)
    logger.info(f"Registered backend scanner loop (every {LOOP_SECONDS}s; auto-start {AUTO_START_FROM} IST on weekdays).")
