from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.core.filter.base_filter import BaseFilter
from app.core.db.entity_status import EntityStatus


class StrategyFilter(BaseFilter):
    category: Optional[str] = None
    structure: Optional[str] = None
    bias: Optional[str] = None
    optionSide: Optional[str] = None
    market: Optional[str] = None
    underlyingType: Optional[str] = None
    exchange: Optional[str] = None
    tradingMode: Optional[str] = None
    executionMode: Optional[str] = None
    lifecycleStatus: Optional[str] = None
    health: Optional[str] = None
    validationStatus: Optional[str] = None
    definitionFormat: Optional[str] = None
    executable: Optional[bool] = None
    suggestable: Optional[bool] = None
    hasReviewFlags: Optional[bool] = None
    tag: Optional[str] = None
    source: Optional[str] = None


class StrategyVersionResponse(BaseModel):
    id: int
    strategyId: int
    versionNo: int
    schemaVersion: int
    definition: Dict[str, Any]
    contentHash: str
    changeNote: Optional[str] = None
    createdAt: datetime
    status: Union[EntityStatus, int]

    model_config = {"populate_by_name": True, "from_attributes": True}


class PerformanceSnapshotSummary(BaseModel):
    id: int
    source: str
    domain: str
    totalTrades: int
    winningTrades: int
    losingTrades: int
    winRatePct: Decimal
    netPnl: Decimal
    profitFactor: Decimal
    maxDrawdown: Decimal
    legacyHealth: Optional[str] = None
    reliabilityFlags: Optional[List[str]] = None
    createdAt: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}


class StrategyResponse(BaseModel):
    id: int
    createdAt: datetime
    status: Union[EntityStatus, int]
    code: str
    name: str
    description: Optional[str] = None
    category: str
    structure: Optional[str] = None
    bias: Optional[str] = None
    optionSide: Optional[str] = None
    markets: List[str]
    underlyingTypes: List[str]
    exchange: Optional[str] = None
    tradingModes: List[str]
    executionModes: List[str]
    timeframe: Optional[str] = None
    definitionFormat: str
    executable: bool
    lifecycleStatus: str
    health: str
    effectiveHealth: str
    healthOverride: Optional[str] = None
    healthOverrideReason: Optional[str] = None
    healthOverrideUntil: Optional[datetime] = None
    validationStatus: str
    enabled: bool
    riskProfile: Optional[Dict[str, Any]] = None
    references: Optional[List[Dict[str, Any]]] = None
    riskNotes: Optional[List[str]] = None
    howItWorks: Optional[List[Dict[str, str]]] = None
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    reviewFlags: Optional[List[str]] = None
    currentVersionId: Optional[int] = None
    suggestable: bool = False
    latestSnapshot: Optional[PerformanceSnapshotSummary] = None

    model_config = {"populate_by_name": True, "from_attributes": True}


class StrategyDetailResponse(StrategyResponse):
    currentVersion: Optional[StrategyVersionResponse] = None
    snapshotsBySource: Optional[Dict[str, PerformanceSnapshotSummary]] = None


class StrategyCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    category: str
    structure: Optional[str] = None
    bias: Optional[str] = None
    optionSide: Optional[str] = None
    markets: List[str] = Field(default_factory=list)
    underlyingTypes: List[str] = Field(default_factory=list)
    exchange: Optional[str] = None
    tradingModes: List[str] = Field(default_factory=list)
    executionModes: List[str] = Field(default_factory=list)
    timeframe: Optional[str] = None
    definitionFormat: str = "RULE_TREE"
    definition: Dict[str, Any]
    riskProfile: Optional[Dict[str, Any]] = None
    references: Optional[List[Dict[str, Any]]] = None
    riskNotes: Optional[List[str]] = None
    howItWorks: Optional[List[Dict[str, str]]] = None
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    changeNote: Optional[str] = "Initial version"


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    structure: Optional[str] = None
    bias: Optional[str] = None
    optionSide: Optional[str] = None
    markets: Optional[List[str]] = None
    underlyingTypes: Optional[List[str]] = None
    exchange: Optional[str] = None
    tradingModes: Optional[List[str]] = None
    executionModes: Optional[List[str]] = None
    timeframe: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    riskProfile: Optional[Dict[str, Any]] = None
    references: Optional[List[Dict[str, Any]]] = None
    riskNotes: Optional[List[str]] = None
    howItWorks: Optional[List[Dict[str, str]]] = None
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    changeNote: Optional[str] = None


class StrategyLifecycleUpdate(BaseModel):
    to: str = Field(..., description="Target lifecycleStatus: DRAFT, IN_REVIEW, ACTIVE, SUSPENDED, ARCHIVED")
    reason: Optional[str] = None


class StrategyEnabledUpdate(BaseModel):
    enabled: bool


class StrategyVersionFilter(BaseFilter):
    pass


class ValidationIssue(BaseModel):
    path: str
    level: str  # ERROR, WARNING
    message: str


class ValidateDefinitionRequest(BaseModel):
    format: str = "RULE_TREE"
    definition: Dict[str, Any]


class ValidateDefinitionResponse(BaseModel):
    valid: bool
    executable: bool
    issues: List[ValidationIssue] = Field(default_factory=list)


class EvaluateStrategyRequest(BaseModel):
    versionId: Optional[int] = None
    definition: Optional[Dict[str, Any]] = None
    context: Dict[str, Any]


class ConditionEvalResult(BaseModel):
    path: str
    condition: str
    passed: bool
    leftValue: Any = None
    rightValue: Any = None


class AdjustmentEvalResult(BaseModel):
    key: str
    triggered: bool
    actions: List[Dict[str, Any]] = Field(default_factory=list)


class EvaluateStrategyResponse(BaseModel):
    entryMet: bool
    exitMet: bool
    activeCaseKey: Optional[str] = None
    conditions: List[ConditionEvalResult] = Field(default_factory=list)
    adjustments: List[AdjustmentEvalResult] = Field(default_factory=list)
    targetLegs: List[Dict[str, Any]] = Field(default_factory=list)


class OperandRequirement(BaseModel):
    source: str
    field: Optional[str] = None
    code: Optional[str] = None
    output: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    timeframe: Optional[str] = None
    bar: Optional[str] = None
    required: bool = True


class RequirementsResponse(BaseModel):
    strategyId: int
    versionNo: int
    requirements: List[OperandRequirement] = Field(default_factory=list)
