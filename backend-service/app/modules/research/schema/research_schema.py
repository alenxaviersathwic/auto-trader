from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from app.core.filter.base_filter import BaseFilter


# --- Run Schemas ---
class StartRunRequest(BaseModel):
    scope: Optional[List[str]] = Field(default=None, description="e.g. ['INDEX', 'COMMODITY', 'STOCK']")
    windowHours: Optional[int] = Field(default=24, ge=6, le=48)
    topN: Optional[int] = Field(default=5, ge=1, le=20)
    maxDocsPerUnderlying: Optional[int] = Field(default=20, ge=5, le=50)


class ResearchRunFilter(BaseFilter):
    state: Optional[str] = None
    resultKind: Optional[str] = None
    triggerSource: Optional[str] = None


class RunEventFilter(BaseFilter):
    level: Optional[str] = None
    node: Optional[str] = None


# --- Results & Candidates Schemas ---
class ResearchCandidateFilter(BaseFilter):
    runId: Optional[int] = None
    scope: Optional[str] = None
    item: Optional[str] = None
    underlyingType: Optional[str] = None
    underlyingCode: Optional[str] = None
    newsStatus: Optional[str] = None
    suggested: Optional[bool] = None
    bearishWatch: Optional[bool] = None
    minScore: Optional[float] = None


class ResearchClaimFilter(BaseFilter):
    underlyingCode: Optional[str] = None
    stance: Optional[str] = None
    catalyst: Optional[str] = None
    origin: Optional[str] = None
    quoteVerified: Optional[bool] = None
    sinceHours: Optional[int] = None
    documentId: Optional[int] = None


class ResearchDocumentFilter(BaseFilter):
    domain: Optional[str] = None
    underlyingCode: Optional[str] = None
    fetchStatus: Optional[str] = None


class SemanticSearchRequest(BaseModel):
    query: str
    scope: Literal["CHUNKS", "CLAIMS", "BRIEFS"] = "CHUNKS"
    underlyingCode: Optional[str] = None
    sinceDays: Optional[int] = None
    topK: int = Field(default=10, ge=1, le=20)


# --- Setup & Entity Management Schemas ---
class ResearchUnderlyingFilter(BaseFilter):
    underlyingType: Optional[str] = None
    enabled: Optional[bool] = None


class CreateUnderlyingRequest(BaseModel):
    code: str
    name: str
    underlyingType: Literal["INDEX", "COMMODITY", "STOCK"]
    groupName: str
    exchange: str
    aliases: List[str] = []
    keywords: List[str] = []
    heavyweights: List[Dict[str, Any]] = []
    enabled: bool = True
    sortOrder: int = 0


class UpdateUnderlyingRequest(BaseModel):
    name: Optional[str] = None
    groupName: Optional[str] = None
    exchange: Optional[str] = None
    aliases: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    heavyweights: Optional[List[Dict[str, Any]]] = None
    enabled: Optional[bool] = None
    sortOrder: Optional[int] = None


class ResearchSourceFilter(BaseFilter):
    sourceType: Optional[str] = None
    enabled: Optional[bool] = None


class CreateSourceRequest(BaseModel):
    name: str
    sourceType: Literal["RSS", "AGENCY", "SEARCH", "PAPER"]
    baseUrl: str
    feedUrl: Optional[str] = None
    credibilityWeight: float = Field(default=0.60, ge=0.0, le=1.0)
    appliesToTypes: List[str] = ["INDEX", "COMMODITY"]
    appliesToGroups: Optional[List[str]] = None
    enabled: bool = True


class UpdateSourceRequest(BaseModel):
    name: Optional[str] = None
    baseUrl: Optional[str] = None
    feedUrl: Optional[str] = None
    credibilityWeight: Optional[float] = None
    appliesToTypes: Optional[List[str]] = None
    appliesToGroups: Optional[List[str]] = None
    enabled: Optional[bool] = None


class ResearchRiskTermFilter(BaseFilter):
    category: Optional[str] = None
    enabled: Optional[bool] = None


class CreateRiskTermRequest(BaseModel):
    term: str
    category: str
    defaultSeverity: int = Field(default=3, ge=1, le=5)
    appliesToTypes: List[str] = ["INDEX", "COMMODITY", "STOCK"]
    enabled: bool = True


class UpdateRiskTermRequest(BaseModel):
    term: Optional[str] = None
    category: Optional[str] = None
    defaultSeverity: Optional[int] = None
    appliesToTypes: Optional[List[str]] = None
    enabled: Optional[bool] = None


class UpdateConfigRequest(BaseModel):
    weights: Dict[str, Any]
    thresholds: Dict[str, Any]
    limits: Dict[str, Any]
    note: Optional[str] = None
