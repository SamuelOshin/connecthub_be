"""Safety API Schemas - Block & Report."""

from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ReportUserRequest(BaseModel):
    """Request to report a user for policy violation."""

    reported_user_id: UUID = Field(..., description="UUID of the user being reported.")
    reason: Literal[
        "SPAM",
        "HARASSMENT",
        "INAPPROPRIATE_CONTENT",
        "FAKE_PROFILE",
        "UNDERAGE",
        "OTHER",
    ] = Field(..., description="Reason for the report.")
    details: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional details about the report.",
    )
