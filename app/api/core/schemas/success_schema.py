from typing import Any, Optional

from pydantic import BaseModel, Field


class SuccessResponseModel(BaseModel):
    """
    Standardized success response model for API endpoints.

    Attributes:
        success (str): Indicates successful operation (always "SUCCESS").
        message (str): Human-readable success message.
        status_code (int): Corresponding HTTP status code.
        data (Any): Actual response payload. Optional.
    """

    status: str = Field(default="SUCCESS", description="Indicates successful operation")
    message: str = Field(..., description="Human-readable success message")
    status_code: int = Field(..., description="HTTP status code")
    data: Optional[Any] = Field(default=None, description="Response payload")
