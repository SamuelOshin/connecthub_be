"""
Pydantic schemas for Photos API.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PhotoBase(BaseModel):
    """Base photo fields."""
    order_index: int = Field(default=0, ge=0, le=9)
    is_primary: bool = False


class PhotoCreate(PhotoBase):
    """Photo creation (after upload)."""
    storage_path: str


class PhotoUpdate(BaseModel):
    """Photo update request."""
    order_index: Optional[int] = Field(None, ge=0, le=9)
    is_primary: Optional[bool] = None


class PhotoReorder(BaseModel):
    """Reorder photos request."""
    photo_ids: list[UUID] = Field(..., min_length=1, max_length=10)


class PhotoResponse(PhotoBase):
    """Photo response with all fields."""
    id: UUID
    user_id: UUID
    storage_path: str
    moderation_status: str
    created_at: datetime
    url: Optional[str] = None  # Signed URL

    class Config:
        from_attributes = True


class UploadUrlResponse(BaseModel):
    """Response with signed upload URL."""
    upload_url: str
    storage_path: str
    expires_in: int = 3600
