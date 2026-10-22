import math
from typing import List, Optional
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.registry_item_entity import RegistryItem
from app.modules.strategies.schema.registry_schema import RegistryFilter


class RegistryRepository:
    """Repository handling database operations for RegistryItem."""

    async def get_by_id(
        self,
        session: AsyncSession,
        item_id: int,
        status: Optional[EntityStatus] = EntityStatus.ACTIVE,
    ) -> Optional[RegistryItem]:
        stmt = select(RegistryItem).where(RegistryItem.id == item_id)
        if status is not None:
            stmt = stmt.where(RegistryItem.status == status)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_type_and_code(
        self,
        session: AsyncSession,
        registry_type: str,
        code: str,
        status: EntityStatus = EntityStatus.ACTIVE,
    ) -> Optional[RegistryItem]:
        stmt = select(RegistryItem).where(
            RegistryItem.registryType == registry_type,
            RegistryItem.code == code,
            RegistryItem.status == status,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_type(
        self,
        session: AsyncSession,
        registry_type: str,
        enabled_only: bool = True,
    ) -> List[RegistryItem]:
        stmt = select(RegistryItem).where(
            RegistryItem.registryType == registry_type,
            RegistryItem.status == EntityStatus.ACTIVE,
        )
        if enabled_only:
            stmt = stmt.where(RegistryItem.enabled.is_(True))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_active(
        self,
        session: AsyncSession,
    ) -> List[RegistryItem]:
        stmt = select(RegistryItem).where(RegistryItem.status == EntityStatus.ACTIVE)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_types(
        self,
        session: AsyncSession,
    ) -> List[str]:
        stmt = (
            select(RegistryItem.registryType)
            .where(RegistryItem.status == EntityStatus.ACTIVE)
            .distinct()
            .order_by(RegistryItem.registryType.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        session: AsyncSession,
        filter_obj: RegistryFilter,
    ) -> PageResult[RegistryItem]:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        stmt = select(RegistryItem).where(RegistryItem.status == target_status)

        if filter_obj.registryType:
            stmt = stmt.where(RegistryItem.registryType == filter_obj.registryType)
        if filter_obj.kind:
            stmt = stmt.where(RegistryItem.kind == filter_obj.kind)
        if filter_obj.executable is not None:
            stmt = stmt.where(RegistryItem.executable.is_(filter_obj.executable))
        if filter_obj.enabled is not None:
            stmt = stmt.where(RegistryItem.enabled.is_(filter_obj.enabled))

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(RegistryItem.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(RegistryItem.createdAt <= filter_obj.dateFilter.to)

        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(
                or_(
                    RegistryItem.code.ilike(term),
                    RegistryItem.name.ilike(term),
                    RegistryItem.description.ilike(term),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "createdAt"
        sort_dir = (filter_obj.sortDir or "desc").lower()

        sort_col = getattr(RegistryItem, sort_by, RegistryItem.createdAt)
        order_clause = desc(sort_col) if sort_dir == "desc" else asc(sort_col)
        stmt = stmt.order_by(order_clause)

        offset = filter_obj.page * filter_obj.limit
        stmt = stmt.offset(offset).limit(filter_obj.limit)

        items_res = await session.execute(stmt)
        items = list(items_res.scalars().all())

        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

        return PageResult(
            list=items,
            page=filter_obj.page,
            limit=limit,
            totalPages=total_pages,
            totalItems=total_items,
        )

    async def save(self, session: AsyncSession, item: RegistryItem) -> RegistryItem:
        session.add(item)
        await session.flush()
        return item

    async def soft_delete(self, session: AsyncSession, item: RegistryItem) -> None:
        item.status = EntityStatus.DELETED
        item.enabled = False
        await session.flush()
