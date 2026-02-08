"""
Pydantic schemas for Subscription API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlanFeature(BaseModel):
    """Single feature in a subscription plan."""
    text: str
    included: bool = True


class PlanResponse(BaseModel):
    """Subscription plan details."""
    id: UUID
    name: str
    display_name: str
    price_monthly: Decimal
    price_yearly: Decimal
    features: list[str]
    swipe_limit: Optional[int] = None
    super_likes_weekly: int = 0
    has_see_likes: bool = False
    has_priority_placement: bool = False
    has_read_receipts: bool = False
    has_monthly_boost: bool = False
    sort_order: int = 0

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    """User's current subscription details."""
    id: UUID
    user_id: UUID
    plan: PlanResponse
    status: str
    billing_interval: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CheckoutSessionRequest(BaseModel):
    """Request to create Stripe checkout session."""
    plan_id: UUID
    billing_interval: str = Field(pattern="^(monthly|yearly)$")
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Response with Stripe checkout session URL."""
    checkout_url: str
    session_id: str


class PortalSessionResponse(BaseModel):
    """Response with Stripe customer portal URL."""
    portal_url: str
