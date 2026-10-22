import math
from typing import Optional
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.pagination.page_result import PageResult
from app.modules.strategies.entity.import_batch_entity import ImportBatch
from app.modules.strategies.schema.import_schema import ImportFilter


class ImportRepository:
    """Repository handling database operations for ImportBatch."""

    async def get_by_id(
        self,
        session: AsyncSession,
        batch_id: int,
    ) -> Optional[ImportBatch]:
        stmt = select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.status == EntityStatus.ACTIVE)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        session: AsyncSession,
        filter_obj: ImportFilter,
    ) -> PageResult[ImportBatch]:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        stmt = select(ImportBatch).where(ImportBatch.status == target_status)

        if filter_obj.sourceFormat:
            stmt = stmt.where(ImportBatch.sourceFormat == filter_obj.sourceFormat)
        if filter_obj.dryRun is not None:
            stmt = stmt.where(ImportBatch.dryRun.is_(filter_obj.dryRun))
        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            stmt = stmt.where(ImportBatch.fileName.ilike(term))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total_items = total_res.scalar_one_or_none() or 0

        stmt = stmt.order_by(desc(ImportBatch.createdAt))
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

    async def save(self, session: AsyncSession, batch: ImportBatch) -> ImportBatch:
        session.add(batch)
        await session.flush()
        return batch
