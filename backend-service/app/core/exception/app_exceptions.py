from typing import Any, Optional


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str = "An application error occurred",
        status_code: int = 500,
        error: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error = error


class NotFoundException(AppException):
    """404 Not Found exception."""

    def __init__(
        self,
        message: str = "Resource not found",
        error: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=404, error=error)


class ConflictException(AppException):
    """409 Conflict exception."""

    def __init__(
        self,
        message: str = "Resource conflict",
        error: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            status_code=409,
            error=error or {"code": "RESOURCE_CONFLICT"},
        )


class ValidationException(AppException):
    """400 Validation / Business Rule exception."""

    def __init__(
        self,
        message: str = "Validation failed",
        error: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=400, error=error)


class BusinessException(ValidationException):
    """400 Business logic error exception."""
    pass


class BadRequestException(AppException):
    """400 Bad Request exception."""

    def __init__(
        self,
        message: str = "Bad request",
        error: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=400, error=error)


class UnauthorizedException(AppException):
    """401 Unauthorized exception."""

    def __init__(
        self,
        message: str = "Unauthorized",
        error: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=401, error=error)


class ForbiddenException(AppException):
    """403 Forbidden exception."""

    def __init__(
        self,
        message: str = "Forbidden",
        error: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=403, error=error)


class InternalServerException(AppException):
    """500 Internal Server error."""

    def __init__(
        self,
        message: str = "Internal server error",
        error: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=500, error=error)
