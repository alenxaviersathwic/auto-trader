from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.core.filter.base_filter import BaseFilter
from app.core.db.entity_status import EntityStatus


class ImportBatchResponse(BaseModel):
    id: int
    createdAt: datetime
    status: Union[EntityStatus, int]
    fileName: str
    sourceFormat: str
    mode: str
    dryRun: bool
    totalItems: int
    createdCount: int
    updatedCount: int
    skippedCount: int
    failedCount: int
    errors: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[Any]] = None

    model_config = {"populate_by_name": True, "from_attributes": True}


class ImportFilter(BaseFilter):
    sourceFormat: Optional[str] = None
    dryRun: Optional[bool] = None


class ImportRequest(BaseModel):
    sourceFormat: str = Field(default="BUNDLE_V2", description="BUNDLE_V2 or LEGACY_ALGO_V1")
    mode: str = Field(default="SKIP", description="SKIP or UPDATE")
    dryRun: bool = Field(default=False)
    fileName: Optional[str] = "api_import.json"
    items: Optional[Dict[str, Any]] = None  # JSON payload containing strategies & rules


class ExportRequest(BaseModel):
    ids: Optional[List[int]] = None
    includePerformance: bool = True


class ExportResponse(BaseModel):
    schemaVersion: int = 2
    source: str = "AUTO_TRADER_V2"
    exportedAt: datetime
    strategies: List[Dict[str, Any]]
    rules: List[Dict[str, Any]]
