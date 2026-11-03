import math

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.sessions.entity.trading_session_entity import TradingSession
from app.modules.sessions.schema.trading_session_schema import TradingSessionSearchFilter


class TradingSessionRepository:
    """Repository handling database operations for TradingSession."""

    async def get_by_id(
        self,
        session: AsyncSession,
        session_id: int,
        status: EntityStatus | None = EntityStatus.ACTIVE,
    ) -> TradingSession | None:
        """Fetch a trading session by id, optionally filtered by status."""
        stmt = select(TradingSession).where(TradingSession.id == session_id)
        if status is not None:
            stmt = stmt.where(TradingSession.status == status)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        session: AsyncSession,
        filter_obj: TradingSessionSearchFilter,
    ) -> PageResult[TradingSession]:
        """Paged search over trading sessions with scope/sessionStatus/sessionType/userId/tradeDate filters."""
        target_status = filter_obj.status or EntityStatus.ACTIVE

        base_stmt = select(TradingSession).where(TradingSession.status == target_status)

        if filter_obj.scope:
            base_stmt = base_stmt.where(TradingSession.scope == filter_obj.scope.upper())
        if filter_obj.sessionStatus:
            base_stmt = base_stmt.where(TradingSession.sessionStatus == filter_obj.sessionStatus.upper())
        if filter_obj.sessionType:
            base_stmt = base_stmt.where(TradingSession.sessionType == filter_obj.sessionType.upper())
        if filter_obj.userId is not None:
            base_stmt = base_stmt.where(TradingSession.userId == filter_obj.userId)
        if filter_obj.tradeDate:
            base_stmt = base_stmt.where(TradingSession.tradeDate == filter_obj.tradeDate)

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                base_stmt = base_stmt.where(TradingSession.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                base_stmt = base_stmt.where(TradingSession.createdAt <= filter_obj.dateFilter.to)

        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            base_stmt = base_stmt.where(TradingSession.name.ilike(term))

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_items = (await session.execute(count_stmt)).scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "createdAt"
        allowed_sorts = {"createdAt", "name", "tradeDate", "capital"}
        if sort_by not in allowed_sorts:
            raise ValidationException(
                message=f"Invalid sortBy field '{sort_by}'. Allowed fields: {sorted(allowed_sorts)}"
            )
        sort_col = getattr(TradingSession, sort_by)
        sort_dir = (filter_obj.sortDir or "desc").lower()
        order_clause = desc(sort_col) if sort_dir == "desc" else asc(sort_col)

        offset = filter_obj.page * filter_obj.limit
        paged_stmt = base_stmt.order_by(order_clause).offset(offset).limit(filter_obj.limit)

        result = await session.execute(paged_stmt)
        rows = list(result.scalars().all())

        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

        return PageResult(
            list=rows,
            page=filter_obj.page,
            limit=limit,
            totalPages=total_pages,
            totalItems=total_items,
        )

    async def save(self, session: AsyncSession, entity: TradingSession) -> TradingSession:
        """Add and flush a trading session."""
        session.add(entity)
        await session.flush()
        return entity

    async def soft_delete(self, session: AsyncSession, entity: TradingSession) -> None:
        """Soft delete a trading session."""
        entity.status = EntityStatus.DELETED
        await session.flush()
