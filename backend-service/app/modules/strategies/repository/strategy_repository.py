import math
from typing import List, Optional
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.strategy_entity import Strategy
from app.modules.strategies.entity.strategy_version_entity import StrategyVersion
from app.modules.strategies.entity.strategy_rule_entity import StrategyRule
from app.modules.strategies.schema.strategy_schema import StrategyFilter, StrategyVersionFilter


class StrategyRepository:
    """Repository handling database operations for Strategy, StrategyVersion, and StrategyRule."""

    async def get_by_id(
        self,
        session: AsyncSession,
        strategy_id: int,
        status: Optional[EntityStatus] = EntityStatus.ACTIVE,
    ) -> Optional[Strategy]:
        stmt = (
            select(Strategy)
            .options(
                selectinload(Strategy.versions),
                selectinload(Strategy.performanceSnapshots),
                selectinload(Strategy.healthEvents),
            )
            .where(Strategy.id == strategy_id)
        )
        if status is not None:
            stmt = stmt.where(Strategy.status == status)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        session: AsyncSession,
        code: str,
        status: EntityStatus = EntityStatus.ACTIVE,
    ) -> Optional[Strategy]:
        stmt = (
            select(Strategy)
            .options(
                selectinload(Strategy.versions),
                selectinload(Strategy.performanceSnapshots),
                selectinload(Strategy.healthEvents),
            )
            .where(Strategy.code == code, Strategy.status == status)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_id(
        self,
        session: AsyncSession,
        version_id: int,
    ) -> Optional[StrategyVersion]:
        stmt = (
            select(StrategyVersion)
            .options(
                selectinload(StrategyVersion.strategy),
                selectinload(StrategyVersion.strategyRules),
            )
            .where(StrategyVersion.id == version_id, StrategyVersion.status == EntityStatus.ACTIVE)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_no(
        self,
        session: AsyncSession,
        strategy_id: int,
        version_no: int,
    ) -> Optional[StrategyVersion]:
        stmt = (
            select(StrategyVersion)
            .options(
                selectinload(StrategyVersion.strategy),
                selectinload(StrategyVersion.strategyRules),
            )
            .where(
                StrategyVersion.strategyId == strategy_id,
                StrategyVersion.versionNo == version_no,
                StrategyVersion.status == EntityStatus.ACTIVE,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(
        self,
        session: AsyncSession,
        strategy_id: int,
        filter_obj: StrategyVersionFilter,
    ) -> PageResult[StrategyVersion]:
        stmt = (
            select(StrategyVersion)
            .where(
                StrategyVersion.strategyId == strategy_id,
                StrategyVersion.status == EntityStatus.ACTIVE,
            )
            .order_by(StrategyVersion.versionNo.desc())
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

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

    async def list_all_active(
        self,
        session: AsyncSession,
    ) -> List[Strategy]:
        stmt = (
            select(Strategy)
            .options(
                selectinload(Strategy.versions),
                selectinload(Strategy.performanceSnapshots),
            )
            .where(Strategy.status == EntityStatus.ACTIVE)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        session: AsyncSession,
        filter_obj: StrategyFilter,
    ) -> PageResult[Strategy]:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        stmt = (
            select(Strategy)
            .options(
                selectinload(Strategy.versions),
                selectinload(Strategy.performanceSnapshots),
                selectinload(Strategy.healthEvents),
            )
            .where(Strategy.status == target_status)
        )

        if filter_obj.category:
            stmt = stmt.where(Strategy.category == filter_obj.category)
        if filter_obj.structure:
            stmt = stmt.where(Strategy.structure == filter_obj.structure)
        if filter_obj.bias:
            stmt = stmt.where(Strategy.bias == filter_obj.bias)
        if filter_obj.optionSide:
            stmt = stmt.where(Strategy.optionSide == filter_obj.optionSide)
        if filter_obj.exchange:
            stmt = stmt.where(Strategy.exchange == filter_obj.exchange)
        if filter_obj.lifecycleStatus:
            stmt = stmt.where(Strategy.lifecycleStatus == filter_obj.lifecycleStatus)
        if filter_obj.health:
            stmt = stmt.where(Strategy.health == filter_obj.health)
        if filter_obj.validationStatus:
            stmt = stmt.where(Strategy.validationStatus == filter_obj.validationStatus)
        if filter_obj.definitionFormat:
            stmt = stmt.where(Strategy.definitionFormat == filter_obj.definitionFormat)
        if filter_obj.executable is not None:
            stmt = stmt.where(Strategy.executable.is_(filter_obj.executable))

        # JSONB contains checks
        if filter_obj.market:
            stmt = stmt.where(Strategy.markets.contains([filter_obj.market]))
        if filter_obj.underlyingType:
            stmt = stmt.where(Strategy.underlyingTypes.contains([filter_obj.underlyingType]))
        if filter_obj.tradingMode:
            stmt = stmt.where(Strategy.tradingModes.contains([filter_obj.tradingMode]))
        if filter_obj.executionMode:
            stmt = stmt.where(Strategy.executionModes.contains([filter_obj.executionMode]))
        if filter_obj.tag:
            stmt = stmt.where(Strategy.tags.contains([filter_obj.tag]))
        if filter_obj.source:
            stmt = stmt.where(Strategy.provenance["source"].astext == filter_obj.source)

        if filter_obj.hasReviewFlags is True:
            stmt = stmt.where(func.jsonb_array_length(Strategy.reviewFlags) > 0)
        elif filter_obj.hasReviewFlags is False:
            stmt = stmt.where(
                or_(Strategy.reviewFlags.is_(None), func.jsonb_array_length(Strategy.reviewFlags) == 0)
            )

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(Strategy.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(Strategy.createdAt <= filter_obj.dateFilter.to)

        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(
                or_(
                    Strategy.code.ilike(term),
                    Strategy.name.ilike(term),
                    Strategy.description.ilike(term),
                    Strategy.tags.cast(String).ilike(term),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        # Sortable: createdAt, name, category, health, lifecycleStatus
        allowed_sorts = {"createdAt", "name", "category", "health", "lifecycleStatus"}
        sort_by = filter_obj.sortBy or "createdAt"
        if sort_by not in allowed_sorts:
            raise ValidationException(message=f"Invalid sortBy field '{sort_by}'. Allowed: {sorted(list(allowed_sorts))}")

        sort_col = getattr(Strategy, sort_by, Strategy.createdAt)
        sort_dir = (filter_obj.sortDir or "desc").lower()
        order_clause = desc(sort_col) if sort_dir == "desc" else asc(sort_col)
        stmt = stmt.order_by(order_clause)

        offset = filter_obj.page * filter_obj.limit
        stmt = stmt.offset(offset).limit(filter_obj.limit)

        result = await session.execute(stmt)
        strategies = list(result.scalars().all())

        # If suggestable filter is requested, filter in memory or apply criteria
        if filter_obj.suggestable is not None:
            strategies = [s for s in strategies if s.suggestable is filter_obj.suggestable]

        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

        return PageResult(
            list=strategies,
            page=filter_obj.page,
            limit=limit,
            totalPages=total_pages,
            totalItems=total_items,
        )

    async def save(self, session: AsyncSession, strategy: Strategy) -> Strategy:
        session.add(strategy)
        await session.flush()
        return strategy

    async def save_version(self, session: AsyncSession, version: StrategyVersion) -> StrategyVersion:
        session.add(version)
        await session.flush()
        return version

    async def save_strategy_rule(self, session: AsyncSession, rule_assoc: StrategyRule) -> StrategyRule:
        session.add(rule_assoc)
        await session.flush()
        return rule_assoc

    async def soft_delete(self, session: AsyncSession, strategy: Strategy) -> None:
        strategy.status = EntityStatus.DELETED
        strategy.enabled = False
        strategy.lifecycleStatus = "ARCHIVED"
        await session.flush()
