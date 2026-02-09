"""
Feedback related background tasks.
Handles feedback requests and score updates from outcomes.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import create_client

from app.api.core.config import settings
from app.api.core.logging import get_logger

logger = get_logger(__name__, context="worker")

# Days after match to request feedback
FEEDBACK_REQUEST_DELAY_DAYS = 3


# ===========================================
# FEEDBACK REQUEST TASK
# ===========================================


async def request_feedback(ctx: dict) -> dict[str, Any]:
    """
    Send 'We Connected' feedback requests.
    
    - Find matches older than 3 days without feedback
    - Send notification to request feedback
    
    Schedule: 4x daily (every 6 hours)
    """

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=FEEDBACK_REQUEST_DELAY_DAYS)

    # Find matches older than cutoff without feedback request
    matches = supabase.table("matches").select("*").eq(
        "status", "ACTIVE"
    ).lt("matched_at", cutoff.isoformat()).is_(
        "feedback_requested_at", "null"
    ).limit(100).execute()

    requests_sent = 0
    for match in matches.data or []:
        # Check if there's been any messaging activity
        first_message = supabase.table("messages").select("id").eq(
            "match_id", match["id"]
        ).limit(1).execute()

        if not first_message.data:
            # No messages, match might have expired without interaction
            continue

        # Send feedback request to both users
        await _send_feedback_request(supabase, match, match["user1_id"])
        await _send_feedback_request(supabase, match, match["user2_id"])

        # Mark as requested
        supabase.table("matches").update({
            "feedback_requested_at": now.isoformat(),
        }).eq("id", match["id"]).execute()

        requests_sent += 1

    return {
        "feedback_requests_sent": requests_sent * 2,  # Both users
    }


async def _send_feedback_request(
    supabase,
    match: dict,
    user_id: str,
) -> None:
    """Send feedback request notification to a user."""

    # Get other user's name
    other_user_id = (
        match["user2_id"]
        if match["user1_id"] == user_id
        else match["user1_id"]
    )

    profile = supabase.table("profiles").select("display_name").eq(
        "id", other_user_id
    ).single().execute()

    name = profile.data.get("display_name", "them") if profile.data else "them"

    # TODO: Implement push notification
    logger.info(f"Requesting feedback from user {user_id} about {name}")


# ===========================================
# FEEDBACK PROCESSING TASK
# ===========================================


async def process_feedback(ctx: dict, feedback_id: str) -> dict[str, Any]:
    """
    Process submitted feedback and update user scores.
    
    This is the 'secret sauce' - we use real-world outcomes
    to train our matching algorithm.
    
    Schedule: On demand (triggered when feedback is submitted)
    """

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    feedback = supabase.table("connection_feedback").select("*").eq(
        "id", feedback_id
    ).single().execute()

    if not feedback.data:
        return {"error": "Feedback not found"}

    data = feedback.data
    match = supabase.table("matches").select("*").eq(
        "id", data["match_id"]
    ).single().execute()

    if not match.data:
        return {"error": "Match not found"}

    # Get the OTHER user (the one being rated)
    other_user_id = (
        match.data["user2_id"]
        if match.data["user1_id"] == data["user_id"]
        else match.data["user1_id"]
    )

    # Get their current scores
    scores = supabase.table("user_scores").select("*").eq(
        "user_id", other_user_id
    ).maybe_single().execute()

    if not scores.data:
        # Create initial scores
        supabase.table("user_scores").insert({
            "user_id": other_user_id,
        }).execute()
        scores = supabase.table("user_scores").select("*").eq(
            "user_id", other_user_id
        ).single().execute()

    current = scores.data

    # Count total feedbacks about this user
    total = supabase.table("connection_feedback").select(
        "id", count="exact"
    ).eq("user_id", other_user_id).execute()
    feedback_count = total.count or 1

    # 1. Update dates_from_matches_ratio
    current_dates = current.get("dates_from_matches_ratio", 0.0)
    new_outcome = 1.0 if data["did_you_meet"] else 0.0
    new_dates_ratio = _recalculate_ratio(current_dates, new_outcome, feedback_count)

    # 2. Update positive_feedback_ratio
    current_positive = current.get("positive_feedback_ratio", 0.5)
    quality = data.get("connection_quality")
    if quality:
        if quality >= 4:
            outcome = 1.0
        elif quality <= 2:
            outcome = 0.0
        else:
            outcome = 0.5
    else:
        outcome = 0.5 if data["did_you_meet"] else 0.3

    new_positive = _recalculate_ratio(current_positive, outcome, feedback_count)

    # 3. Ghost tracking
    ghost_count = current.get("ghost_count", 0)
    if data.get("negative_factors") and "ghosted" in data["negative_factors"]:
        ghost_count += 1

    # Update scores
    supabase.table("user_scores").update({
        "dates_from_matches_ratio": new_dates_ratio,
        "positive_feedback_ratio": new_positive,
        "ghost_count": ghost_count,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", other_user_id).execute()

    return {
        "other_user_id": other_user_id,
        "dates_ratio_updated": new_dates_ratio,
        "positive_ratio_updated": new_positive,
        "ghost_count": ghost_count,
    }


def _recalculate_ratio(current: float, new_outcome: float, total: int) -> float:
    """Recalculate rolling ratio with new outcome."""

    if total <= 1:
        return new_outcome

    # Weighted average with decay
    weight = min(0.3, 1.0 / total)
    return (1 - weight) * current + weight * new_outcome
