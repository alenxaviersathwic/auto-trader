from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.core.filter.base_filter import BaseFilter
from app.core.db.entity_status import EntityStatus


class RegistryFilter(BaseFilter):
    registryType: Optional[str] = Field(default=None, description="Registry category (e.g. INDICATOR, OPERATOR)")
    kind: Optional[str] = Field(default=None, description="BUILT_IN, DERIVED, CUSTOM")
    executable: Optional[bool] = Field(default=None, description="Executable flag")
    enabled: Optional[bool] = Field(default=None, description="Enabled flag")


class RegistryItemCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    registryType: str = Field(..., description="Registry category")
    code: str = Field(..., description="Unique code within registry type")
    name: str = Field(..., description="Human-readable label")
    kind: str = Field(default="CUSTOM", description="DERIVED or CUSTOM (BUILT_IN requires code handler)")
    schema: Optional[Dict[str, Any]] = Field(default=None, description="Parameters and outputs schema")
    expression: Optional[Dict[str, Any]] = Field(default=None, description="Expression over other items for DERIVED")
    handlerKey: Optional[str] = Field(default=None, description="Code handler key")
    requires: Optional[List[str]] = Field(default=None, description="Required data inputs")
    description: Optional[str] = Field(default=None, description="Description")
    enabled: bool = Field(default=True)


class RegistryItemUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}
    name: Optional[str] = None
    schema: Optional[Dict[str, Any]] = None
    expression: Optional[Dict[str, Any]] = None
    handlerKey: Optional[str] = None
    requires: Optional[List[str]] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class RegistryItemResponse(BaseModel):
    id: int
    createdAt: datetime
    status: Union[EntityStatus, int]
    registryType: str
    code: str
    name: str
    kind: str
    version: int
    schema: Optional[Dict[str, Any]] = None
    expression: Optional[Dict[str, Any]] = None
    handlerKey: Optional[str] = None
    executable: bool
    requires: Optional[List[str]] = None
    description: Optional[str] = None
    enabled: bool
    usedByCount: Optional[int] = 0

    model_config = {"populate_by_name": True, "from_attributes": True, "protected_namespaces": ()}


class DerivedTestRequest(BaseModel):
    expression: Dict[str, Any]
    context: Dict[str, Any]


class DerivedTestResponse(BaseModel):
    result: Optional[float]
    success: bool
    error: Optional[str] = None
