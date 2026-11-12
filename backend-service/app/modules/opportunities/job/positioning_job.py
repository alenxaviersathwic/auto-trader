"""Mon-Fri 19:30 IST (+ 08:50 catch-up, + once at boot): save NSE participant-wise OI for the day (plus any missed days of the last week)."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.core.logging.logger import logger
from app.core.scheduler.scheduler import get_scheduler
from app.modules.opportunities.service import positioning

_IST = ZoneInfo("Asia/Kolkata")
JOB_ID = "opportunities.participant_oi"


async def fetch_recent(days: int = 7) -> int:
    today = datetime.now(_IST).date()
    got = 0
    for i in range(days, -1, -1):
        d: date = today - timedelta(days=i)
        if d.weekday() < 5 and await positioning.fetch(d):
            got += 1
    return got


async def _run() -> None:
    try:
        n = await fetch_recent()
        logger.info(f"[POSITIONING] participant OI files available for {n} recent day(s); state {positioning.snapshot()}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[POSITIONING] job failed: {type(e).__name__}: {e}")


def register_positioning_job() -> None:
    get_scheduler().add_job(_run, CronTrigger(day_of_week="mon-fri", hour=19, minute=30, timezone=_IST), id=JOB_ID,
                            replace_existing=True, coalesce=True, max_instances=1, misfire_grace_time=12 * 3600)
    # FII_OPEN_DRIVE reads yesterday's file at 09:20: catch up before the open and once at boot, in case the
    # backend was not running at 19:30 the evening before
    get_scheduler().add_job(_run, CronTrigger(day_of_week="mon-fri", hour=8, minute=50, timezone=_IST),
                            id=JOB_ID + ".morning", replace_existing=True, coalesce=True, max_instances=1,
                            misfire_grace_time=1800)
    get_scheduler().add_job(_run, id=JOB_ID + ".boot", replace_existing=True, max_instances=1)
    logger.info("Registered participant OI job (Mon-Fri 19:30 + 08:50 IST, and once at boot).")
