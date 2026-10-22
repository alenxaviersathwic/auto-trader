from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterProposal(BaseEntity):
    __tablename__ = "master_proposals"

    conversationId: Mapped[int] = mapped_column("conversation_id", BigInteger, ForeignKey("master_conversations.id"), nullable=False, index=True)
    messageId: Mapped[Optional[int]] = mapped_column("message_id", BigInteger, ForeignKey("master_messages.id"), nullable=True)
    kind: Mapped[str] = mapped_column("kind", String(30), nullable=False)
    targetType: Mapped[Optional[str]] = mapped_column("target_type", String(30), nullable=True)
    targetCode: Mapped[Optional[str]] = mapped_column("target_code", String(100), nullable=True)
    userText: Mapped[str] = mapped_column("user_text", Text, nullable=False)
    backTranslation: Mapped[str] = mapped_column("back_translation", Text, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column("payload", JSONB, nullable=False)
    diff: Mapped[Optional[Dict[str, Any]]] = mapped_column("diff", JSONB, nullable=True)
    complications: Mapped[List[Dict[str, Any]]] = mapped_column("complications", JSONB, nullable=False, default=list)
    assumptions: Mapped[List[str]] = mapped_column("assumptions", JSONB, nullable=False, default=list)
    structureAnalysis: Mapped[Optional[Dict[str, Any]]] = mapped_column("structure_analysis", JSONB, nullable=True)
    validation: Mapped[Optional[Dict[str, Any]]] = mapped_column("validation", JSONB, nullable=True)
    contentHash: Mapped[str] = mapped_column("content_hash", String(64), nullable=False)
    proposalStatus: Mapped[str] = mapped_column("proposal_status", String(15), nullable=False, default="PENDING")  # PENDING, CONFIRMED, REJECTED, EXPIRED, SUPERSEDED, FAILED
    expiresAt: Mapped[datetime] = mapped_column("expires_at", DateTime(timezone=True), nullable=False)
    confirmedAt: Mapped[Optional[datetime]] = mapped_column("confirmed_at", DateTime(timezone=True), nullable=True)
    confirmMode: Mapped[Optional[str]] = mapped_column("confirm_mode", String(25), nullable=True)
    resultRefs: Mapped[Optional[Dict[str, Any]]] = mapped_column("result_refs", JSONB, nullable=True)
    failureReason: Mapped[Optional[str]] = mapped_column("failure_reason", String(500), nullable=True)
