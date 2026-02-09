"""
Chat-related background tasks.
Handles cache invalidation and read cursor updates after message sends.
"""

from datetime import datetime, UTC
from typing import Any

from supabase import create_client

from app.api.core.config import settings
from app.api.core.logging import get_logger
from app.api.core.redis_client import (
    invalidate_conversation_cache,
    invalidate_match_cache,
    invalidate_match_stats,
)

logger = get_logger(__name__, context="worker")


async def invalidate_message_caches(
    ctx: dict,
    match_id: str,
    sender_id: str,
    other_user_id: str,
    invalidate_match: bool = False,
) -> dict[str, Any]:
    """
    Invalidate Redis caches after a message is sent.

    This is safe to retry and idempotent - cache invalidation
    either succeeds or the cache naturally expires.

    Args:
        ctx: ARQ context (contains redis connection)
        match_id: The match/conversation ID
        sender_id: The sender's user ID
        other_user_id: The recipient's user ID
        invalidate_match: Whether to also invalidate match cache

    Returns:
        Dict with operation results
    """
    results = {
        "sender_cache_invalidated": False,
        "other_user_cache_invalidated": False,
        "match_cache_invalidated": False,
        "other_user_stats_invalidated": False,
    }

    try:
        # Invalidate conversation cache for both users
        results["sender_cache_invalidated"] = await invalidate_conversation_cache(sender_id)
        results["other_user_cache_invalidated"] = await invalidate_conversation_cache(
            other_user_id
        )
        
        # Invalidate match stats cache for recipient (their unread count changed)
        results["other_user_stats_invalidated"] = await invalidate_match_stats(other_user_id)

        # Invalidate match cache if first message
        if invalidate_match:
            results["match_cache_invalidated"] = await invalidate_match_cache(match_id)

        logger.info(
            f"Cache invalidation complete for match {match_id}",
            extra={"results": results},
        )

    except Exception as e:
        logger.error(f"Cache invalidation failed for match {match_id}: {e}")
        # Re-raise to trigger ARQ retry
        raise

    return results


async def update_sender_read_cursor(
    ctx: dict,
    match_id: str,
    user_id: str,
    message_id: str,
    message_created_at: str,
) -> dict[str, Any]:
    """
    Update the sender's read cursor after sending a message.

    When a user sends a message, they've implicitly "read" up to that point.
    This task updates their read cursor asynchronously.

    Args:
        ctx: ARQ context
        match_id: The match/conversation ID
        user_id: The sender's user ID
        message_id: The ID of the message just sent
        message_created_at: ISO timestamp of the message

    Returns:
        Dict with operation result
    """
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

        now = datetime.now(UTC)

        # Upsert read cursor
        supabase.table("message_read_cursors").upsert(
            {
                "match_id": match_id,
                "user_id": user_id,
                "last_read_message_id": message_id,
                "last_read_at": message_created_at,
                "updated_at": now.isoformat(),
            },
            on_conflict="match_id,user_id",
        ).execute()

        logger.info(f"Read cursor updated for user {user_id} in match {match_id}")

        return {"success": True, "user_id": user_id, "match_id": match_id}

    except Exception as e:
        logger.error(f"Read cursor update failed for user {user_id}: {e}")
        raise


async def enqueue_post_message_tasks(
    match_id: str,
    sender_id: str,
    other_user_id: str,
    message_id: str,
    message_created_at: str | None = None,
    invalidate_match_cache: bool = False,
) -> None:
    """
    Enqueue all post-message async tasks.

    Called from ChatService.send_message() after successful INSERT.
    This is a fire-and-forget operation - if enqueueing fails,
    the message was already saved successfully.

    Args:
        match_id: The match/conversation ID
        sender_id: The sender's user ID
        other_user_id: The recipient's user ID
        message_id: The ID of the message just sent
        message_created_at: ISO timestamp of the message
        invalidate_match_cache: Whether to invalidate match cache
    """
    from arq import create_pool
    from app.workers.settings import REDIS_SETTINGS

    try:
        pool = await create_pool(REDIS_SETTINGS)

        # Enqueue cache invalidation
        await pool.enqueue_job(
            "invalidate_message_caches",
            match_id=match_id,
            sender_id=sender_id,
            other_user_id=other_user_id,
            invalidate_match=invalidate_match_cache,
        )

        # Enqueue read cursor update for sender
        if message_created_at:
            await pool.enqueue_job(
                "update_sender_read_cursor",
                match_id=match_id,
                user_id=sender_id,
                message_id=message_id,
                message_created_at=message_created_at,
            )

        await pool.close()

        logger.debug(f"Post-message tasks enqueued for match {match_id}")

    except Exception as e:
        # Log but don't fail - message was already saved
        logger.warning(f"Failed to enqueue post-message tasks: {e}")
