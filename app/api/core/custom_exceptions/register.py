"""
Registers all exception handlers to the FastAPI application.
"""

import logging

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.core.custom_exceptions.exceptions import CustomDomainException
from app.api.core.custom_exceptions.handlers import (
    domain_exception_handler,
    internal_server_error_handler,
    starlette_http_exception_handler,
)

logger = logging.getLogger(__name__)


def register_all_errors(app: FastAPI) -> None:
    """
    Registers all custom exception handlers to the FastAPI app instance.

    Args:
        app: The FastAPI application instance
    """

    app.add_exception_handler(CustomDomainException, domain_exception_handler)

    app.add_exception_handler(500, internal_server_error_handler)

    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)

    logger.info("All exception handlers registered successfully")
