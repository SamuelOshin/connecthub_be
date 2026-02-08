"""
Subscription service layer - business logic for premium plans.

Contains all business logic for subscription management including:
- Listing available plans
- Managing user subscriptions
- Stripe checkout integration
- Webhook handling
"""

from typing import Optional
from uuid import UUID

from supabase import Client

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ProcessingError,
    ValidationError,
)


class SubscriptionService:
    """
    Service for subscription operations.

    Handles all business logic related to subscription management
    including plan retrieval, checkout session creation, and
    subscription lifecycle management.

    Attributes:
        supabase: Authenticated Supabase client (respects RLS).
        user_id: Current authenticated user's UUID.
    """

    def __init__(self, supabase: Client, user_id: UUID):
        """
        Initialize subscription service.

        Args:
            supabase: Authenticated Supabase client (respects RLS).
            user_id: Current authenticated user's ID.
        """
        self.supabase = supabase
        self.user_id = user_id

    def get_plans(self) -> list[dict]:
        """
        Get all active subscription plans.

        Returns:
            list[dict]: List of subscription plans ordered by sort_order.

        Raises:
            ProcessingError: If query fails.
        """
        result = self.supabase.table("subscription_plans").select("*").eq(
            "is_active", True
        ).order("sort_order").execute()

        if hasattr(result, "error") and result.error:
            raise ProcessingError(f"Failed to fetch plans: {result.error}")

        return result.data

    def get_user_subscription(self) -> Optional[dict]:
        """
        Get the current user's subscription with plan details.

        Returns:
            dict: User subscription with embedded plan data, or None.

        Raises:
            ProcessingError: If query fails.
        """
        result = self.supabase.table("user_subscriptions").select(
            "*, plan:subscription_plans(*)"
        ).eq("user_id", str(self.user_id)).maybe_single().execute()

        if hasattr(result, "error") and result.error:
            raise ProcessingError(f"Failed to fetch subscription: {result.error}")

        return result.data if result else None

    def get_or_create_basic_subscription(self) -> dict:
        """
        Get user's subscription or create a Basic (free) one.

        Returns:
            dict: User subscription with plan data.

        Raises:
            ProcessingError: If operation fails.
        """
        existing = self.get_user_subscription()
        if existing:
            return existing

        # Get basic plan
        basic_plan = self.supabase.table("subscription_plans").select("id").eq(
            "name", "basic"
        ).single().execute()

        if not basic_plan.data:
            raise ProcessingError("Basic plan not found in database")

        # Create subscription
        new_sub = self.supabase.table("user_subscriptions").insert({
            "user_id": str(self.user_id),
            "plan_id": basic_plan.data["id"],
            "status": "active",
        }).execute()

        if hasattr(new_sub, "error") and new_sub.error:
            raise ProcessingError(f"Failed to create subscription: {new_sub.error}")

        return self.get_user_subscription()

    def update_subscription(
        self,
        plan_id: UUID,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        status: str = "active",
        billing_interval: Optional[str] = None,
        current_period_start: Optional[str] = None,
        current_period_end: Optional[str] = None,
    ) -> dict:
        """
        Update user's subscription after successful payment.

        Args:
            plan_id: New plan UUID.
            stripe_customer_id: Stripe customer ID.
            stripe_subscription_id: Stripe subscription ID.
            status: Subscription status.
            billing_interval: 'monthly' or 'yearly'.
            current_period_start: Period start timestamp.
            current_period_end: Period end timestamp.

        Returns:
            dict: Updated subscription data.

        Raises:
            ProcessingError: If update fails.
        """
        update_data = {
            "plan_id": str(plan_id),
            "status": status,
            "updated_at": "now()",
        }

        if stripe_customer_id:
            update_data["stripe_customer_id"] = stripe_customer_id
        if stripe_subscription_id:
            update_data["stripe_subscription_id"] = stripe_subscription_id
        if billing_interval:
            update_data["billing_interval"] = billing_interval
        if current_period_start:
            update_data["current_period_start"] = current_period_start
        if current_period_end:
            update_data["current_period_end"] = current_period_end

        result = self.supabase.table("user_subscriptions").upsert(
            {**update_data, "user_id": str(self.user_id)},
            on_conflict="user_id"
        ).execute()

        if hasattr(result, "error") and result.error:
            raise ProcessingError(f"Failed to update subscription: {result.error}")

        return self.get_user_subscription()

    def cancel_subscription(self) -> dict:
        """
        Cancel user's subscription (immediate or end of period).

        Returns:
            dict: Updated subscription with canceled status.

        Raises:
            NotFoundError: If no subscription exists.
            ProcessingError: If cancellation fails.
        """
        existing = self.get_user_subscription()
        if not existing:
            raise NotFoundError("No active subscription found")

        if existing["plan"]["name"] == "basic":
            raise ValidationError("Cannot cancel free plan")

        result = self.supabase.table("user_subscriptions").update({
            "status": "canceled",
            "canceled_at": "now()",
            "updated_at": "now()",
        }).eq("user_id", str(self.user_id)).execute()

        if hasattr(result, "error") and result.error:
            raise ProcessingError(f"Failed to cancel subscription: {result.error}")

        return self.get_user_subscription()

    def get_plan_by_id(self, plan_id: UUID) -> dict:
        """
        Get a specific plan by ID.

        Args:
            plan_id: Plan UUID.

        Returns:
            dict: Plan data.

        Raises:
            NotFoundError: If plan not found.
        """
        result = self.supabase.table("subscription_plans").select("*").eq(
            "id", str(plan_id)
        ).single().execute()

        if not result.data:
            raise NotFoundError("Plan not found")

        return result.data
