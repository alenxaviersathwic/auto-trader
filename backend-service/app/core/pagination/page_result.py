from typing import Generic, List, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    """
    Standard pagination result container.
    list: items matching the filter, never null
    page: zero-based page number
    limit: items per page
    totalPages: ceil(totalItems / limit), 0 when empty
    totalItems: total rows matching filter
    """

    list: List[T] = Field(default_factory=list, description="Items on the current page")
    page: int = Field(..., description="Current zero-based page number")
    limit: int = Field(..., description="Requested page limit")
    totalPages: int = Field(..., description="Total pages available")
    totalItems: int = Field(..., description="Total matching items across all pages")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
