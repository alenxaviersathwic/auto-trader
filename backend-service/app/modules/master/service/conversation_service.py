from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import NotFoundException
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_conversation_entity import MasterConversation
from app.modules.master.repository.conversation_repository import ConversationFilter, ConversationRepository


class ConversationService:
    """Manages master chat conversations."""

    def __init__(self, repo: Optional[ConversationRepository] = None):
        self.repo = repo or ConversationRepository()

    async def create(self, session: AsyncSession, title: Optional[str] = None) -> MasterConversation:
        conv = MasterConversation(
            title=title or "New Conversation",
            messageCount=0,
            archived=False,
            lastMessageAt=datetime.now(timezone.utc),
        )
        return await self.repo.save(session, conv)

    async def get_by_id(self, session: AsyncSession, conv_id: int) -> MasterConversation:
        conv = await self.repo.get_by_id(session, conv_id)
        if not conv:
            raise NotFoundException(message=f"Conversation #{conv_id} not found")
        return conv

    async def search(self, session: AsyncSession, filter_obj: ConversationFilter) -> PageResult[MasterConversation]:
        return await self.repo.search(session, filter_obj)

    async def update(
        self,
        session: AsyncSession,
        conv_id: int,
        title: Optional[str] = None,
        archived: Optional[bool] = None,
    ) -> MasterConversation:
        conv = await self.get_by_id(session, conv_id)
        if title is not None:
            conv.title = title
        if archived is not None:
            conv.archived = archived
        return await self.repo.save(session, conv)

    async def delete(self, session: AsyncSession, conv_id: int) -> None:
        conv = await self.get_by_id(session, conv_id)
        conv.status = EntityStatus.DELETED
        await self.repo.save(session, conv)
