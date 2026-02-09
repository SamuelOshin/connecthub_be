"""
Discovery related background tasks.
Handles queue refresh and stale data cleanup.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import create_client

from app.api.core.config import settings


# ===========================================
# QUEUE CLEANUP TASK
# ===========================================


async def cleanup_discovery_queues(ctx: dict) -> dict[str, Any]:
    """
    Clean up expired discovery queue entries.
    
    Schedule: Every hour
    """

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    now = datetime.now(timezone.utc)

    # Delete expired entries
    result = supabase.table("discovery_queue").delete().lt(
        "expires_at", now.isoformat()
    ).execute()

    deleted = len(result.data) if result.data else 0

    return {
        "expired_entries_deleted": deleted,
    }


# ===========================================
# SWIPE ARCHIVAL TASK
# ===========================================


async def cleanup_old_swipes(ctx: dict) -> dict[str, Any]:
    """
    Archive swipe data older than 90 days.
    We keep pass swipes for a shorter period than likes.
    
    Schedule: Weekly
    """

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    now = datetime.now(timezone.utc)
    ninety_days_ago = now - timedelta(days=90)

    # Delete old LEFT swipes (passes) - we don't need these long-term
    result = supabase.table("swipes").delete().eq(
        "direction", "LEFT"
    ).lt("created_at", ninety_days_ago.isoformat()).execute()

    passes_deleted = len(result.data) if result.data else 0

    return {
        "old_passes_archived": passes_deleted,
    }


# ===========================================
# ACTIVITY TRACKING TASK  
# ===========================================


async def update_last_active(ctx: dict, user_id: str) -> dict[str, Any]:
    """
    Update user's last active timestamp.
    Called when user takes actions in the app.
    
    Schedule: On demand
    """

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    now = datetime.now(timezone.utc)

    # Update or create user scores with last_active
    existing = supabase.table("user_scores").select("id").eq(
        "user_id", user_id
    ).maybe_single().execute()

    if existing.data:
        supabase.table("user_scores").update({
            "last_active": now.isoformat(),
        }).eq("user_id", user_id).execute()
    else:
        supabase.table("user_scores").insert({
            "user_id": user_id,
            "last_active": now.isoformat(),
        }).execute()

    return {
        "user_id": user_id,
        "last_active": now.isoformat(),
    }
