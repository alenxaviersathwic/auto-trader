import math
from typing import List, Optional
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.health_policy_entity import HealthPolicy
from app.modules.strategies.entity.strategy_health_event_entity import StrategyHealthEvent
from app.modules.strategies.schema.performance_schema import HealthEventFilter, HealthPolicyFilter


class HealthRepository:
    """Repository handling database operations for HealthPolicy and StrategyHealthEvent."""

    async def get_policy_by_id(
        self,
        session: AsyncSession,
        policy_id: int,
    ) -> Optional[HealthPolicy]:
        stmt = select(HealthPolicy).where(HealthPolicy.id == policy_id, HealthPolicy.status == EntityStatus.ACTIVE)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_policy_by_code(
        self,
        session: AsyncSession,
        code: str,
    ) -> Optional[HealthPolicy]:
        stmt = select(HealthPolicy).where(HealthPolicy.code == code, HealthPolicy.status == EntityStatus.ACTIVE)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_policies(
        self,
        session: AsyncSession,
    ) -> List[HealthPolicy]:
        stmt = (
            select(HealthPolicy)
            .where(HealthPolicy.enabled.is_(True), HealthPolicy.status == EntityStatus.ACTIVE)
            .order_by(HealthPolicy.id.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search_policies(
        self,
        session: AsyncSession,
        filter_obj: HealthPolicyFilter,
    ) -> PageResult[HealthPolicy]:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        stmt = select(HealthPolicy).where(HealthPolicy.status == target_status)

        if filter_obj.enabled is not None:
            stmt = stmt.where(HealthPolicy.enabled.is_(filter_obj.enabled))
        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(HealthPolicy.name.ilike(term) | HealthPolicy.code.ilike(term))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        stmt = stmt.order_by(desc(HealthPolicy.createdAt))
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

    async def save_policy(self, session: AsyncSession, policy: HealthPolicy) -> HealthPolicy:
        session.add(policy)
        await session.flush()
        return policy

    async def soft_delete_policy(self, session: AsyncSession, policy: HealthPolicy) -> None:
        policy.status = EntityStatus.DELETED
        policy.enabled = False
        await session.flush()

    async def get_recent_events_for_strategy(
        self,
        session: AsyncSession,
        strategy_id: int,
        limit: int = 20,
    ) -> List[StrategyHealthEvent]:
        stmt = (
            select(StrategyHealthEvent)
            .where(StrategyHealthEvent.strategyId == strategy_id, StrategyHealthEvent.status == EntityStatus.ACTIVE)
            .order_by(desc(StrategyHealthEvent.createdAt))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search_events(
        self,
        session: AsyncSession,
        filter_obj: HealthEventFilter,
    ) -> PageResult[StrategyHealthEvent]:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        stmt = select(StrategyHealthEvent).where(StrategyHealthEvent.status == target_status)

        if filter_obj.strategyId:
            stmt = stmt.where(StrategyHealthEvent.strategyId == filter_obj.strategyId)
        if filter_obj.toHealth:
            stmt = stmt.where(StrategyHealthEvent.toHealth == filter_obj.toHealth)
        if filter_obj.triggeredBy:
            stmt = stmt.where(StrategyHealthEvent.triggeredBy == filter_obj.triggeredBy)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        stmt = stmt.order_by(desc(StrategyHealthEvent.createdAt))
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

    async def save_event(self, session: AsyncSession, event: StrategyHealthEvent) -> StrategyHealthEvent:
        session.add(event)
        await session.flush()
        return event
