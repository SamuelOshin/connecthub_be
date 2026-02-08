"""
Discovery API schemas for matching engine.
Based on matching_engine_spec.md
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ===========================================
# REQUEST SCHEMAS
# ===========================================


class SwipeCreate(BaseModel):
    """Request to create a swipe action."""

    profile_id: UUID = Field(..., description="ID of the profile being swiped on")
    direction: str = Field(
        ...,
        pattern="^(LEFT|RIGHT|SUPER_LIKE)$",
        description="Swipe direction: LEFT (pass), RIGHT (like), SUPER_LIKE",
    )
    comment: Optional[str] = Field(
        None, min_length=10, description="Required comment for RIGHT/SUPER_LIKE (min 10 chars)"
    )
    comment_target: Optional[str] = Field(
        None, description="What the comment is about: 'photo_0', 'prompt_1', etc."
    )
    time_spent_viewing_ms: Optional[int] = Field(
        None, ge=0, description="Time spent viewing profile in milliseconds"
    )
    profile_scroll_depth: Optional[float] = Field(
        None, ge=0, le=1, description="How far user scrolled (0.0 to 1.0)"
    )


class PreferencesUpdate(BaseModel):
    """Request to update user preferences."""

    min_age: Optional[int] = Field(None, ge=18, le=99)
    max_age: Optional[int] = Field(None, ge=18, le=99)
    max_distance_km: Optional[int] = Field(None, ge=1, le=500)
    gender_preferences: Optional[list[str]] = None
    preferred_height_min_cm: Optional[int] = Field(None, ge=100, le=250)
    preferred_height_max_cm: Optional[int] = Field(None, ge=100, le=250)
    preferred_education: Optional[list[str]] = None
    preferred_religion: Optional[list[str]] = None
    preferred_smoking: Optional[str] = Field(
        None, pattern="^(non_smoker|social|regular|any)$"
    )
    preferred_drinking: Optional[str] = Field(
        None, pattern="^(non_drinker|social|regular|any)$"
    )
    preferred_children: Optional[str] = Field(
        None, pattern="^(want|dont_want|have|open|any)$"
    )
    show_verified_only: Optional[bool] = None


# ===========================================
# RESPONSE SCHEMAS
# ===========================================


class MatchScoreBreakdown(BaseModel):
    """Breakdown of match score components."""

    preference_overlap: float = Field(..., ge=0, le=1)
    behavioral_compatibility: float = Field(..., ge=0, le=1)
    effort_score: float = Field(..., ge=0, le=1)
    activity_freshness: float = Field(..., ge=0, le=1)
    feedback_history: float = Field(..., ge=0, le=1)
    exploration: float = Field(..., ge=0, le=1)


class DiscoveryProfile(BaseModel):
    """Profile returned in discovery feed."""

    id: UUID
    display_name: Optional[str]
    age: int
    gender: Optional[str]
    bio: Optional[str]
    prompts: list[dict] = []
    photos: list[dict] = []
    distance_km: float
    passions: list[str] = []
    is_verified: bool = False

    # Match scoring (transparency feature)
    match_score: float = Field(..., ge=0, le=1)
    match_reasons: list[str] = []
    score_breakdown: Optional[MatchScoreBreakdown] = None

    # Response behavior badge
    response_badge: Optional[str] = Field(
        None,
        description="VERY_RESPONSIVE, RESPONSIVE, SOMETIMES_RESPONDS, or None",
    )


class DiscoveryResponse(BaseModel):
    """Response for discovery profiles endpoint."""

    profiles: list[DiscoveryProfile]
    next_cursor: Optional[str] = None
    remaining_likes_today: int
    daily_like_limit: int


class SwipeResponse(BaseModel):
    """Response after creating a swipe."""

    success: bool
    match: Optional["MatchInfo"] = None
    remaining_likes_today: int


class MatchInfo(BaseModel):
    """Basic match information for match notification."""

    id: UUID
    matched_user_id: UUID
    matched_user_name: Optional[str]
    matched_user_photo_url: Optional[str]
    matched_at: datetime
    expires_at: datetime
    your_comment: Optional[str]
    their_comment: Optional[str]


class PreferencesResponse(BaseModel):
    """User preferences response."""

    min_age: int
    max_age: int
    max_distance_km: int
    gender_preferences: list[str]
    preferred_height_min_cm: Optional[int]
    preferred_height_max_cm: Optional[int]
    preferred_education: list[str]
    preferred_religion: list[str]
    preferred_smoking: Optional[str]
    preferred_drinking: Optional[str]
    preferred_children: Optional[str]
    show_verified_only: bool


class DiscoveryStats(BaseModel):
    """User's discovery statistics."""

    likes_sent_today: int
    likes_remaining_today: int
    daily_like_limit: int
    super_likes_remaining: int
    profiles_viewed_today: int
    match_rate: float  # Percentage of likes that resulted in matches
    response_rate: float  # User's message response rate


# Fix forward reference
SwipeResponse.model_rebuild()
