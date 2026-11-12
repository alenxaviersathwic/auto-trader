"""Scheduled real-option-price downloads (research gap 2): Upstox keeps 1-minute history for about a month, so it
has to be collected continuously or it is gone.
  daily   Mon-Fri 16:05 IST  fetch_day(today)      -- after the 15:40 NSE close; holidays just write nothing
  weekly  Saturday 10:15 IST backfill_expired(4)  -- needs Upstox Plus; logs and moves on without it"""
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.core.logging.logger import logger
from app.core.scheduler.scheduler import get_scheduler
from app.modules.backtest.service import option_history_service as ohs

_IST = ZoneInfo("Asia/Kolkata")
DAILY_JOB_ID = "backtest.option_history.daily"
WEEKLY_JOB_ID = "backtest.option_history.expired"


async def _daily() -> None:
    try:
        logger.info(f"[OPTION_HISTORY] daily fetch: {await ohs.fetch_day()}")
    except Exception as e:  # noqa: BLE001 -- e.g. no Upstox login today
        logger.error(f"[OPTION_HISTORY] daily fetch failed: {type(e).__name__}: {e}")


async def _weekly() -> None:
    try:
        logger.info(f"[OPTION_HISTORY] expired backfill: {await ohs.backfill_expired()}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[OPTION_HISTORY] expired backfill failed: {type(e).__name__}: {e}")


def register_option_history_jobs() -> None:
    s = get_scheduler()
    s.add_job(_daily, CronTrigger(day_of_week="mon-fri", hour=16, minute=5, timezone=_IST), id=DAILY_JOB_ID,
              replace_existing=True, coalesce=True, max_instances=1, misfire_grace_time=6 * 3600)
    s.add_job(_weekly, CronTrigger(day_of_week="sat", hour=10, minute=15, timezone=_IST), id=WEEKLY_JOB_ID,
              replace_existing=True, coalesce=True, max_instances=1, misfire_grace_time=24 * 3600)
    logger.info("Registered option history jobs (Mon-Fri 16:05 IST daily, Sat 10:15 IST expired backfill).")
