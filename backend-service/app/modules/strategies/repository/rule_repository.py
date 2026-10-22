from datetime import date
import math
from typing import List, Optional
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.db.entity_status import EntityStatus
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.rule_entity import Rule
from app.modules.strategies.entity.rule_version_entity import RuleVersion
from app.modules.strategies.entity.strategy_rule_entity import StrategyRule
from app.modules.strategies.entity.strategy_version_entity import StrategyVersion
from app.modules.strategies.entity.strategy_entity import Strategy
from app.modules.strategies.schema.rule_schema import RuleFilter, RuleVersionFilter, StrategyUsageSummary


class RuleRepository:
    """Repository handling database operations for Rule, RuleVersion, and their strategy usages."""

    async def get_by_id(
        self,
        session: AsyncSession,
        rule_id: int,
        status: Optional[EntityStatus] = EntityStatus.ACTIVE,
    ) -> Optional[Rule]:
        stmt = select(Rule).options(selectinload(Rule.versions)).where(Rule.id == rule_id)
        if status is not None:
            stmt = stmt.where(Rule.status == status)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        session: AsyncSession,
        code: str,
        status: EntityStatus = EntityStatus.ACTIVE,
    ) -> Optional[Rule]:
        stmt = (
            select(Rule)
            .options(selectinload(Rule.versions))
            .where(Rule.code == code, Rule.status == status)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_id(
        self,
        session: AsyncSession,
        version_id: int,
    ) -> Optional[RuleVersion]:
        stmt = select(RuleVersion).where(RuleVersion.id == version_id, RuleVersion.status == EntityStatus.ACTIVE)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_no(
        self,
        session: AsyncSession,
        rule_id: int,
        version_no: int,
    ) -> Optional[RuleVersion]:
        stmt = select(RuleVersion).where(
            RuleVersion.ruleId == rule_id,
            RuleVersion.versionNo == version_no,
            RuleVersion.status == EntityStatus.ACTIVE,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(
        self,
        session: AsyncSession,
        rule_id: int,
        filter_obj: RuleVersionFilter,
    ) -> PageResult[RuleVersion]:
        stmt = (
            select(RuleVersion)
            .where(RuleVersion.ruleId == rule_id, RuleVersion.status == EntityStatus.ACTIVE)
            .order_by(RuleVersion.versionNo.desc())
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

    async def get_strategies_using_rule(
        self,
        session: AsyncSession,
        rule_id: int,
    ) -> List[StrategyUsageSummary]:
        stmt = (
            select(Strategy.id, Strategy.code, Strategy.name, StrategyRule.role)
            .join(StrategyVersion, StrategyVersion.id == StrategyRule.strategyVersionId)
            .join(Strategy, Strategy.id == StrategyVersion.strategyId)
            .where(
                StrategyRule.ruleId == rule_id,
                StrategyRule.status == EntityStatus.ACTIVE,
                Strategy.status == EntityStatus.ACTIVE,
            )
            .distinct()
        )
        result = await session.execute(stmt)
        return [
            StrategyUsageSummary(strategyId=row[0], code=row[1], name=row[2], role=row[3])
            for row in result.all()
        ]

    async def get_active_guardrails(
        self,
        session: AsyncSession,
    ) -> List[Rule]:
        stmt = (
            select(Rule)
            .options(selectinload(Rule.versions))
            .where(
                Rule.ruleKind == "GUARDRAIL",
                Rule.enabled.is_(True),
                Rule.status == EntityStatus.ACTIVE,
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        session: AsyncSession,
        filter_obj: RuleFilter,
    ) -> PageResult[Rule]:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        stmt = select(Rule).options(selectinload(Rule.versions)).where(Rule.status == target_status)

        if filter_obj.ruleKind:
            stmt = stmt.where(Rule.ruleKind == filter_obj.ruleKind)
        if filter_obj.ruleType:
            stmt = stmt.where(Rule.ruleType == filter_obj.ruleType)
        if filter_obj.action:
            stmt = stmt.where(Rule.action == filter_obj.action)
        if filter_obj.priority:
            stmt = stmt.where(Rule.priority == filter_obj.priority)
        if filter_obj.executable is not None:
            stmt = stmt.where(Rule.executable.is_(filter_obj.executable))
        if filter_obj.enabled is not None:
            stmt = stmt.where(Rule.enabled.is_(filter_obj.enabled))

        # Scope filters in appliesTo jsonb
        if filter_obj.market:
            stmt = stmt.where(Rule.appliesTo["markets"].contains([filter_obj.market]))
        if filter_obj.optionSide:
            stmt = stmt.where(Rule.appliesTo["optionSides"].contains([filter_obj.optionSide]))
        if filter_obj.executionDomain:
            stmt = stmt.where(Rule.appliesTo["executionDomains"].contains([filter_obj.executionDomain]))

        if filter_obj.stale is True:
            stmt = stmt.where(Rule.reviewBy.is_not(None), Rule.reviewBy < date.today())
        elif filter_obj.stale is False:
            stmt = stmt.where(or_(Rule.reviewBy.is_(None), Rule.reviewBy >= date.today()))

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(Rule.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(Rule.createdAt <= filter_obj.dateFilter.to)

        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(
                or_(
                    Rule.code.ilike(term),
                    Rule.name.ilike(term),
                    Rule.conditionText.ilike(term),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "createdAt"
        sort_dir = (filter_obj.sortDir or "desc").lower()
        sort_col = getattr(Rule, sort_by, Rule.createdAt)
        order_clause = desc(sort_col) if sort_dir == "desc" else asc(sort_col)
        stmt = stmt.order_by(order_clause)

        offset = filter_obj.page * filter_obj.limit
        stmt = stmt.offset(offset).limit(filter_obj.limit)

        result = await session.execute(stmt)
        rules = list(result.scalars().all())

        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

        return PageResult(
            list=rules,
            page=filter_obj.page,
            limit=limit,
            totalPages=total_pages,
            totalItems=total_items,
        )

    async def save(self, session: AsyncSession, rule: Rule) -> Rule:
        session.add(rule)
        await session.flush()
        return rule

    async def save_version(self, session: AsyncSession, version: RuleVersion) -> RuleVersion:
        session.add(version)
        await session.flush()
        return version

    async def soft_delete(self, session: AsyncSession, rule: Rule) -> None:
        rule.status = EntityStatus.DELETED
        rule.enabled = False
        await session.flush()
