import math
from typing import List, Optional
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.strategy_performance_snapshot_entity import StrategyPerformanceSnapshot
from app.modules.strategies.schema.performance_schema import PerformanceSnapshotFilter


class PerformanceRepository:
    """Repository handling database operations for StrategyPerformanceSnapshot."""

    async def get_by_id(
        self,
        session: AsyncSession,
        snapshot_id: int,
    ) -> Optional[StrategyPerformanceSnapshot]:
        stmt = select(StrategyPerformanceSnapshot).where(
            StrategyPerformanceSnapshot.id == snapshot_id,
            StrategyPerformanceSnapshot.status == EntityStatus.ACTIVE,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_by_source(
        self,
        session: AsyncSession,
        strategy_id: int,
    ) -> List[StrategyPerformanceSnapshot]:
        stmt = (
            select(StrategyPerformanceSnapshot)
            .where(
                StrategyPerformanceSnapshot.strategyId == strategy_id,
                StrategyPerformanceSnapshot.status == EntityStatus.ACTIVE,
            )
            .order_by(StrategyPerformanceSnapshot.createdAt.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        session: AsyncSession,
        strategy_id: int,
        filter_obj: PerformanceSnapshotFilter,
    ) -> PageResult[StrategyPerformanceSnapshot]:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        stmt = select(StrategyPerformanceSnapshot).where(
            StrategyPerformanceSnapshot.strategyId == strategy_id,
            StrategyPerformanceSnapshot.status == target_status,
        )

        if filter_obj.source:
            stmt = stmt.where(StrategyPerformanceSnapshot.source == filter_obj.source)
        if filter_obj.domain:
            stmt = stmt.where(StrategyPerformanceSnapshot.domain == filter_obj.domain)

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(StrategyPerformanceSnapshot.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(StrategyPerformanceSnapshot.createdAt <= filter_obj.dateFilter.to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        stmt = stmt.order_by(desc(StrategyPerformanceSnapshot.createdAt))
        offset = filter_obj.page * filter_obj.limit
        stmt = stmt.offset(offset).limit(filter_obj.limit)

        result = await session.execute(stmt)
        items = list(result.scalars().all())

        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

        return PageResult(
            list=items,
            page=filter_obj.page,
            limit=limit,
            totalPages=total_pages,
            totalItems=total_items,
        )

    async def save(
        self,
        session: AsyncSession,
        snapshot: StrategyPerformanceSnapshot,
    ) -> StrategyPerformanceSnapshot:
        session.add(snapshot)
        await session.flush()
        return snapshot
