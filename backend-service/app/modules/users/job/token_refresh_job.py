from datetime import datetime, timedelta

from app.core.logging.logger import logger
from app.core.scheduler.scheduler import get_scheduler, tz
from app.modules.users.service.user_service import UserService

JOB_ID = "users.upstox_token_refresh"
_user_service = UserService()


async def _run() -> None:
    try:
        await _user_service.refresh_expiring_tokens()
    except Exception as ex:
        logger.error(f"[UPSTOX_TOKEN_REFRESH] job failed: {ex}")


def register_token_refresh_job() -> None:
    """
    Every 15 minutes (first run ~20s after boot): renew Upstox tokens that are missing,
    expired, or expire within 30 minutes. Tokens die at 03:30 IST, so the first tick after
    03:30 renews them well before the 09:00 MCX / 09:15 NSE open. Idempotent: replace_existing.
    """
    get_scheduler().add_job(
        _run,
        "interval",
        minutes=15,
        id=JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=datetime.now(tz) + timedelta(seconds=20),
    )
    logger.info("Registered Upstox token refresh job (every 15 min).")
