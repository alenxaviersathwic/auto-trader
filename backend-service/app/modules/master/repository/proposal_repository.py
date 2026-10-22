import math
from typing import Optional
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.filter.base_filter import BaseFilter
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_proposal_entity import MasterProposal


class ProposalFilter(BaseFilter):
    conversationId: Optional[int] = None
    kind: Optional[str] = None
    targetCode: Optional[str] = None
    proposalStatus: Optional[str] = None


class ProposalRepository:
    async def get_by_id(
        self,
        session: AsyncSession,
        proposal_id: int,
        status: Optional[EntityStatus] = EntityStatus.ACTIVE,
    ) -> Optional[MasterProposal]:
        stmt = select(MasterProposal).where(MasterProposal.id == proposal_id)
        if status is not None:
            stmt = stmt.where(MasterProposal.status == status)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def save(self, session: AsyncSession, proposal: MasterProposal) -> MasterProposal:
        session.add(proposal)
        await session.flush()
        await session.refresh(proposal)
        return proposal

    async def search(
        self,
        session: AsyncSession,
        filter_obj: ProposalFilter,
    ) -> PageResult[MasterProposal]:
        stmt = select(MasterProposal)

        if filter_obj.status is not None:
            stmt = stmt.where(MasterProposal.status == filter_obj.status)
        if filter_obj.conversationId is not None:
            stmt = stmt.where(MasterProposal.conversationId == filter_obj.conversationId)
        if filter_obj.kind:
            stmt = stmt.where(MasterProposal.kind == filter_obj.kind)
        if filter_obj.targetCode:
            stmt = stmt.where(MasterProposal.targetCode == filter_obj.targetCode)
        if filter_obj.proposalStatus:
            stmt = stmt.where(MasterProposal.proposalStatus == filter_obj.proposalStatus)

        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                stmt = stmt.where(MasterProposal.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                stmt = stmt.where(MasterProposal.createdAt <= filter_obj.dateFilter.to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "createdAt"
        sort_dir = filter_obj.sortDir or "desc"
        sort_col = getattr(MasterProposal, sort_by, MasterProposal.createdAt)
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
