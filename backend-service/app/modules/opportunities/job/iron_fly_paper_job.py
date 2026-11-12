"""Every minute 09:45-15:00 IST, Mon-Fri: paper-trade the expiry-day iron fly on live quotes (never sends orders)."""
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.core.logging.logger import logger
from app.core.scheduler.scheduler import get_scheduler
from app.modules.opportunities.service import iron_fly_paper

_IST = ZoneInfo("Asia/Kolkata")
JOB_ID = "opportunities.iron_fly_paper"


async def _run() -> None:
    try:
        await iron_fly_paper.tick()
    except Exception as e:  # noqa: BLE001
        logger.error(f"[IRON_FLY_PAPER] tick failed: {type(e).__name__}: {e}")


def register_iron_fly_paper_job() -> None:
    get_scheduler().add_job(
        _run, CronTrigger(day_of_week="mon-fri", hour="9-14", minute="*", second=30, timezone=_IST), id=JOB_ID,
        replace_existing=True, coalesce=True, max_instances=1, misfire_grace_time=30,
    )
    logger.info("Registered iron fly PAPER job (every minute 09:00-14:59 IST, Mon-Fri; entries only 09:45-10:45).")
