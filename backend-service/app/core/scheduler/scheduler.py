try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config.settings import settings

logger = logging.getLogger("auto-trader.scheduler")

# Single process APScheduler with Asia/Kolkata timezone
tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
scheduler = AsyncIOScheduler(timezone=tz)


def start_scheduler() -> None:
    """Starts the background APScheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info(f"APScheduler started with timezone {settings.SCHEDULER_TIMEZONE}")


def shutdown_scheduler() -> None:
    """Shuts down the APScheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")


def get_scheduler() -> AsyncIOScheduler:
    """Returns the scheduler instance."""
    return scheduler
