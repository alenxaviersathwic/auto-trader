from typing import Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.modules.master.entity.master_run_entity import MasterRun


class RunRepository:
    async def get_by_id(
        self,
        session: AsyncSession,
        run_id: int,
    ) -> Optional[MasterRun]:
        stmt = select(MasterRun).where(MasterRun.id == run_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_run_for_conversation(
        self,
        session: AsyncSession,
        conversation_id: int,
    ) -> Optional[MasterRun]:
        stmt = (
            select(MasterRun)
            .where(
                MasterRun.conversationId == conversation_id,
                MasterRun.state.in_(["RUNNING", "WAITING_USER"]),
                MasterRun.status == EntityStatus.ACTIVE,
            )
            .order_by(desc(MasterRun.id))
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def save(self, session: AsyncSession, run: MasterRun) -> MasterRun:
        session.add(run)
        await session.flush()
        await session.refresh(run)
        return run
