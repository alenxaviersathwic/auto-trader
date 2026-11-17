from typing import Any, Dict, List, Optional
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterMessage(BaseEntity):
    __tablename__ = "master_messages"

    conversationId: Mapped[int] = mapped_column("conversation_id", BigInteger, ForeignKey("master_conversations.id"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column("seq", Integer, nullable=False)
    role: Mapped[str] = mapped_column("role", String(10), nullable=False)  # USER, ASSISTANT, SYSTEM
    content: Mapped[str] = mapped_column("content", Text, nullable=False)
    blocks: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column("blocks", JSONB, nullable=True)
    runId: Mapped[Optional[int]] = mapped_column("run_id", BigInteger, ForeignKey("master_runs.id", use_alter=True), nullable=True, index=True)
    redacted: Mapped[bool] = mapped_column("redacted", Boolean, default=False, nullable=False)
    model: Mapped[Optional[str]] = mapped_column("model", String(80), nullable=True)
    tokensIn: Mapped[Optional[int]] = mapped_column("tokens_in", Integer, nullable=True)
    tokensOut: Mapped[Optional[int]] = mapped_column("tokens_out", Integer, nullable=True)
    latencyMs: Mapped[Optional[int]] = mapped_column("latency_ms", Integer, nullable=True)
