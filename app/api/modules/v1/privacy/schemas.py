"""Privacy API Schemas - GDPR Compliance."""

from typing import Optional
from pydantic import BaseModel, Field


class AccountDeletionRequest(BaseModel):
    """Request to delete user account."""

    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for leaving.",
    )
