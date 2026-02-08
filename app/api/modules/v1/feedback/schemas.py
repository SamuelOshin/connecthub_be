"""
Feedback API schemas for 'We Connected' system.
Based on matching_engine_spec.md
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ===========================================
# REQUEST SCHEMAS
# ===========================================


class ConnectionFeedbackCreate(BaseModel):
    """Request to submit connection feedback."""

    match_id: UUID

    # Core questions
    did_you_meet: bool = Field(
        ...,
        description="Did you meet or have meaningful contact with this person?",
    )
    meeting_type: Literal[
        "VIDEO_CALL", "IN_PERSON", "STILL_CHATTING", "NO_CONTACT"
    ] = Field(
        ...,
        description="Type of meeting or contact",
    )

    # If met
    would_meet_again: Optional[bool] = Field(
        None,
        description="Would you meet this person again?",
    )
    connection_quality: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Quality of connection (1-5 stars)",
    )

    # What worked/didn't
    positive_factors: Optional[list[Literal[
        "great_conversation",
        "shared_interests",
        "physical_attraction",
        "similar_values",
        "good_communication",
        "felt_safe",
        "fun_personality",
    ]]] = Field(
        default=None,
        description="What made the connection good?",
    )

    negative_factors: Optional[list[Literal[
        "no_chemistry",
        "different_than_photos",
        "different_than_profile",
        "poor_communicator",
        "ghosted",
        "felt_unsafe",
        "incompatible_values",
        "no_shared_interests",
    ]]] = Field(
        default=None,
        description="What made the connection not work?",
    )

    # Optional free text
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Any additional notes (private, not shared)",
    )


# ===========================================
# RESPONSE SCHEMAS
# ===========================================


class FeedbackMatchInfo(BaseModel):
    """Match info for feedback context."""

    id: UUID
    matched_user_name: Optional[str]
    matched_user_photo_url: Optional[str]
    matched_at: datetime
    days_since_match: int


class PendingFeedbackItem(BaseModel):
    """A match that needs feedback."""

    match: FeedbackMatchInfo
    prompt_text: str  # "How's it going with [Name]?"
    reminder_count: int  # How many times we've asked


class PendingFeedbackResponse(BaseModel):
    """Response for pending feedback endpoint."""

    pending: list[PendingFeedbackItem]
    total_count: int


class FeedbackResponse(BaseModel):
    """Response for submitted feedback."""

    id: UUID
    match_id: UUID
    submitted_at: datetime
    thank_you_message: str


class FeedbackSummary(BaseModel):
    """Summary of feedback for a match."""

    id: UUID
    match_id: UUID
    did_you_meet: bool
    meeting_type: str
    would_meet_again: Optional[bool]
    connection_quality: Optional[int]
    positive_factors: list[str]
    negative_factors: list[str]
    submitted_at: datetime
