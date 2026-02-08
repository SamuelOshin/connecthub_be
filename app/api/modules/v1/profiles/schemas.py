"""
Pydantic schemas for Profile API.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PreferencesSchema(BaseModel):
    """User discovery preferences."""
    min_age: int = Field(default=18, ge=18, le=100)
    max_age: int = Field(default=50, ge=18, le=100)
    distance_km: int = Field(default=50, ge=1, le=500)
    show_me: list[str] = Field(default=["male", "female"])


class PrivacySettingsSchema(BaseModel):
    """User privacy settings."""
    incognito_mode: bool = False
    active_status: bool = True
    read_receipts: bool = True


class NotificationSettingsSchema(BaseModel):
    """User notification settings."""
    new_matches: bool = True
    new_messages: bool = True
    super_likes: bool = True
    promotions: bool = False


class PromptSchema(BaseModel):

    """Profile prompt with question and answer."""
    question: str = Field(..., max_length=200)
    answer: str = Field(..., max_length=500)


class LocationUpdate(BaseModel):
    """Location update request."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class ProfileBase(BaseModel):
    """Base profile fields."""
    display_name: Optional[str] = Field(None, max_length=50)
    birthdate: date
    gender: Optional[str] = Field(None, pattern="^(male|female|non-binary|other)$")
    looking_for: list[str] = Field(default_factory=list)
    bio: Optional[str] = Field(None, max_length=500)

    @field_validator("birthdate")
    @classmethod
    def validate_age(cls, v: date) -> date:
        """Ensure user is at least 18 years old."""
        from datetime import date as dt
        today = dt.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError("Must be at least 18 years old")
        return v


class ProfileCreate(ProfileBase):
    """Profile creation request (during onboarding)."""
    pass


class ProfileUpdate(BaseModel):
    """Profile update request (partial)."""
    display_name: Optional[str] = Field(None, max_length=50)
    gender: Optional[str] = Field(None, pattern="^(male|female|non-binary|other)$")
    looking_for: Optional[list[str]] = None
    bio: Optional[str] = Field(None, max_length=500)
    preferences: Optional[PreferencesSchema] = None
    prompts: Optional[list[PromptSchema]] = None
    passions: Optional[list[str]] = None
    privacy_settings: Optional[PrivacySettingsSchema] = None
    notification_settings: Optional[NotificationSettingsSchema] = None


class ProfileResponse(ProfileBase):
    """Profile response with all fields."""
    id: UUID
    preferences: PreferencesSchema
    prompts: list[PromptSchema]
    is_verified: bool
    subscription_status: str
    passions: list[str] = Field(default_factory=list)
    privacy_settings: Optional[PrivacySettingsSchema] = None
    notification_settings: Optional[NotificationSettingsSchema] = None
    last_active: datetime
    created_at: datetime
    updated_at: datetime
    
    # Computed fields (populated by service)
    age: Optional[int] = None
    distance_km: Optional[float] = None
    primary_photo_url: Optional[str] = None

    class Config:
        from_attributes = True


class ProfilePublic(BaseModel):
    """Public profile for discovery (limited fields)."""
    id: UUID
    display_name: Optional[str]
    age: int
    gender: Optional[str]
    bio: Optional[str]
    prompts: list[PromptSchema]
    distance_km: Optional[float]
    distance_km: Optional[float]
    is_verified: bool
    passions: list[str] = Field(default_factory=list)
    photos: list[str]  # Photo URLs

    class Config:
        from_attributes = True
