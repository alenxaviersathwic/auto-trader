import math
from typing import List, Optional
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_conversation_entity import MasterConversation


class ConversationFilter(BaseFilter):
    archived: Optional[bool] = None


class ConversationRepository:
    async def get_by_id(
        self,
        session: AsyncSession,
        conversation_id: int,
        status: Optional[EntityStatus] = EntityStatus.ACTIVE,
    ) -> Optional[MasterConversation]:
        stmt = select(MasterConversation).where(MasterConversation.id == conversation_id)
        if status is not None:
            stmt = stmt.where(MasterConversation.status == status)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, session: AsyncSession, conversation: MasterConversation) -> MasterConversation:
        session.add(conversation)
        await session.flush()
        await session.commit()
        await session.refresh(conversation)
        return conversation

    async def search(
        self,
        session: AsyncSession,
        filter_obj: ConversationFilter,
    ) -> PageResult[MasterConversation]:
        stmt = select(MasterConversation)

        if filter_obj.status is not None:
            stmt = stmt.where(MasterConversation.status == filter_obj.status)

        if filter_obj.archived is not None:
            stmt = stmt.where(MasterConversation.archived.is_(filter_obj.archived))

        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(MasterConversation.title.ilike(term))

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(MasterConversation.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(MasterConversation.createdAt <= filter_obj.dateFilter.to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        # Sortable: lastMessageAt, createdAt
        sort_by = filter_obj.sortBy or "lastMessageAt"
        sort_dir = filter_obj.sortDir or "desc"
        sort_col = getattr(MasterConversation, sort_by, MasterConversation.lastMessageAt)
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
