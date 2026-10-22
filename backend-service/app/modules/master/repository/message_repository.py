import math
from typing import List, Optional
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_message_entity import MasterMessage


class MessageFilter(BaseFilter):
    conversationId: Optional[int] = None


class MessageRepository:
    async def get_by_id(
        self,
        session: AsyncSession,
        message_id: int,
        status: Optional[EntityStatus] = EntityStatus.ACTIVE,
    ) -> Optional[MasterMessage]:
        stmt = select(MasterMessage).where(MasterMessage.id == message_id)
        if status is not None:
            stmt = stmt.where(MasterMessage.status == status)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_next_seq(self, session: AsyncSession, conversation_id: int) -> int:
        stmt = select(func.coalesce(func.max(MasterMessage.seq), 0) + 1).where(
            MasterMessage.conversationId == conversation_id
        )
        res = await session.execute(stmt)
        return res.scalar_one()

    async def save(self, session: AsyncSession, message: MasterMessage) -> MasterMessage:
        session.add(message)
        await session.flush()
        await session.refresh(message)
        return message

    async def get_recent_history(
        self,
        session: AsyncSession,
        conversation_id: int,
        limit: int = 20,
    ) -> List[MasterMessage]:
        stmt = (
            select(MasterMessage)
            .where(MasterMessage.conversationId == conversation_id, MasterMessage.status == EntityStatus.ACTIVE)
            .order_by(asc(MasterMessage.seq))
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def search(
        self,
        session: AsyncSession,
        conversation_id: int,
        filter_obj: MessageFilter,
    ) -> PageResult[MasterMessage]:
        stmt = select(MasterMessage).where(MasterMessage.conversationId == conversation_id)

        if filter_obj.status is not None:
            stmt = stmt.where(MasterMessage.status == filter_obj.status)

        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(MasterMessage.content.ilike(term))

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(MasterMessage.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(MasterMessage.createdAt <= filter_obj.dateFilter.to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "seq"
        sort_dir = filter_obj.sortDir or "asc"
        sort_col = getattr(MasterMessage, sort_by, MasterMessage.seq)
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
