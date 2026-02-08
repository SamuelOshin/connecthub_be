"""
Matches API schemas.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ===========================================
# RESPONSE SCHEMAS
# ===========================================


class MatchedUserInfo(BaseModel):
    """Information about the matched user."""

    id: UUID
    display_name: Optional[str]
    age: Optional[int]
    primary_photo_url: Optional[str]
    response_badge: Optional[str]


class MatchDetail(BaseModel):
    """Detailed match information."""

    id: UUID
    matched_user: MatchedUserInfo
    matched_at: datetime
    expires_at: Optional[datetime]
    status: str  # ACTIVE, EXPIRED, UNMATCHED, REPORTED

    # Match context
    your_opening_comment: Optional[str]
    their_opening_comment: Optional[str]
    match_reasons: list[str] = []

    # Chat preview
    first_message_at: Optional[datetime]
    last_message_at: Optional[datetime]
    last_message_preview: Optional[str]
    unread_count: int = 0

    # Expiration tracking
    hours_until_expiry: Optional[float]
    is_expiring_soon: bool = False  # < 12 hours left


class MatchListItem(BaseModel):
    """Match item for list view."""

    id: UUID
    matched_user: MatchedUserInfo
    matched_at: datetime
    status: str

    # Quick preview
    last_message_preview: Optional[str]
    last_message_at: Optional[datetime]
    unread_count: int = 0

    # Expiration flags
    has_started_chatting: bool = False
    hours_until_expiry: Optional[float]
    is_expiring_soon: bool = False


class MatchListResponse(BaseModel):
    """Response for matches list endpoint."""

    matches: list[MatchListItem]
    total_count: int
    active_count: int
    expiring_soon_count: int


class UnmatchResponse(BaseModel):
    """Response after unmatching."""

    success: bool
    message: str
