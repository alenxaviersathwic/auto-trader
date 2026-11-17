from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class MarketMove(BaseEntity):
    """A sudden move on any scanned underlying (index or commodity) and the news sub-agent's explanation of it."""

    __tablename__ = "market_moves"

    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False, index=True)
    underlyingType: Mapped[str] = mapped_column("underlying_type", String(10), nullable=False)
    detectedAt: Mapped[datetime] = mapped_column("detected_at", DateTime(timezone=True), nullable=False, index=True)
    direction: Mapped[str] = mapped_column("direction", String(4), nullable=False)  # UP | DOWN
    windowMin: Mapped[int] = mapped_column("window_min", Integer, nullable=False)
    priceFrom: Mapped[float] = mapped_column("price_from", Float, nullable=False)
    priceTo: Mapped[float] = mapped_column("price_to", Float, nullable=False)
    movePct: Mapped[float] = mapped_column("move_pct", Float, nullable=False)
    moveAtr: Mapped[float] = mapped_column("move_atr", Float, nullable=False)
    newsState: Mapped[str] = mapped_column("news_state", String(12), nullable=False)  # PENDING | FOUND | UNCLEAR | NO_NEWS
    cause: Mapped[str | None] = mapped_column("cause", String(20), nullable=True)  # NEWS | NO_CLEAR_NEWS | UNCLEAR
    summary: Mapped[str | None] = mapped_column("summary", Text, nullable=True)
    headlines: Mapped[list[dict[str, Any]]] = mapped_column("headlines", JSONB, nullable=False, default=list)
    source: Mapped[str | None] = mapped_column("source", String(8), nullable=True)  # LLM | CODE
