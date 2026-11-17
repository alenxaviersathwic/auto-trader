import math

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.opportunity_finder.entity.opportunity_finder_entity import OpportunityFinder
from app.modules.opportunity_finder.schema.opportunity_finder_schema import OpportunityFinderSearchFilter

SORTS = {"createdAt", "sortOrder", "name", "code"}


class OpportunityFinderRepository:
    async def save(self, session: AsyncSession, row: OpportunityFinder) -> OpportunityFinder:
        session.add(row)
        await session.flush()
        return row

    async def get_by_code(self, session: AsyncSession, code: str) -> OpportunityFinder | None:
        res = await session.execute(select(OpportunityFinder).where(
            OpportunityFinder.status == EntityStatus.ACTIVE, OpportunityFinder.code == code.upper()))
        return res.scalar_one_or_none()

    async def list_active(self, session: AsyncSession) -> list[OpportunityFinder]:
        res = await session.execute(select(OpportunityFinder).where(OpportunityFinder.status == EntityStatus.ACTIVE)
                                    .order_by(OpportunityFinder.sortOrder, OpportunityFinder.id))
        return list(res.scalars().all())

    async def search(self, session: AsyncSession, f: OpportunityFinderSearchFilter) -> PageResult[OpportunityFinder]:
        stmt = select(OpportunityFinder).where(OpportunityFinder.status == (f.status or EntityStatus.ACTIVE))
        if f.dateFilter:
            if f.dateFilter.from_ is not None and f.dateFilter.to is not None and f.dateFilter.from_ > f.dateFilter.to:
                raise ValidationException(message="dateFilter.from must not be later than dateFilter.to")
            if f.dateFilter.from_ is not None:
                stmt = stmt.where(OpportunityFinder.createdAt >= f.dateFilter.from_)
            if f.dateFilter.to is not None:
                stmt = stmt.where(OpportunityFinder.createdAt <= f.dateFilter.to)
        if f.query:
            q = f"%{f.query}%"
            stmt = stmt.where(OpportunityFinder.name.ilike(q) | OpportunityFinder.code.ilike(q))
        if f.optionType:
            stmt = stmt.where(OpportunityFinder.optionTypes.contains([f.optionType.upper()]))
        if f.enabled is not None:
            stmt = stmt.where(OpportunityFinder.enabled == f.enabled)
        total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one_or_none() or 0
        sort_by = f.sortBy or "sortOrder"
        if sort_by not in SORTS:
            raise ValidationException(message=f"Invalid sortBy '{sort_by}'. Allowed: {sorted(SORTS)}")
        col = getattr(OpportunityFinder, sort_by)
        stmt = stmt.order_by(desc(col) if (f.sortDir or "asc") == "desc" else asc(col), OpportunityFinder.id)
        rows = list((await session.execute(stmt.offset(f.page * f.limit).limit(f.limit))).scalars().all())
        return PageResult(list=rows, page=f.page, limit=f.limit,
                          totalPages=math.ceil(total / f.limit) if total else 0, totalItems=total)


opportunity_finder_repository = OpportunityFinderRepository()
