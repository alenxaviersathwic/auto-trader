from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class DeskDecision(BaseEntity):
    """One Commodity Desk decision on one commodity: every sub-agent's report, the setups on the table, what the risk
    gate refused, and the head trader's decision with its written reasoning. A TAKE becomes a normal opportunity on
    the next scan (if the setup still holds); `outcome` records what happened to it there."""

    __tablename__ = "commodity_desk_decisions"

    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False, index=True)
    decidedAt: Mapped[datetime] = mapped_column("decided_at", DateTime(timezone=True), nullable=False, index=True)
    phase: Mapped[str] = mapped_column("phase", String(12), nullable=False)
    spot: Mapped[float | None] = mapped_column("spot", Float, nullable=True)
    decision: Mapped[str] = mapped_column("decision", String(8), nullable=False)  # TAKE | WAIT
    source: Mapped[str] = mapped_column("source", String(8), nullable=False)  # LLM | CODE
    setupName: Mapped[str | None] = mapped_column("setup_name", String(40), nullable=True)
    side: Mapped[str | None] = mapped_column("side", String(2), nullable=True)
    conviction: Mapped[int] = mapped_column("conviction", Integer, nullable=False, default=0)
    thinking: Mapped[str] = mapped_column("thinking", Text, nullable=False, default="")
    watchFor: Mapped[str] = mapped_column("watch_for", String(300), nullable=False, default="")
    agents: Mapped[dict[str, Any]] = mapped_column("agents", JSONB, nullable=False, default=dict)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column("candidates", JSONB, nullable=False, default=list)
    chosen: Mapped[dict[str, Any] | None] = mapped_column("chosen", JSONB, nullable=True)
    outcome: Mapped[str | None] = mapped_column("outcome", String(200), nullable=True)
