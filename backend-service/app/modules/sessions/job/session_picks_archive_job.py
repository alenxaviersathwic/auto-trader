from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.core.db.session import async_engine, async_session_factory
from app.core.logging.logger import logger
from app.core.scheduler.scheduler import get_scheduler
from app.modules.sessions.repository.session_pick_repository import SessionPickRepository

JOB_ID = "sessions.archive_session_picks"
_IST = ZoneInfo("Asia/Kolkata")
_repo = SessionPickRepository()


async def archive_finished_session_picks() -> dict[str, int]:
    """Move finished sessions' picks to session_picks_archive, then free the space of the live table."""
    now = datetime.now(UTC)
    async with async_session_factory() as db:
        result = await _repo.archive_finished(db, now.astimezone(_IST).date().isoformat(), now)
        await db.commit()
    if result["picksArchived"]:
        try:  # keeps the live table small and its statistics fresh; cannot run inside a transaction
            async with async_engine.connect() as conn:
                await conn.execution_options(isolation_level="AUTOCOMMIT")
                await conn.execute(text("VACUUM (ANALYZE) session_picks"))
        except Exception as e:  # noqa: BLE001 -- autovacuum will catch up
            logger.warning(f"[SESSION_PICKS_ARCHIVE] vacuum skipped: {type(e).__name__}: {e}")
    logger.info(f"[SESSION_PICKS_ARCHIVE] {result}")
    return result


async def _run() -> None:
    try:
        await archive_finished_session_picks()
    except Exception as ex:  # noqa: BLE001
        logger.error(f"[SESSION_PICKS_ARCHIVE] job failed: {ex}")


def register_archive_job() -> None:
    """Every day at 16:00 IST (after the 15:45 default close). Idempotent: replace_existing."""
    get_scheduler().add_job(
        _run, CronTrigger(hour=16, minute=0, timezone=_IST), id=JOB_ID, replace_existing=True,
        coalesce=True, max_instances=1, misfire_grace_time=3600,
    )
    logger.info("Registered session picks archive job (daily 16:00 IST).")
