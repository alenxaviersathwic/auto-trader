"""Pre-market health check (09:05 IST Mon-Fri): verifies Upstox token validity and Research Engine readiness."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.db.entity_status import EntityStatus
from app.core.db.session import async_session_factory
from app.core.events.notify import RESEARCH, SESSION_HALTED, notify
from app.core.logging.logger import logger
from app.core.scheduler.scheduler import get_scheduler

_IST = ZoneInfo("Asia/Kolkata")
JOB_ID = "system.premarket_health"


async def run_premarket_health_check() -> dict[str, bool]:
    """Check Upstox token validity and Research Engine data; notify user if action is needed before 09:15."""
    from app.modules.opportunity_finder.service.run_service import opportunity_run_service
    from app.modules.users.entity.upstox_config_entity import UpstoxConfig
    from app.modules.users.entity.user_entity import User

    now = datetime.now(UTC)
    token_ok = False
    research_ok = False
    async with async_session_factory() as s:
        res = await s.execute(
            select(UpstoxConfig)
            .join(User, User.id == UpstoxConfig.userId)
            .where(UpstoxConfig.accessTokenEnc.is_not(None))
            .where(UpstoxConfig.status == EntityStatus.ACTIVE, User.status == EntityStatus.ACTIVE)
            .order_by(User.isDefault.desc(), UpstoxConfig.lastAuthAt.desc().nulls_last())
            .limit(1)
        )
        cfg = res.scalars().first()
        if cfg and cfg.tokenExpiresAt:
            exp = cfg.tokenExpiresAt if cfg.tokenExpiresAt.tzinfo else cfg.tokenExpiresAt.replace(tzinfo=UTC)
            token_ok = exp > now
        research_ok = await opportunity_run_service.research_has_data(s)

    if not token_ok:
        logger.warning("[PREMARKET] Upstox token missing or expired -- re-authenticate before 09:15 IST")
        await notify(
            SESSION_HALTED,
            "Pre-Market: Upstox Token Expired",
            "Re-authenticate your Upstox account in Users & Accounts before 09:15 IST.",
            severity="warning",
            link="/users",
        )
    if not research_ok:
        logger.warning("[PREMARKET] Research Engine has no data yet -- run Research Engine before starting scanners")
        await notify(
            RESEARCH,
            "Pre-Market: Research Engine Empty",
            "Run the Research Engine so Opportunity Finders have today's directional bias.",
            severity="warning",
            link="/research",
        )
    if token_ok and research_ok:
        logger.info("[PREMARKET] Health check passed: Upstox token valid and Research data ready.")
    return {"tokenOk": token_ok, "researchOk": research_ok}


def register_premarket_health_job() -> None:
    get_scheduler().add_job(
        run_premarket_health_check,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=5, timezone=_IST),
        id=JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=1800,
    )
