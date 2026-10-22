from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterRun(BaseEntity):
    __tablename__ = "master_runs"

    conversationId: Mapped[int] = mapped_column("conversation_id", BigInteger, ForeignKey("master_conversations.id"), nullable=False, index=True)
    userMessageId: Mapped[Optional[int]] = mapped_column("user_message_id", BigInteger, nullable=True)
    state: Mapped[str] = mapped_column("state", String(15), nullable=False, default="RUNNING")  # RUNNING, WAITING_USER, COMPLETED, FAILED, CANCELLED
    intent: Mapped[Optional[str]] = mapped_column("intent", String(25), nullable=True)
    threadId: Mapped[str] = mapped_column("thread_id", String(60), nullable=False)
    iterations: Mapped[int] = mapped_column("iterations", Integer, default=0, nullable=False)
    toolCallCount: Mapped[int] = mapped_column("tool_call_count", Integer, default=0, nullable=False)
    clarificationRound: Mapped[int] = mapped_column("clarification_round", Integer, default=0, nullable=False)
    startedAt: Mapped[datetime] = mapped_column("started_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    finishedAt: Mapped[Optional[datetime]] = mapped_column("finished_at", DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column("error", String(500), nullable=True)
