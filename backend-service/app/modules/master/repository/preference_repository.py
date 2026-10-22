import math
from typing import Any, Dict, List, Optional
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_preference_entity import MasterPreference


class PreferenceFilter(BaseFilter):
    pass


class PreferenceRepository:
    async def get_by_key(
        self,
        session: AsyncSession,
        key: str,
        status: EntityStatus = EntityStatus.ACTIVE,
    ) -> Optional[MasterPreference]:
        stmt = select(MasterPreference).where(MasterPreference.key == key, MasterPreference.status == status)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_all_dict(
        self,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        stmt = select(MasterPreference).where(MasterPreference.status == EntityStatus.ACTIVE)
        res = await session.execute(stmt)
        items = list(res.scalars().all())
        return {item.key: item.value for item in items}

    async def save(self, session: AsyncSession, pref: MasterPreference) -> MasterPreference:
        session.add(pref)
        await session.flush()
        await session.refresh(pref)
        return pref

    async def search(
        self,
        session: AsyncSession,
        filter_obj: PreferenceFilter,
    ) -> PageResult[MasterPreference]:
        stmt = select(MasterPreference)

        if filter_obj.status is not None:
            stmt = stmt.where(MasterPreference.status == filter_obj.status)

        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(MasterPreference.key.ilike(term))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "createdAt"
        sort_dir = filter_obj.sortDir or "desc"
        sort_col = getattr(MasterPreference, sort_by, MasterPreference.createdAt)
        order_clause = desc(sort_col) if sort_dir.lower() == "desc" else asc(sort_col)

        offset = filter_obj.page * filter_obj.limit
        stmt = stmt.order_by(order_clause).offset(offset).limit(filter_obj.limit)

        result = await session.execute(stmt)
        items = list(result.scalars().all())
        total_pages = math.ceil(total_items / filter_obj.limit) if filter_obj.limit > 0 else 0

        return PageResult(
            list=items,
            page=filter_obj.page,
            limit=filter_obj.limit,
            totalItems=total_items,
            totalPages=total_pages,
        )
