"""
Matching related background tasks.
Handles match expiration, ghost tracking, and queue refresh.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from supabase import create_client

from app.api.core.config import settings
from app.api.core.logging import get_logger

logger = get_logger(__name__, context="worker")
# MATCH EXPIRATION TASK
# ===========================================


async def process_match_expirations(ctx: dict) -> dict[str, Any]:
    """
    Process matches approaching expiration.
    
    - Send reminder notifications 12 hours before expiry
    - Expire matches without first message after 72 hours
    - Update ghost counts for expired matches
    
    Schedule: Every hour
    """

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    now = datetime.now(timezone.utc)
    twelve_hours_from_now = now + timedelta(hours=12)

    # Find matches expiring in next 12 hours without first message
    expiring = supabase.table("matches").select("*").eq(
        "status", "ACTIVE"
    ).is_("first_message_at", "null").lt(
        "expires_at", twelve_hours_from_now.isoformat()
    ).execute()

    reminders_sent = 0
    matches_expired = 0

    for match in expiring.data or []:
        expires_at = datetime.fromisoformat(
            match["expires_at"].replace("Z", "+00:00")
        )
        hours_remaining = (expires_at - now).total_seconds() / 3600

        # Send 12-hour reminder if not already sent
        if hours_remaining <= 12 and not match.get("reminder_12h_sent"):
            await _send_expiration_reminder(supabase, match, hours=12)

            supabase.table("matches").update({
                "reminder_12h_sent": True,
            }).eq("id", match["id"]).execute()

            reminders_sent += 1

        # Expire match if past deadline
        if hours_remaining <= 0:
            supabase.table("matches").update({
                "status": "EXPIRED",
            }).eq("id", match["id"]).execute()

            # Increment ghost count for both users
            await _increment_ghost_count(supabase, match["user1_id"])
            await _increment_ghost_count(supabase, match["user2_id"])

            matches_expired += 1

    return {
        "reminders_sent": reminders_sent,
        "matches_expired": matches_expired,
    }


async def _send_expiration_reminder(
    supabase,
    match: dict,
    hours: int,
) -> None:
    """Send expiration reminder notification to both users."""

    # TODO: Implement push notification
    # For now, just log it
    logger.info(f"Match {match['id']} expires in {hours} hours - reminder pending")


async def _increment_ghost_count(supabase, user_id: str) -> None:
    """Increment ghost count for a user."""

    # Get current scores
    scores = supabase.table("user_scores").select("ghost_count").eq(
        "user_id", user_id
    ).maybe_single().execute()

    if scores.data:
        new_count = (scores.data.get("ghost_count") or 0) + 1
        supabase.table("user_scores").update({
            "ghost_count": new_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("user_id", user_id).execute()
    else:
        # Create initial scores record
        supabase.table("user_scores").insert({
            "user_id": user_id,
            "ghost_count": 1,
        }).execute()


# ===========================================
# DISCOVERY QUEUE REFRESH TASK
# ===========================================


async def refresh_discovery_queues(ctx: dict) -> dict[str, Any]:
    """
    Refresh stale discovery queues.
    
    - Delete expired queue entries
    - Refresh queues for active users
    
    Schedule: Every hour
    """

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    now = datetime.now(timezone.utc)

    # Delete expired queue entries
    deleted = supabase.table("discovery_queue").delete().lt(
        "expires_at", now.isoformat()
    ).execute()

    expired_count = len(deleted.data) if deleted.data else 0

    # Find active users with empty or stale queues
    one_hour_ago = now - timedelta(hours=1)

    stale_users = supabase.table("user_scores").select("user_id").gt(
        "last_active", one_hour_ago.isoformat()
    ).limit(100).execute()

    refreshed = 0
    for user in stale_users.data or []:
        # Check if queue needs refresh
        queue = supabase.table("discovery_queue").select(
            "id", count="exact"
        ).eq("user_id", user["user_id"]).gt(
            "expires_at", now.isoformat()
        ).execute()

        if (queue.count or 0) < 10:
            # Queue needs refresh - will be done on next request
            # Could trigger refresh here but better to do it lazily
            refreshed += 1

    return {
        "expired_entries_deleted": expired_count,
        "users_needing_refresh": refreshed,
    }


# ===========================================
# USER SCORE RECALCULATION TASK
# ===========================================


async def recalculate_user_scores(ctx: dict) -> dict[str, Any]:
    """
    Full recalculation of user behavioral scores.
    
    - Profile completion score
    - Response rate
    - Average response time
    - Days since signup
    
    Schedule: Daily at 3 AM
    """

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    # Get all profiles
    profiles = supabase.table("profiles").select("id, created_at").execute()

    updated = 0
    for profile in profiles.data or []:
        user_id = profile["id"]

        # Calculate profile completion
        profile_data = supabase.table("profiles").select("*").eq(
            "id", user_id
        ).single().execute()

        completion = await _calculate_profile_completion(profile_data.data)

        # Calculate response rate from messages
        messages_received = supabase.table("messages").select(
            "id", count="exact"
        ).neq("sender_id", user_id).execute()

        messages_replied = supabase.table("messages").select(
            "id", count="exact"
        ).eq("sender_id", user_id).execute()

        received = messages_received.count or 0
        replied = messages_replied.count or 0
        response_rate = replied / received if received > 0 else 0.5

        # Calculate days since signup
        created_at = datetime.fromisoformat(
            profile["created_at"].replace("Z", "+00:00")
        )
        days_since_signup = (datetime.now(timezone.utc) - created_at).days

        # Update or create scores
        existing = supabase.table("user_scores").select("id").eq(
            "user_id", user_id
        ).maybe_single().execute()

        score_data = {
            "profile_completion": completion,
            "response_rate": min(1.0, response_rate),
            "days_since_signup": days_since_signup,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if existing.data:
            supabase.table("user_scores").update(score_data).eq(
                "user_id", user_id
            ).execute()
        else:
            supabase.table("user_scores").insert({
                "user_id": user_id,
                **score_data,
            }).execute()

        updated += 1

    return {
        "users_updated": updated,
    }


async def _calculate_profile_completion(profile: dict) -> float:
    """Calculate profile completion score (0.0 - 1.0)."""

    if not profile:
        return 0.0

    score = 0.0
    total = 0.0

    # Display name (10%)
    total += 0.10
    if profile.get("display_name"):
        score += 0.10

    # Age (10%)
    total += 0.10
    if profile.get("age"):
        score += 0.10

    # Gender (10%)
    total += 0.10
    if profile.get("gender"):
        score += 0.10

    # Bio (20%)
    total += 0.20
    bio = profile.get("bio", "")
    if bio:
        # Partial credit for short bios
        if len(bio) >= 100:
            score += 0.20
        elif len(bio) >= 50:
            score += 0.15
        elif len(bio) >= 20:
            score += 0.10

    # Prompts (20%)
    total += 0.20
    prompts = profile.get("prompts", []) or []
    if len(prompts) >= 3:
        score += 0.20
    elif len(prompts) >= 2:
        score += 0.15
    elif len(prompts) >= 1:
        score += 0.10

    # Height (10%)
    total += 0.10
    if profile.get("height_cm"):
        score += 0.10

    # Location (20%)
    total += 0.20
    if profile.get("location_lat") and profile.get("location_lng"):
        score += 0.20

    return score / total if total > 0 else 0.0
