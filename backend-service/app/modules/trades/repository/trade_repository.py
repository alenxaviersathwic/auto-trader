import math
from datetime import datetime

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.trades.entity.trade_entity import ActiveTrade
from app.modules.trades.schema.trade_schema import TradeSearchFilter


class TradeRepository:
    """Repository handling database operations for ActiveTrade."""

    async def get_by_id(self, session: AsyncSession, trade_id: int) -> ActiveTrade | None:
        res = await session.execute(
            select(ActiveTrade)
            .where(ActiveTrade.id == trade_id)
            .where(ActiveTrade.status == EntityStatus.ACTIVE)
        )
        return res.scalar_one_or_none()

    async def get_by_pick_id(self, session: AsyncSession, pick_id: int) -> ActiveTrade | None:
        res = await session.execute(
            select(ActiveTrade)
            .where(ActiveTrade.pickId == pick_id)
            .where(ActiveTrade.status == EntityStatus.ACTIVE)
        )
        return res.scalar_one_or_none()

    async def running_for_session(self, session: AsyncSession, session_id: int) -> list[ActiveTrade]:
        res = await session.execute(
            select(ActiveTrade)
            .where(ActiveTrade.sessionId == session_id)
            .where(ActiveTrade.status == EntityStatus.ACTIVE)
            .where(ActiveTrade.tradeState == "RUNNING")
            .order_by(ActiveTrade.id)
        )
        return list(res.scalars().all())

    async def all_for_session(self, session: AsyncSession, session_id: int) -> list[ActiveTrade]:
        res = await session.execute(
            select(ActiveTrade)
            .where(ActiveTrade.sessionId == session_id)
            .where(ActiveTrade.status == EntityStatus.ACTIVE)
            .order_by(ActiveTrade.id.desc())
        )
        return list(res.scalars().all())

    async def running_ids_today(self, session: AsyncSession, day_start: datetime) -> list[int]:
        res = await session.execute(
            select(ActiveTrade.id)
            .where(ActiveTrade.status == EntityStatus.ACTIVE)
            .where(ActiveTrade.tradeState == "RUNNING")
            .where(ActiveTrade.enteredAt >= day_start)
            .order_by(ActiveTrade.id)
        )
        return [int(x) for x in res.scalars().all()]

    async def net_pnl_exited_since(self, session: AsyncSession, user_id: int, since: datetime) -> float:
        """Sum of netPnl of this user's EXITED trades with exitedAt >= since (all sessions)."""
        res = await session.execute(
            select(func.coalesce(func.sum(ActiveTrade.netPnl), 0))
            .where(ActiveTrade.userId == user_id)
            .where(ActiveTrade.tradeState == "EXITED")
            .where(ActiveTrade.exitedAt >= since)
            .where(ActiveTrade.status == EntityStatus.ACTIVE)
        )
        return float(res.scalar_one() or 0)

    async def save(self, session: AsyncSession, entity: ActiveTrade) -> ActiveTrade:
        session.add(entity)
        await session.flush()
        return entity

    async def search(self, session: AsyncSession, filter_obj: TradeSearchFilter) -> PageResult[ActiveTrade]:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        base = select(ActiveTrade).where(ActiveTrade.status == target_status)

        if filter_obj.sessionId is not None:
            base = base.where(ActiveTrade.sessionId == filter_obj.sessionId)
        if filter_obj.underlyingCode:
            base = base.where(ActiveTrade.underlyingCode == filter_obj.underlyingCode.upper())
        if filter_obj.tradeState:
            base = base.where(ActiveTrade.tradeState == filter_obj.tradeState.upper())
        if filter_obj.traderProfile:
            base = base.where(ActiveTrade.traderProfile == filter_obj.traderProfile.upper())
        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                base = base.where(ActiveTrade.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                base = base.where(ActiveTrade.createdAt <= filter_obj.dateFilter.to)
        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            base = base.where(
                ActiveTrade.underlyingCode.ilike(term)
                | ActiveTrade.strategy.ilike(term)
                | ActiveTrade.opportunityRef.ilike(term)
            )

        total_items = (
            await session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "createdAt"
        allowed = {"createdAt", "enteredAt", "exitedAt", "netPnl", "pnlPct", "confidence", "capitalUsed"}
        if sort_by not in allowed:
            raise ValidationException(
                message=f"Invalid sortBy field '{sort_by}'. Allowed fields: {sorted(allowed)}"
            )
        col = getattr(ActiveTrade, sort_by)
        order = desc(col) if (filter_obj.sortDir or "desc").lower() == "desc" else asc(col)

        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        rows = list(
            (
                await session.execute(
                    base.order_by(order).offset(filter_obj.page * limit).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return PageResult(
            list=rows,
            page=filter_obj.page,
            limit=limit,
            totalPages=math.ceil(total_items / limit) if total_items > 0 else 0,
            totalItems=total_items,
        )


trade_repository = TradeRepository()

