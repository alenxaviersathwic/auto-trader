from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.filter.base_filter import BaseFilter

OPTION_TYPES = ("INDEX", "COMMODITY")


def clean_option_types(values: list[str]) -> list[str]:
    """Upper-cased, de-duplicated, in INDEX, COMMODITY order; at least one, only known values."""
    wanted = {str(v).strip().upper() for v in values or []}
    unknown = wanted - set(OPTION_TYPES)
    if unknown:
        raise ValueError(f"optionTypes may only contain {list(OPTION_TYPES)}; got {sorted(unknown)}")
    out = [t for t in OPTION_TYPES if t in wanted]
    if not out:
        raise ValueError("optionTypes needs at least one of INDEX, COMMODITY")
    return out


class OpportunityFinderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    shortLabel: str
    badgeColor: str
    optionTypes: list[str]
    methodology: str
    entryLogic: str
    trailLogic: str
    strategies: list[str]
    checks: list[str]
    drivers: str
    liveOnly: bool
    enabled: bool
    sortOrder: int
    status: str
    createdAt: datetime

    @field_validator("status", mode="before")
    @classmethod
    def _status_name(cls, v: object) -> str:
        return getattr(v, "name", v)  # type: ignore[return-value]


class OpportunityFinderUpdateRequest(BaseModel):
    """Editable profile of a finder. Only the fields sent are changed."""

    optionTypes: Optional[list[str]] = Field(default=None, description="Markets it works on: INDEX and/or COMMODITY")
    enabled: Optional[bool] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)

    @field_validator("optionTypes")
    @classmethod
    def _types(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return None if v is None else clean_option_types(v)


class OpportunityFinderSearchFilter(BaseFilter):
    """Search finders; `optionType` keeps only finders that work on that market."""

    sortBy: Optional[str] = "sortOrder"
    sortDir: Optional[Literal["asc", "desc"]] = "asc"
    optionType: Optional[str] = Field(default=None, description="INDEX or COMMODITY")
    enabled: Optional[bool] = None
