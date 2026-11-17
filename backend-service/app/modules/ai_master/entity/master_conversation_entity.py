from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterConversation(BaseEntity):
    __tablename__ = "master_conversations"

    title: Mapped[str] = mapped_column("title", String(150), nullable=False, default="New Conversation")
    summary: Mapped[Optional[str]] = mapped_column("summary", Text, nullable=True)
    lastMessageAt: Mapped[datetime] = mapped_column("last_message_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    messageCount: Mapped[int] = mapped_column("message_count", Integer, default=0, nullable=False)
    createdByUserId: Mapped[Optional[int]] = mapped_column("created_by_user_id", nullable=True)
    archived: Mapped[bool] = mapped_column("archived", Boolean, default=False, nullable=False)
