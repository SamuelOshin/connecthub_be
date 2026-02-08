"""
Global exception handlers for FastAPI application.
Converts domain exceptions into standardized JSON responses.
"""

import logging

from fastapi import Request, status
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.core.custom_exceptions.error_status_code_mapper import ERROR_STATUS_MAP
from app.api.core.custom_exceptions.exceptions import CustomDomainException
from app.api.utils.response_payloads import error_response

logger = logging.getLogger(__name__)


async def domain_exception_handler(request: Request, exc: CustomDomainException):
    """
    Global handler for all CustomDomainException instances.
    Converts domain exceptions into standardized error responses.

    Also logs additional context from exception properties for debugging.
    """
    status_code = ERROR_STATUS_MAP.get(exc.code, status.HTTP_400_BAD_REQUEST)

    # Check if it's a validation error with field-level errors
    field_errors = getattr(exc, "field_errors", None)

    log_context = {
        "error_code": exc.code,
        "status_code": status_code,
        "path": request.url.path,
    }

    # Dynamically capture ALL additional properties from the exception
    base_attrs = {"message", "code", "args", "field_errors", "with_traceback"}
    for attr, value in exc.__dict__.items():
        # Skip internal/base attributes and None values
        if attr not in base_attrs and value is not None:
            log_context[attr] = value

    logger.warning(
        f"Domain exception raised: {exc.code} - {exc.message} - {status_code}", extra=log_context
    )

    return error_response(
        status_code=status_code,
        message=exc.message,
        error_code=exc.code,
        errors=field_errors,
    )


async def internal_server_error_handler(request: Request, exc: Exception):
    """Handler for uncaught 500 errors"""
    logger.exception(
        "Internal Server Error",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )

    return error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred. Please try again later.",
        error_code="INTERNAL_SERVER_ERROR",
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Fallback handler for Starlette HTTP exceptions"""
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )

    return error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code="HTTP_EXCEPTION",
    )
