from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from app.core.filter.base_filter import BaseFilter


class ComponentHealth(BaseModel):
    name: str
    status: Literal["OK", "DEGRADED", "DOWN"]
    detail: str
    checkedAt: str


class SystemStatusResponse(BaseModel):
    components: List[ComponentHealth]
    overallStatus: Literal["OK", "DEGRADED", "DOWN"]
    checkedAt: str


class EngineSummary(BaseModel):
    code: str
    name: str
    description: str
    module: str
    runnable: bool
    currentState: Literal["IDLE", "QUEUED", "RUNNING", "FAILED", "CANCELLED", "COMPLETED", "PARTIAL"] = "IDLE"
    lastRunSummary: Optional[str] = None
    lastRunAt: Optional[str] = None
    storedInfo: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    paramSchema: Optional[Dict[str, Any]] = None


class EngineSearchFilter(BaseFilter):
    pass


class EngineRunRequest(BaseModel):
    scope: Optional[List[str]] = Field(default=None, description="Types to evaluate, e.g. ['INDEX', 'COMMODITY']")
    windowHours: Optional[int] = Field(default=24, ge=6, le=48, description="Freshness window in hours")
    topN: Optional[int] = Field(default=5, ge=1, le=20, description="Top candidates to suggest")
    maxDocsPerUnderlying: Optional[int] = Field(default=20, ge=5, le=50, description="Fetch limit per underlying")
