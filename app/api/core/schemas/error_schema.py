from typing import Dict, List

from pydantic import BaseModel, Field


class ErrorResponseModel(BaseModel):
    """
    Standardized error response model for API endpoints.

    Attributes:
        error (str): Indicates failed operation (always "ERROR").
        status_code (int): Corresponding HTTP error status code.
        message (str): Human-readable description of the error.
        error (str): Machine-readable error identifier
                     (e.g., "VALIDATION_ERROR", "UNAUTHORIZED").
        errors (dict): Optional field-level validation errors.
                       Keys are field names; values are lists of error messages.
    """

    error: str = Field(default="ERROR", description="Indicates failed operation")
    status_code: int = Field(..., description="HTTP status code for the error")
    message: str = Field(..., description="Human-readable error message")
    errors: Dict[str, List[str]] = Field(
        default_factory=dict, description="Field-level validation errors"
    )
