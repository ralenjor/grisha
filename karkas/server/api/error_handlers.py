"""
Global Exception Handlers for KARKAS API

This module provides FastAPI exception handlers that convert exceptions
to standardized JSON error responses with proper HTTP status codes.
"""
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.exceptions import KarkasException, RateLimitError
from server.logging_config import get_logger, get_request_id, LOGGER_API

logger = get_logger(f"{LOGGER_API}.errors")


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    error_type: str = "error",
    details: dict | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """Create a standardized JSON error response"""
    from datetime import datetime, timezone

    content = {
        "error": {
            "code": error_code,
            "message": message,
            "type": error_type,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "request_id": request_id,
        }
    }

    headers = {}
    return JSONResponse(status_code=status_code, content=content, headers=headers)


async def karkas_exception_handler(request: Request, exc: KarkasException) -> JSONResponse:
    """
    Handle KarkasException and subclasses.

    Converts KARKAS-specific exceptions to standardized JSON error responses.
    """
    request_id = get_request_id()

    # Log the error with appropriate level
    if exc.http_status >= 500:
        logger.error(
            f"Server error: {exc.error_code} - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "details": exc.details,
                "path": str(request.url),
            },
            exc_info=True,
        )
    elif exc.http_status >= 400:
        logger.warning(
            f"Client error: {exc.error_code} - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "details": exc.details,
                "path": str(request.url),
            },
        )

    response = JSONResponse(
        status_code=exc.http_status,
        content=exc.to_dict(request_id),
    )

    # Add Retry-After header for rate limit errors
    if isinstance(exc, RateLimitError) and exc.retry_after:
        response.headers["Retry-After"] = str(exc.retry_after)

    return response


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle standard HTTPException.

    Converts FastAPI/Starlette HTTPException to standardized format.
    """
    request_id = get_request_id()

    # Map status codes to error codes and types
    status_code_map = {
        400: ("BAD_REQUEST", "validation_error"),
        401: ("UNAUTHORIZED", "authentication_error"),
        403: ("FORBIDDEN", "authorization_error"),
        404: ("NOT_FOUND", "not_found"),
        405: ("METHOD_NOT_ALLOWED", "client_error"),
        409: ("CONFLICT", "conflict"),
        422: ("UNPROCESSABLE_ENTITY", "validation_error"),
        429: ("RATE_LIMIT_EXCEEDED", "rate_limit"),
        500: ("INTERNAL_SERVER_ERROR", "server_error"),
        502: ("BAD_GATEWAY", "service_error"),
        503: ("SERVICE_UNAVAILABLE", "service_error"),
        504: ("GATEWAY_TIMEOUT", "service_error"),
    }

    error_code, error_type = status_code_map.get(
        exc.status_code, ("ERROR", "error")
    )

    # Extract message from detail
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code}: {message}", extra={"path": str(request.url)})
    elif exc.status_code >= 400:
        logger.warning(f"HTTP {exc.status_code}: {message}", extra={"path": str(request.url)})

    return create_error_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=message,
        error_type=error_type,
        request_id=request_id,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic/FastAPI validation errors.

    Converts validation errors to standardized format with field-level details.
    """
    request_id = get_request_id()

    # Extract validation errors
    errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
        })

    # Use first error for main message
    first_error = errors[0] if errors else {"field": "unknown", "message": "Validation failed"}
    message = f"Validation error: {first_error['message']}"
    if first_error["field"] != "body":
        message = f"Validation error in '{first_error['field']}': {first_error['message']}"

    logger.warning(
        f"Validation failed: {len(errors)} error(s)",
        extra={
            "errors": errors,
            "path": str(request.url),
        },
    )

    return create_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message=message,
        error_type="validation_error",
        details={"errors": errors},
        request_id=request_id,
    )


async def pydantic_exception_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
    """
    Handle raw Pydantic ValidationError (not wrapped by FastAPI).
    """
    request_id = get_request_id()

    errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
        })

    first_error = errors[0] if errors else {"field": "unknown", "message": "Validation failed"}

    logger.warning(
        f"Pydantic validation failed: {len(errors)} error(s)",
        extra={"errors": errors, "path": str(request.url)},
    )

    return create_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message=f"Validation error in '{first_error['field']}': {first_error['message']}",
        error_type="validation_error",
        details={"errors": errors},
        request_id=request_id,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unhandled exceptions.

    Catches all other exceptions and returns a generic 500 error.
    In production, sensitive details are hidden.
    """
    request_id = get_request_id()

    # Log the full exception with traceback
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={"path": str(request.url)},
    )

    # In debug mode, include exception details
    from server.config import get_settings
    settings = get_settings()

    details = {}
    if settings.server.debug:
        details["exception_type"] = type(exc).__name__
        details["exception_message"] = str(exc)

    return create_error_response(
        status_code=500,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred" if not settings.server.debug else str(exc),
        error_type="server_error",
        details=details,
        request_id=request_id,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.

    Should be called during application setup.
    """
    # Custom KARKAS exceptions (most specific first)
    app.add_exception_handler(KarkasException, karkas_exception_handler)

    # FastAPI/Starlette HTTP exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(PydanticValidationError, pydantic_exception_handler)

    # Catch-all for unhandled exceptions
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Exception handlers registered")


# =============================================================================
# HTTP Error Helper Functions
# =============================================================================


def raise_not_found(resource_type: str, resource_id: str) -> None:
    """Helper to raise a not found error"""
    from server.exceptions import NotFoundError
    raise NotFoundError(resource_type, resource_id)


def raise_validation_error(message: str, field: str | None = None, value: str | None = None) -> None:
    """Helper to raise a validation error"""
    from server.exceptions import ValidationError
    raise ValidationError(message, field=field, value=value)


def raise_conflict(message: str, current_state: str | None = None) -> None:
    """Helper to raise a conflict error"""
    from server.exceptions import ConflictError
    raise ConflictError(message, details={"current_state": current_state} if current_state else {})
