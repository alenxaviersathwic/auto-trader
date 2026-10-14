from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    Universal API response envelope for all endpoints.
    statusCode matches HTTP response code.
    data contains payload or null.
    message is always a human-readable string.
    error is null on success or structured error on failure.
    """

    statusCode: int = Field(..., description="HTTP status code")
    data: Optional[T] = Field(default=None, description="Response data payload")
    message: str = Field(..., description="Human-readable message")
    error: Optional[Any] = Field(default=None, description="Error detail if failed")

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "statusCode": 200,
                "data": {"id": 1, "status": "ACTIVE"},
                "message": "Fetched successfully",
                "error": None,
            }
        },
    }
