import math
from datetime import datetime
from typing import Any

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult
from app.modules.autopsy.entity.setup_guard_entity import SetupGuard
from app.modules.autopsy.entity.setup_scorecard_entity import SetupScorecard
from app.modules.autopsy.entity.trade_autopsy_entity import TradeAutopsy
from app.modules.autopsy.schema.learning_schema import (
    AutopsySearchFilter,
    GuardSearchFilter,
    ScorecardSearchFilter,
)


async def _page(session: AsyncSession, model: Any, stmt: Any, f: BaseFilter, sorts: set[str]) -> PageResult[Any]:
    if f.dateFilter:
        if f.dateFilter.from_ is not None and f.dateFilter.to is not None and f.dateFilter.from_ > f.dateFilter.to:
            raise ValidationException(message="dateFilter.from must not be later than dateFilter.to")
        if f.dateFilter.from_ is not None:
            stmt = stmt.where(model.createdAt >= f.dateFilter.from_)
        if f.dateFilter.to is not None:
            stmt = stmt.where(model.createdAt <= f.dateFilter.to)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one_or_none() or 0
    sort_by = f.sortBy or "createdAt"
    if sort_by not in sorts:
        raise ValidationException(message=f"Invalid sortBy '{sort_by}'. Allowed: {sorted(sorts)}")
    col = getattr(model, sort_by)
    stmt = stmt.order_by(desc(col) if (f.sortDir or "desc").lower() == "desc" else asc(col))
    rows = list((await session.execute(stmt.offset(f.page * f.limit).limit(f.limit))).scalars().all())
    return PageResult(list=rows, page=f.page, limit=f.limit,
                      totalPages=math.ceil(total / f.limit) if total else 0, totalItems=total)


class LearningRepository:
    """trade_autopsies, setup_scorecards and setup_guards; every row belongs to one session manager (managerCode)."""

    # ───────── autopsies ─────────
    async def autopsy_for_trade(self, session: AsyncSession, trade_id: int) -> TradeAutopsy | None:
        res = await session.execute(select(TradeAutopsy).where(TradeAutopsy.tradeId == trade_id)
                                    .where(TradeAutopsy.status == EntityStatus.ACTIVE))
        return res.scalar_one_or_none()

    async def autopsies_since(self, session: AsyncSession, manager: str, setup: str,
                              since: datetime) -> list[TradeAutopsy]:
        res = await session.execute(select(TradeAutopsy).where(TradeAutopsy.managerCode == manager)
                                    .where(TradeAutopsy.setup == setup)
                                    .where(TradeAutopsy.status == EntityStatus.ACTIVE)
                                    .where(TradeAutopsy.createdAt >= since).order_by(TradeAutopsy.id))
        return list(res.scalars().all())

    async def search_autopsies(self, session: AsyncSession, f: AutopsySearchFilter) -> PageResult[TradeAutopsy]:
        stmt = select(TradeAutopsy).where(TradeAutopsy.status == (f.status or EntityStatus.ACTIVE))
        if f.managerCode:
            stmt = stmt.where(TradeAutopsy.managerCode == f.managerCode)
        if f.sessionId is not None:
            stmt = stmt.where(TradeAutopsy.sessionId == f.sessionId)
        if f.setup:
            stmt = stmt.where(TradeAutopsy.setup == f.setup)
        if f.outcome:
            stmt = stmt.where(TradeAutopsy.outcome == f.outcome.upper())
        if f.query and f.query.strip():
            stmt = stmt.where(TradeAutopsy.setup.ilike(f"%{f.query.strip()}%"))
        return await _page(session, TradeAutopsy, stmt, f, {"createdAt", "netPnl", "rMultiple"})

    # ───────── scorecards ─────────
    async def scorecard(self, session: AsyncSession, manager: str, setup: str) -> SetupScorecard | None:
        res = await session.execute(select(SetupScorecard).where(SetupScorecard.managerCode == manager)
                                    .where(SetupScorecard.setup == setup)
                                    .where(SetupScorecard.status == EntityStatus.ACTIVE))
        return res.scalar_one_or_none()

    async def all_scorecards(self, session: AsyncSession) -> list[SetupScorecard]:
        res = await session.execute(select(SetupScorecard).where(SetupScorecard.status == EntityStatus.ACTIVE))
        return list(res.scalars().all())

    async def search_scorecards(self, session: AsyncSession, f: ScorecardSearchFilter) -> PageResult[SetupScorecard]:
        stmt = select(SetupScorecard).where(SetupScorecard.status == (f.status or EntityStatus.ACTIVE))
        if f.managerCode:
            stmt = stmt.where(SetupScorecard.managerCode == f.managerCode)
        if f.scoreStatus:
            stmt = stmt.where(SetupScorecard.scoreStatus == f.scoreStatus.upper())
        if f.query and f.query.strip():
            stmt = stmt.where(SetupScorecard.setup.ilike(f"%{f.query.strip()}%"))
        return await _page(session, SetupScorecard, stmt, f,
                           {"createdAt", "netPnl", "closedTrades", "avgR", "winRatePct", "setup"})

    # ───────── guards ─────────
    async def guard(self, session: AsyncSession, guard_id: int) -> SetupGuard | None:
        res = await session.execute(select(SetupGuard).where(SetupGuard.id == guard_id)
                                    .where(SetupGuard.status == EntityStatus.ACTIVE))
        return res.scalar_one_or_none()

    async def guards_for(self, session: AsyncSession, manager: str, setup: str) -> list[SetupGuard]:
        res = await session.execute(select(SetupGuard).where(SetupGuard.managerCode == manager)
                                    .where(SetupGuard.setup == setup)
                                    .where(SetupGuard.status == EntityStatus.ACTIVE))
        return list(res.scalars().all())

    async def applied_guards(self, session: AsyncSession) -> list[SetupGuard]:
        res = await session.execute(select(SetupGuard).where(SetupGuard.guardState == "APPLIED")
                                    .where(SetupGuard.status == EntityStatus.ACTIVE))
        return list(res.scalars().all())

    async def search_guards(self, session: AsyncSession, f: GuardSearchFilter) -> PageResult[SetupGuard]:
        stmt = select(SetupGuard).where(SetupGuard.status == (f.status or EntityStatus.ACTIVE))
        if f.managerCode:
            stmt = stmt.where(SetupGuard.managerCode == f.managerCode)
        if f.setup:
            stmt = stmt.where(SetupGuard.setup == f.setup)
        if f.guardState:
            stmt = stmt.where(SetupGuard.guardState == f.guardState.upper())
        if f.query and f.query.strip():
            stmt = stmt.where(SetupGuard.text.ilike(f"%{f.query.strip()}%"))
        return await _page(session, SetupGuard, stmt, f, {"createdAt", "setup"})

    async def save(self, session: AsyncSession, entity: Any) -> Any:
        session.add(entity)
        await session.flush()
        return entity
