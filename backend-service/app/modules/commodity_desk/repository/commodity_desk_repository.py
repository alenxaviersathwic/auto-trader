import math
from datetime import datetime
from typing import Any

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult
from app.modules.commodity_desk.entity.desk_decision_entity import DeskDecision
from app.modules.commodity_desk.entity.market_move_entity import MarketMove

DECISION_SORTS = {"createdAt", "decidedAt", "conviction", "underlyingCode"}
MOVE_SORTS = {"createdAt", "detectedAt", "movePct", "underlyingCode"}


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


class CommodityDeskRepository:
    async def save(self, session: AsyncSession, row: Any) -> Any:
        session.add(row)
        await session.flush()
        return row

    async def get_decision(self, session: AsyncSession, decision_id: int) -> DeskDecision | None:
        return await session.get(DeskDecision, decision_id)

    async def get_move(self, session: AsyncSession, move_id: int) -> MarketMove | None:
        return await session.get(MarketMove, move_id)

    async def search_decisions(self, session: AsyncSession, f: Any) -> PageResult[DeskDecision]:
        stmt = select(DeskDecision).where(DeskDecision.status == EntityStatus.ACTIVE)
        if getattr(f, "underlyingCode", None):
            stmt = stmt.where(DeskDecision.underlyingCode == f.underlyingCode.upper())
        if getattr(f, "decision", None):
            stmt = stmt.where(DeskDecision.decision == f.decision.upper())
        if f.query:
            stmt = stmt.where(DeskDecision.thinking.ilike(f"%{f.query}%"))
        return await _page(session, DeskDecision, stmt, f, DECISION_SORTS)

    async def search_moves(self, session: AsyncSession, f: Any) -> PageResult[MarketMove]:
        stmt = select(MarketMove).where(MarketMove.status == EntityStatus.ACTIVE)
        if getattr(f, "underlyingCode", None):
            stmt = stmt.where(MarketMove.underlyingCode == f.underlyingCode.upper())
        if f.query:
            stmt = stmt.where(MarketMove.summary.ilike(f"%{f.query}%"))
        return await _page(session, MarketMove, stmt, f, MOVE_SORTS)

    async def latest_decisions(self, session: AsyncSession, since: datetime) -> list[DeskDecision]:
        """Newest decision per commodity since `since`."""
        sub = (select(DeskDecision.underlyingCode.label("code"), func.max(DeskDecision.decidedAt).label("at"))
               .where(DeskDecision.status == EntityStatus.ACTIVE, DeskDecision.decidedAt >= since)
               .group_by(DeskDecision.underlyingCode).subquery())
        stmt = (select(DeskDecision).join(sub, (DeskDecision.underlyingCode == sub.c.code)
                                          & (DeskDecision.decidedAt == sub.c.at))
                .where(DeskDecision.status == EntityStatus.ACTIVE).order_by(DeskDecision.underlyingCode))
        return list((await session.execute(stmt)).scalars().all())

    async def moves_since(self, session: AsyncSession, since: datetime, code: str | None = None) -> list[MarketMove]:
        stmt = select(MarketMove).where(MarketMove.status == EntityStatus.ACTIVE, MarketMove.detectedAt >= since)
        if code:
            stmt = stmt.where(MarketMove.underlyingCode == code)
        return list((await session.execute(stmt.order_by(MarketMove.detectedAt.desc()))).scalars().all())


commodity_desk_repository = CommodityDeskRepository()
