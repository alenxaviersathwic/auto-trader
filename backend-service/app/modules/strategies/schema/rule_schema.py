from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.core.filter.base_filter import BaseFilter
from app.core.db.entity_status import EntityStatus


class RuleFilter(BaseFilter):
    ruleKind: Optional[str] = None
    ruleType: Optional[str] = None
    action: Optional[str] = None
    priority: Optional[str] = None
    market: Optional[str] = None
    optionSide: Optional[str] = None
    executionDomain: Optional[str] = None
    executable: Optional[bool] = None
    stale: Optional[bool] = None
    enabled: Optional[bool] = None


class RuleVersionResponse(BaseModel):
    id: int
    ruleId: int
    versionNo: int
    content: Dict[str, Any]
    changeNote: Optional[str] = None
    createdAt: datetime
    status: Union[EntityStatus, int]

    model_config = {"populate_by_name": True, "from_attributes": True}


class RuleResponse(BaseModel):
    id: int
    createdAt: datetime
    status: Union[EntityStatus, int]
    code: str
    name: str
    ruleKind: str
    ruleType: str
    action: Optional[str] = None
    priority: str
    appliesTo: Dict[str, Any]
    conditionText: str
    currentVersionId: Optional[int] = None
    evidence: Optional[Dict[str, Any]] = None
    reviewBy: Optional[date] = None
    executable: bool
    reviewFlags: Optional[List[str]] = None
    provenance: Optional[Dict[str, Any]] = None
    enabled: bool
    isStale: bool = False

    model_config = {"populate_by_name": True, "from_attributes": True}


class StrategyUsageSummary(BaseModel):
    strategyId: int
    code: str
    name: str
    role: str


class RuleDetailResponse(RuleResponse):
    currentVersion: Optional[RuleVersionResponse] = None
    usedInStrategies: List[StrategyUsageSummary] = Field(default_factory=list)


class RuleCreate(BaseModel):
    code: str
    name: str
    ruleKind: str = "GUARDRAIL"
    ruleType: str
    action: Optional[str] = None
    priority: str = "MEDIUM"
    appliesTo: Dict[str, Any] = Field(default_factory=dict)
    conditionText: str
    content: Dict[str, Any]
    evidence: Optional[Dict[str, Any]] = None
    reviewBy: Optional[date] = None
    provenance: Optional[Dict[str, Any]] = None
    changeNote: Optional[str] = "Initial rule version"


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    action: Optional[str] = None
    priority: Optional[str] = None
    appliesTo: Optional[Dict[str, Any]] = None
    conditionText: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    reviewBy: Optional[date] = None
    enabled: Optional[bool] = None
    changeNote: Optional[str] = None


class RuleVersionFilter(BaseFilter):
    pass


class CheckRulesRequest(BaseModel):
    context: Dict[str, Any]
    includeStale: bool = False


class GuardrailCheckResult(BaseModel):
    ruleCode: str
    ruleName: str
    action: Optional[str]
    priority: str
    message: str
    met: Optional[bool]
    whenMet: bool
    unlessMet: bool
    requireMet: bool


class CheckRulesResponse(BaseModel):
    results: List[GuardrailCheckResult] = Field(default_factory=list)
    hasBlock: bool = False
    hasAvoid: bool = False
