from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.filter.base_filter import BaseFilter


class TradeAutopsyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tradeId: int
    sessionId: int
    setup: str
    managerCode: str
    traderCode: Optional[str] = None
    underlyingCode: str
    optionType: str
    outcome: str
    verdict: str
    rMultiple: float
    mfeR: float
    maeR: float
    givebackPct: Optional[float] = None
    netPnl: float
    plannedTargetPct: Optional[float] = None
    tags: list[str]
    wentRight: list[str]
    wentWrong: list[str]
    lessons: list[str]
    details: dict[str, Any]
    learning: dict[str, Any]
    createdAt: datetime


class SetupScorecardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    setup: str
    managerCode: str
    policy: Optional[str] = None
    closedTrades: int
    wins: int
    losses: int
    netPnl: float
    avgR: float
    winRatePct: float
    expectancy: float
    scoreStatus: str
    statusReason: Optional[str] = None
    pausedAt: Optional[datetime] = None
    resumedAt: Optional[datetime] = None
    lastTradeId: Optional[int] = None
    updatedAt: Optional[datetime] = None


class SetupGuardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    setup: str
    managerCode: str
    guardType: str
    tag: str
    params: dict[str, Any]
    text: str
    evidence: dict[str, Any]
    guardState: str
    decidedAt: Optional[datetime] = None
    ruleId: Optional[int] = None
    createdAt: datetime


MANAGER_FILTER = "The session manager whose autopsy sub-agent owns the row: FIB_GOLDEN_TRADER | FLOW_MOMENTUM_TRADER"


class AutopsySearchFilter(BaseFilter):
    managerCode: Optional[str] = Field(default=None, description=MANAGER_FILTER)
    sessionId: Optional[int] = None
    setup: Optional[str] = None
    outcome: Optional[str] = Field(default=None, description="WIN | LOSS")


class ScorecardSearchFilter(BaseFilter):
    sortBy: Optional[str] = Field(default="netPnl")
    managerCode: Optional[str] = Field(default=None, description=MANAGER_FILTER)
    scoreStatus: Optional[str] = Field(default=None, description="ACTIVE | PAUSED")


class GuardSearchFilter(BaseFilter):
    managerCode: Optional[str] = Field(default=None, description=MANAGER_FILTER)
    setup: Optional[str] = None
    guardState: Optional[str] = Field(default=None, description="PROPOSED | APPLIED | REJECTED")
