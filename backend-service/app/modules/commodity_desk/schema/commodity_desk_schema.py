from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.filter.base_filter import BaseFilter


class DeskDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    underlyingCode: str
    decidedAt: datetime
    phase: str
    spot: Optional[float] = None
    decision: str
    source: str
    setupName: Optional[str] = None
    side: Optional[str] = None
    conviction: int
    thinking: str
    watchFor: str
    agents: dict[str, Any]
    candidates: list[dict[str, Any]]
    chosen: Optional[dict[str, Any]] = None
    outcome: Optional[str] = None
    createdAt: datetime


class MarketMoveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    underlyingCode: str
    underlyingType: str
    detectedAt: datetime
    direction: str
    windowMin: int
    priceFrom: float
    priceTo: float
    movePct: float
    moveAtr: float
    newsState: str
    cause: Optional[str] = None
    summary: Optional[str] = None
    headlines: list[dict[str, Any]]
    source: Optional[str] = None
    createdAt: datetime


class DeskDecisionSearchFilter(BaseFilter):
    underlyingCode: Optional[str] = Field(default=None, description="Only this commodity")
    decision: Optional[str] = Field(default=None, description="TAKE | WAIT")


class MarketMoveSearchFilter(BaseFilter):
    underlyingCode: Optional[str] = Field(default=None, description="Only this underlying")


class DeskLatestResponse(BaseModel):
    """The newest decision per commodity, and the moves of the last few hours."""

    decisions: list[DeskDecisionResponse]
    moves: list[MarketMoveResponse]


class DeskLiveItem(BaseModel):
    """One commodity's desk right now (in-memory status of this process)."""

    code: str
    passAt: Optional[datetime] = None
    passNo: int = 0
    passMs: float = 0.0
    stances: dict[str, str] = Field(default_factory=dict)
    allowed: int = 0
    refused: int = 0
    thinkingSince: Optional[datetime] = None
    decidedAt: Optional[datetime] = None
    lastDecision: Optional[str] = None
    sentAt: Optional[datetime] = None


class NewsCheckItem(BaseModel):
    code: str
    since: datetime
    step: str
    direction: str
    pct: float
    headlines: Optional[int] = None


class DeskLiveResponse(BaseModel):
    serverTime: datetime
    desks: list[DeskLiveItem]
    newsChecks: list[NewsCheckItem]
