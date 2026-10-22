from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.core.filter.base_filter import BaseFilter
from app.core.db.entity_status import EntityStatus


class PerformanceSnapshotFilter(BaseFilter):
    strategyId: Optional[int] = None
    source: Optional[str] = None
    domain: Optional[str] = None


class PerformanceSnapshotCreate(BaseModel):
    versionNo: Optional[int] = None
    source: str = Field(..., description="PAPER, LIVE, BACKTEST")
    domain: str = Field(default="UNKNOWN", description="PAPER, LIVE, UNKNOWN")
    periodFrom: Optional[date] = None
    periodTo: Optional[date] = None
    asOf: Optional[datetime] = None
    totalTrades: int = Field(ge=0)
    winningTrades: int = Field(ge=0)
    losingTrades: int = Field(ge=0)
    winRatePct: Decimal
    netPnl: Decimal
    profitFactor: Decimal
    maxDrawdown: Decimal
    legacyHealth: Optional[str] = None


class PerformanceSnapshotResponse(BaseModel):
    id: int
    createdAt: datetime
    status: Union[EntityStatus, int]
    strategyId: int
    versionNo: Optional[int] = None
    source: str
    domain: str
    periodFrom: Optional[date] = None
    periodTo: Optional[date] = None
    asOf: Optional[datetime] = None
    totalTrades: int
    winningTrades: int
    losingTrades: int
    winRatePct: Decimal
    netPnl: Decimal
    profitFactor: Decimal
    maxDrawdown: Decimal
    legacyHealth: Optional[str] = None
    reliabilityFlags: Optional[List[str]] = None

    model_config = {"populate_by_name": True, "from_attributes": True}


class HealthEventResponse(BaseModel):
    id: int
    createdAt: datetime
    status: Union[EntityStatus, int]
    strategyId: int
    fromHealth: str
    toHealth: str
    reason: str
    snapshotId: Optional[int] = None
    triggeredBy: str

    model_config = {"populate_by_name": True, "from_attributes": True}


class HealthEventFilter(BaseFilter):
    strategyId: Optional[int] = None
    toHealth: Optional[str] = None
    triggeredBy: Optional[str] = None


class HealthResponse(BaseModel):
    strategyId: int
    health: str
    effectiveHealth: str
    healthOverride: Optional[str] = None
    healthOverrideReason: Optional[str] = None
    healthOverrideUntil: Optional[datetime] = None
    policyUsed: Optional[Dict[str, Any]] = None
    recentEvents: List[HealthEventResponse] = Field(default_factory=list)


class HealthOverrideRequest(BaseModel):
    health: str = Field(..., description="HEALTHY, DEGRADED, SUSPENDED, UNKNOWN")
    reason: str = Field(..., description="Mandatory reason for override")
    until: Optional[datetime] = None


class RecomputeHealthResponse(BaseModel):
    recomputedCount: int
    changedCount: int
    details: List[Dict[str, Any]] = Field(default_factory=list)


class HealthPolicyFilter(BaseFilter):
    enabled: Optional[bool] = None


class HealthPolicyCreate(BaseModel):
    code: str
    name: str
    scope: Any = Field(default="ALL")
    params: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class HealthPolicyUpdate(BaseModel):
    name: Optional[str] = None
    scope: Optional[Any] = None
    params: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class HealthPolicyResponse(BaseModel):
    id: int
    createdAt: datetime
    status: Union[EntityStatus, int]
    code: str
    name: str
    scope: Any
    params: Dict[str, Any]
    enabled: bool

    model_config = {"populate_by_name": True, "from_attributes": True}
