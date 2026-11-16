from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.filter.base_filter import BaseFilter


class NotificationResponse(BaseModel):
    """One notification. `id` grows by one per event, so a reconnecting stream can ask for what it missed."""

    id: int
    kind: str  # NEW_SUGGESTION | TRADE_LOCKED | TRADE_ENTERED | EXIT_SIGNAL | TRADE_EXITED | SESSION_HALTED | LEARNING | RESEARCH
    title: str
    body: str
    severity: str  # info | success | warning | danger
    sessionId: Optional[int] = None
    tradeId: Optional[int] = None
    link: Optional[str] = None
    data: dict[str, Any] = {}
    createdAt: datetime


class NotificationSearchFilter(BaseFilter):
    kind: Optional[str] = None
    sessionId: Optional[int] = None
    afterId: Optional[int] = Field(default=None, description="Only notifications with a larger id")
