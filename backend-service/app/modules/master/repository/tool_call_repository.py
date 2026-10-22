import math
from typing import Optional
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_tool_call_entity import MasterToolCall


class ToolCallFilter(BaseFilter):
    runId: Optional[int] = None
    serverName: Optional[str] = None
    toolName: Optional[str] = None
    tier: Optional[str] = None
    callStatus: Optional[str] = None


class ToolCallRepository:
    async def save(self, session: AsyncSession, call: MasterToolCall) -> MasterToolCall:
        session.add(call)
        await session.flush()
        await session.refresh(call)
        return call

    async def search(
        self,
        session: AsyncSession,
        filter_obj: ToolCallFilter,
    ) -> PageResult[MasterToolCall]:
        stmt = select(MasterToolCall)

        if filter_obj.runId is not None:
            stmt = stmt.where(MasterToolCall.runId == filter_obj.runId)
        if filter_obj.serverName:
            stmt = stmt.where(MasterToolCall.serverName == filter_obj.serverName)
        if filter_obj.toolName:
            stmt = stmt.where(MasterToolCall.toolName == filter_obj.toolName)
        if filter_obj.tier:
            stmt = stmt.where(MasterToolCall.tier == filter_obj.tier)
        if filter_obj.callStatus:
            stmt = stmt.where(MasterToolCall.callStatus == filter_obj.callStatus)

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(MasterToolCall.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(MasterToolCall.createdAt <= filter_obj.dateFilter.to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "createdAt"
        sort_dir = filter_obj.sortDir or "desc"
        sort_col = getattr(MasterToolCall, sort_by, MasterToolCall.createdAt)
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
