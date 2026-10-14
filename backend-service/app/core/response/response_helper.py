from typing import Any
from fastapi.responses import JSONResponse
from app.core.response.api_response import ApiResponse


def success(
    data: Any = None,
    message: str = "Operation completed successfully",
    status_code: int = 200,
) -> ApiResponse[Any]:
    """Helper to return a success ApiResponse."""
    return ApiResponse[Any](
        statusCode=status_code,
        data=data,
        message=message,
        error=None,
    )


def created(
    data: Any = None,
    message: str = "Resource created successfully",
) -> ApiResponse[Any]:
    """Helper to return a 201 Created ApiResponse."""
    return ApiResponse[Any](
        statusCode=201,
        data=data,
        message=message,
        error=None,
    )


def build_response(
    status_code: int,
    data: Any = None,
    message: str = "Operation completed",
    error: Any = None,
) -> JSONResponse:
    """Helper to construct a direct FastAPI JSONResponse using the standard envelope."""
    payload = ApiResponse[Any](
        statusCode=status_code,
        data=data,
        message=message,
        error=error,
    ).model_dump(by_alias=True)
    return JSONResponse(status_code=status_code, content=payload)
