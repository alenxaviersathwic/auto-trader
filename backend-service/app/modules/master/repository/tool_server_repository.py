import math
from typing import List, Optional
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_tool_policy_entity import MasterToolPolicy
from app.modules.master.entity.master_tool_server_entity import MasterToolServer


class ToolServerFilter(BaseFilter):
    enabled: Optional[bool] = None


class ToolPolicyFilter(BaseFilter):
    serverName: Optional[str] = None
    tier: Optional[str] = None
    enabled: Optional[bool] = None


class ToolServerRepository:
    async def get_by_id(
        self,
        session: AsyncSession,
        server_id: int,
        status: EntityStatus = EntityStatus.ACTIVE,
    ) -> Optional[MasterToolServer]:
        stmt = select(MasterToolServer).where(MasterToolServer.id == server_id, MasterToolServer.status == status)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_name(
        self,
        session: AsyncSession,
        name: str,
        status: EntityStatus = EntityStatus.ACTIVE,
    ) -> Optional[MasterToolServer]:
        stmt = select(MasterToolServer).where(MasterToolServer.name == name, MasterToolServer.status == status)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def save(self, session: AsyncSession, server: MasterToolServer) -> MasterToolServer:
        session.add(server)
        await session.flush()
        await session.refresh(server)
        return server

    async def search(
        self,
        session: AsyncSession,
        filter_obj: ToolServerFilter,
    ) -> PageResult[MasterToolServer]:
        stmt = select(MasterToolServer)

        if filter_obj.status is not None:
            stmt = stmt.where(MasterToolServer.status == filter_obj.status)
        if filter_obj.enabled is not None:
            stmt = stmt.where(MasterToolServer.enabled.is_(filter_obj.enabled))
        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(MasterToolServer.name.ilike(term))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "name"
        sort_dir = filter_obj.sortDir or "asc"
        sort_col = getattr(MasterToolServer, sort_by, MasterToolServer.name)
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

    # Tool Policy operations
    async def get_policy(
        self,
        session: AsyncSession,
        server_name: str,
        tool_name: str,
    ) -> Optional[MasterToolPolicy]:
        stmt = select(MasterToolPolicy).where(
            MasterToolPolicy.serverName == server_name,
            MasterToolPolicy.toolName == tool_name,
            MasterToolPolicy.status == EntityStatus.ACTIVE,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_policy_by_id(
        self,
        session: AsyncSession,
        policy_id: int,
    ) -> Optional[MasterToolPolicy]:
        stmt = select(MasterToolPolicy).where(MasterToolPolicy.id == policy_id, MasterToolPolicy.status == EntityStatus.ACTIVE)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_policy(self, session: AsyncSession, policy: MasterToolPolicy) -> MasterToolPolicy:
        session.add(policy)
        await session.flush()
        await session.refresh(policy)
        return policy

    async def search_policies(
        self,
        session: AsyncSession,
        filter_obj: ToolPolicyFilter,
    ) -> PageResult[MasterToolPolicy]:
        stmt = select(MasterToolPolicy)

        if filter_obj.status is not None:
            stmt = stmt.where(MasterToolPolicy.status == filter_obj.status)
        if filter_obj.serverName:
            stmt = stmt.where(MasterToolPolicy.serverName == filter_obj.serverName)
        if filter_obj.tier:
            stmt = stmt.where(MasterToolPolicy.tier == filter_obj.tier)
        if filter_obj.enabled is not None:
            stmt = stmt.where(MasterToolPolicy.enabled.is_(filter_obj.enabled))
        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(MasterToolPolicy.toolName.ilike(term))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "toolName"
        sort_dir = filter_obj.sortDir or "asc"
        sort_col = getattr(MasterToolPolicy, sort_by, MasterToolPolicy.toolName)
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
