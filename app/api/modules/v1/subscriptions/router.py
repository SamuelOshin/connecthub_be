"""
Subscription router - API endpoints for premium plans.
"""
from fastapi import APIRouter

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.utils.response_payloads import success_response

from .service import SubscriptionService
from .schemas import CheckoutSessionRequest


subscription_router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@subscription_router.get("/plans")
async def get_plans(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get all available subscription plans.

    Returns list of plans with pricing and features.
    """
    service = SubscriptionService(supabase, user_id)
    plans = service.get_plans()
    return success_response(200, "Plans retrieved successfully", {"plans": plans})


@subscription_router.get("/me")
async def get_my_subscription(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get current user's subscription.

    Creates a Basic (free) subscription if none exists.
    """
    service = SubscriptionService(supabase, user_id)
    subscription = service.get_or_create_basic_subscription()
    return success_response(200, "Subscription retrieved", {"subscription": subscription})


@subscription_router.post("/checkout")
async def create_checkout_session(
    request: CheckoutSessionRequest,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Create a Stripe checkout session for plan upgrade.

    Returns checkout URL to redirect user to Stripe.
    """
    service = SubscriptionService(supabase, user_id)
    
    # Get the plan
    plan = service.get_plan_by_id(request.plan_id)
    
    # For now, return a mock checkout URL (Stripe integration later)
    # In production, this would create a real Stripe Checkout Session
    checkout_data = {
        "checkout_url": f"https://checkout.stripe.com/mock?plan={plan['name']}&interval={request.billing_interval}",
        "session_id": f"mock_session_{user_id}_{plan['id']}",
        "plan": plan,
        "billing_interval": request.billing_interval,
        "message": "Stripe integration pending - using mock checkout URL"
    }
    
    return success_response(200, "Checkout session created", checkout_data)


@subscription_router.post("/cancel")
async def cancel_subscription(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Cancel the current subscription.

    User will retain access until end of billing period.
    """
    service = SubscriptionService(supabase, user_id)
    subscription = service.cancel_subscription()
    return success_response(200, "Subscription canceled", {"subscription": subscription})


@subscription_router.get("/portal")
async def get_customer_portal(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get Stripe Customer Portal URL.

    Allows user to manage payment methods and billing.
    """
    service = SubscriptionService(supabase, user_id)
    subscription = service.get_user_subscription()
    
    if not subscription or not subscription.get("stripe_customer_id"):
        return success_response(200, "No payment history", {
            "portal_url": None,
            "message": "Upgrade to a paid plan first"
        })
    
    # Mock portal URL - real Stripe integration would create actual portal session
    portal_data = {
        "portal_url": f"https://billing.stripe.com/mock/portal/{subscription['stripe_customer_id']}",
        "message": "Stripe integration pending - using mock portal URL"
    }
    
    return success_response(200, "Portal URL generated", portal_data)
