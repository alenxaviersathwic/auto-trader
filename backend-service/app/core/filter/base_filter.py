from typing import Literal, Optional
from pydantic import BaseModel, Field
from app.core.db.entity_status import EntityStatus
from app.core.filter.date_filter import DateFilter


class BaseFilter(BaseModel):
    """
    BaseFilter for all search endpoints (POST /api/v1/<resource>/search).
    All search request bodies extend this class.
    """

    page: int = Field(default=0, ge=0, description="Zero-based page index")
    limit: int = Field(default=10, ge=1, le=100, description="Items per page (max 100)")
    sortBy: Optional[str] = Field(default="createdAt", description="Field to sort by in camelCase")
    sortDir: Optional[Literal["asc", "desc"]] = Field(
        default="desc", description="Sort direction: 'asc' or 'desc'"
    )
    status: Optional[EntityStatus] = Field(
        default=EntityStatus.ACTIVE,
        description="Filter by EntityStatus (default ACTIVE)",
    )
    query: Optional[str] = Field(
        default=None, description="Free-text substring search across declared fields"
    )
    dateFilter: Optional[DateFilter] = Field(
        default=None, description="Date filter on createdAt (null means no date restriction)"
    )

    model_config = {
        "populate_by_name": True,
    }
