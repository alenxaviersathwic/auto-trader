import logging
from typing import Any, List, Sequence
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from app.core.exception.app_exceptions import AppException
from app.core.response.response_helper import build_response

logger = logging.getLogger("auto-trader.exceptions")


def format_validation_errors(errors: Sequence[Any]) -> List[dict]:
    """Formats Pydantic / FastAPI validation errors into [{ field, message }] array."""
    formatted = []
    for err in errors:
        loc = err.get("loc", [])
        # Extract field name, skipping 'body', 'query', etc. if nested
        field_parts = [str(x) for x in loc if x not in ("body", "query", "path")]
        field_name = ".".join(field_parts) if field_parts else "root"
        msg = err.get("msg", "Invalid value")
        # Clean up Pydantic string prefixes if any
        if msg.startswith("Value error, "):
            msg = msg.replace("Value error, ", "")
        formatted.append({"field": field_name, "message": msg})
    return formatted


def register_exception_handlers(app: FastAPI) -> None:
    """Registers global exception handlers for the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(
            f"AppException [{exc.status_code}] on {request.method} {request.url.path}: {exc.message} (error: {exc.error})"
        )
        return build_response(
            status_code=exc.status_code,
            data=None,
            message=exc.message,
            error=exc.error,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        field_errors = format_validation_errors(exc.errors())
        logger.warning(
            f"Validation error on {request.method} {request.url.path}: {field_errors}"
        )
        return build_response(
            status_code=400,
            data=None,
            message="Validation failed",
            error=field_errors,
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        field_errors = format_validation_errors(exc.errors())
        logger.warning(
            f"Pydantic validation error on {request.method} {request.url.path}: {field_errors}"
        )
        return build_response(
            status_code=400,
            data=None,
            message="Validation failed",
            error=field_errors,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(
            f"HTTPException [{exc.status_code}] on {request.method} {request.url.path}: {exc.detail}"
        )
        msg = str(exc.detail) if exc.detail else "Request failed"
        return build_response(
            status_code=exc.status_code,
            data=None,
            message=msg,
            error=None,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Log full traceback internally; never leak to client
        logger.exception(
            f"Unhandled 500 error on {request.method} {request.url.path}: {str(exc)}"
        )
        return build_response(
            status_code=500,
            data=None,
            message="Internal server error",
            error=None,
        )
