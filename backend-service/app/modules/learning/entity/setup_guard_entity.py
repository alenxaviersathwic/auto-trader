from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class SetupGuard(BaseEntity):
    """A restriction learned from repeated autopsy failures on one setup (service/learning_rules.py). The engine
    enforces it only while guardState is APPLIED. Mirrored to the Rules module as an AUTOPSY rule (ruleId)."""

    __tablename__ = "setup_guards"

    setup: Mapped[str] = mapped_column("setup", String(100), nullable=False, index=True)
    guardType: Mapped[str] = mapped_column("guard_type", String(24), nullable=False)
    tag: Mapped[str] = mapped_column("tag", String(24), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column("params", JSONB, nullable=False, default=dict)
    text: Mapped[str] = mapped_column("text", String(300), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column("evidence", JSONB, nullable=False, default=dict)
    guardState: Mapped[str] = mapped_column("guard_state", String(10), nullable=False, default="PROPOSED")
    decidedAt: Mapped[datetime | None] = mapped_column("decided_at", DateTime(timezone=True), nullable=True)
    ruleId: Mapped[int | None] = mapped_column("rule_id", BigInteger, nullable=True)
