"""
Chat service for message management.
"""

from datetime import UTC, datetime
from uuid import UUID

from supabase import Client

from app.api.core.custom_exceptions.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from app.api.core.logging import get_logger
from app.api.core.redis_client import (
    cache_match,
    cache_profile,
    get_cached_match,
    get_cached_profile,
    invalidate_conversation_cache,
    invalidate_match_cache,
)
from app.api.modules.v1.chat.schemas import (
    ConversationListResponse,
    ConversationPreview,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    MessageSender,
    ReadCursorResponse,
    SendMessageResponse,
)

logger = get_logger(__name__)


# Default limit for message pagination
DEFAULT_MESSAGE_LIMIT = 50


class ChatService:
    """Service for chat/message operations."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def get_conversations(
        self,
        user_id: UUID,
        limit: int = 50,
    ) -> ConversationListResponse:
        """
        Get all conversations (matches) for a user.
        Returns matches with last message preview.
        """

        # Get all active matches
        matches_query = (
            self.supabase.table("matches")
            .select("*")
            .or_(f"user1_id.eq.{user_id},user2_id.eq.{user_id}")
            .ilike("status", "active")
            .order("matched_at", desc=True)
            .limit(limit)
        )

        matches_result = matches_query.execute()

        conversations = []

        for match_data in matches_result.data or []:
            conversation = await self._build_conversation_preview(match_data, user_id)
            conversations.append(conversation)

        # Sort by last message time (most recent first)
        conversations.sort(key=lambda c: c.last_message_at or c.matched_at, reverse=True)

        return ConversationListResponse(
            conversations=conversations,
            total_count=len(conversations),
        )

    async def get_messages(
        self,
        user_id: UUID,
        match_id: UUID,
        cursor: str | None = None,
        limit: int = DEFAULT_MESSAGE_LIMIT,
    ) -> MessageListResponse:
        """
        Get paginated messages for a match.
        Cursor is ISO timestamp for pagination.
        """

        # Verify user is part of this match
        match = await self._verify_match_access(user_id, match_id)

        other_user_id = (
            match["user2_id"] if match["user1_id"] == str(user_id) else match["user1_id"]
        )

        # Build query
        query = self.supabase.table("messages").select("*").eq("match_id", str(match_id))

        # Apply cursor if provided (get messages older than cursor)
        if cursor:
            query = query.lt("created_at", cursor)

        # Order by created_at descending (newest first)
        query = query.order("created_at", desc=True).limit(limit + 1)

        result = query.execute()

        messages_data = result.data or []
        has_more = len(messages_data) > limit

        if has_more:
            messages_data = messages_data[:limit]

        # Get other user's read cursor for read receipt rendering
        other_user_cursor = self._get_read_cursor(match_id, UUID(other_user_id))
        other_user_last_read_at = None
        if other_user_cursor and other_user_cursor.get("last_read_at"):
            other_user_last_read_at = datetime.fromisoformat(
                other_user_cursor["last_read_at"].replace("Z", "+00:00")
            )

        other_user_sender = None
        if messages_data:
            has_other_user_messages = any(
                msg.get("sender_id") != str(user_id) for msg in messages_data
            )
            if has_other_user_messages:
                other_user_sender = await self._get_sender_info(other_user_id)

        # Build message responses
        messages = []
        for msg in messages_data:
            message = await self._build_message_response(
                msg,
                user_id,
                other_user_last_read_at=other_user_last_read_at,
                sender_override=other_user_sender,
            )
            messages.append(message)

        # Return in chronological order (oldest to newest for chat display)
        messages.reverse()

        next_cursor = None
        if has_more and messages:
            # Cursor is the oldest message's created_at
            next_cursor = messages[0].created_at.isoformat()

        return MessageListResponse(
            messages=messages,
            has_more=has_more,
            next_cursor=next_cursor,
            other_user_read_cursor=self._build_read_cursor_response(other_user_cursor)
            if other_user_cursor
            else None,
        )

    async def send_message(
        self,
        user_id: UUID,
        match_id: UUID,
        message_data: MessageCreate,
    ) -> SendMessageResponse:
        """
        Send a message in a match conversation.
        Updates first_message_at if this is the first message.
        """

        # Verify user is part of this match
        match = await self._verify_match_access(user_id, match_id)

        # Check match is still active
        if match["status"].upper() != "ACTIVE":
            raise BadRequestError(
                message="Cannot send message to inactive match",
                code="MATCH_NOT_ACTIVE",
            )

        # Check match hasn't expired
        if match.get("expires_at"):
            expires_at = datetime.fromisoformat(match["expires_at"].replace("Z", "+00:00"))
            if expires_at < datetime.now(UTC):
                raise BadRequestError(
                    message="Match has expired",
                    code="MATCH_EXPIRED",
                )

        # Check if this is the first message
        first_message_sent = match.get("first_message_at") is None

        # Insert message
        now = datetime.now(UTC)
        message_insert = {
            "match_id": str(match_id),
            "sender_id": str(user_id),
            "content": message_data.content,
            "message_type": message_data.message_type,
            "created_at": now.isoformat(),
        }

        result = self.supabase.table("messages").insert(message_insert).execute()

        if not result.data:
            raise BadRequestError(
                message="Failed to send message",
                code="MESSAGE_SEND_FAILED",
            )

        new_message = result.data[0]

        # Update match first_message_at if this is the first message
        if first_message_sent:
            self.supabase.table("matches").update(
                {
                    "first_message_at": now.isoformat(),
                }
            ).eq("id", str(match_id)).execute()

            # Invalidate match cache since we updated it
            await invalidate_match_cache(str(match_id))

        # Invalidate conversation cache for both users
        other_user_id = (
            match["user2_id"] if match["user1_id"] == str(user_id) else match["user1_id"]
        )
        await invalidate_conversation_cache(str(user_id))
        await invalidate_conversation_cache(other_user_id)

        logger.info(f"Message sent in match {match_id}, caches invalidated")

        # Build response
        message_response = await self._build_message_response(new_message, user_id)

        return SendMessageResponse(
            message=message_response,
            first_message_sent=first_message_sent,
        )

    async def mark_as_read(
        self,
        user_id: UUID,
        match_id: UUID,
        last_read_message_id: UUID | None = None,
    ) -> int:
        """
        Mark messages as read.
        Returns count of messages marked as read.
        """

        # Verify user is part of this match
        await self._verify_match_access(user_id, match_id)

        now = datetime.now(UTC)

        # Determine the last read message (explicit or most recent from other user)
        message_row = None
        if last_read_message_id:
            msg = (
                self.supabase.table("messages")
                .select("id, created_at")
                .eq("id", str(last_read_message_id))
                .maybe_single()
                .execute()
            )
            message_row = msg.data
        else:
            msg = (
                self.supabase.table("messages")
                .select("id, created_at")
                .eq("match_id", str(match_id))
                .neq("sender_id", str(user_id))
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if msg.data:
                message_row = msg.data[0]

        if not message_row:
            return 0

        last_read_message_id = UUID(message_row["id"])
        last_read_at = message_row["created_at"]

        # Get previous cursor for incremental count
        previous_cursor = self._get_read_cursor(match_id, user_id)
        previous_last_read_at = previous_cursor.get("last_read_at") if previous_cursor else None

        # Upsert read cursor
        self.supabase.table("message_read_cursors").upsert(
            {
                "match_id": str(match_id),
                "user_id": str(user_id),
                "last_read_message_id": str(last_read_message_id),
                "last_read_at": last_read_at,
                "updated_at": now.isoformat(),
            },
            on_conflict="match_id,user_id",
        ).execute()

        # Count messages newly marked as read
        count_query = (
            self.supabase.table("messages")
            .select("id", count="exact")
            .eq("match_id", str(match_id))
            .neq("sender_id", str(user_id))
            .lte("created_at", last_read_at)
        )

        if previous_last_read_at:
            count_query = count_query.gt("created_at", previous_last_read_at)

        count_result = count_query.execute()

        return count_result.count or 0

    # ===========================================
    # PRIVATE HELPERS
    # ===========================================

    async def _verify_match_access(
        self,
        user_id: UUID,
        match_id: UUID,
    ) -> dict:
        """Verify user has access to this match. Returns match data."""

        # Try to get from cache first
        match_data = await get_cached_match(str(match_id))

        if not match_data:
            # Cache miss - fetch from database
            result = (
                self.supabase.table("matches")
                .select("*")
                .eq("id", str(match_id))
                .single()
                .execute()
            )

            if not result.data:
                raise NotFoundError(message="Match not found", code="MATCH_NOT_FOUND")

            match_data = result.data

            # Cache the match data
            await cache_match(str(match_id), match_data)
            logger.debug(f"Match {match_id} cached")
        else:
            logger.debug(f"Match {match_id} retrieved from cache")

        if str(user_id) not in [match_data["user1_id"], match_data["user2_id"]]:
            raise ForbiddenError(
                message="You are not part of this match",
                code="NOT_YOUR_MATCH",
            )

        return match_data

    async def _build_message_response(
        self,
        msg_data: dict,
        current_user_id: UUID,
        other_user_last_read_at: datetime | None = None,
        sender_override: MessageSender | None = None,
    ) -> MessageResponse:
        """Build message response from raw data."""

        sender_id = msg_data["sender_id"]
        is_mine = sender_id == str(current_user_id)

        # Get sender info if not current user
        sender = None
        if not is_mine:
            sender = sender_override or await self._get_sender_info(sender_id)

        created_at = datetime.fromisoformat(msg_data["created_at"].replace("Z", "+00:00"))

        read_at = None
        if is_mine and other_user_last_read_at:
            if created_at <= other_user_last_read_at:
                read_at = other_user_last_read_at

        return MessageResponse(
            id=UUID(msg_data["id"]),
            match_id=UUID(msg_data["match_id"]),
            sender_id=UUID(sender_id),
            sender=sender,
            content=msg_data["content"],
            message_type=msg_data.get("message_type", "text"),
            created_at=created_at,
            read_at=read_at,
            is_mine=is_mine,
        )

    async def _get_sender_info(self, user_id: str) -> MessageSender:
        """Get sender basic info for message display."""

        # Try to get from cache first
        cached_data = await get_cached_profile(user_id)

        if cached_data:
            logger.debug(f"Profile {user_id} retrieved from cache")
            return MessageSender(
                id=UUID(user_id),
                display_name=cached_data.get("display_name"),
                avatar_url=cached_data.get("avatar_url"),
            )

        # Cache miss - fetch from database
        profile = (
            self.supabase.table("profiles")
            .select("id, display_name")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        photo = (
            self.supabase.table("photos")
            .select("storage_path")
            .eq("user_id", user_id)
            .eq("is_primary", True)
            .limit(1)
            .execute()
        )

        profile_data = profile.data[0] if profile.data else {}
        photo_data = photo.data[0] if photo.data else {}

        avatar_url = None
        if photo_data.get("storage_path"):
            avatar_url = self.supabase.storage.from_("photos").get_public_url(
                photo_data["storage_path"]
            )

        # Cache the profile data
        cache_data = {
            "display_name": profile_data.get("display_name"),
            "avatar_url": avatar_url,
        }
        await cache_profile(user_id, cache_data)
        logger.debug(f"Profile {user_id} cached")

        return MessageSender(
            id=UUID(user_id),
            display_name=profile_data.get("display_name"),
            avatar_url=avatar_url,
        )

    async def _build_conversation_preview(
        self,
        match_data: dict,
        user_id: UUID,
    ) -> ConversationPreview:
        """Build conversation preview from match data."""

        # Determine matched user
        matched_user_id = (
            match_data["user2_id"]
            if match_data["user1_id"] == str(user_id)
            else match_data["user1_id"]
        )

        # Try to get matched user info from cache
        cached_profile = await get_cached_profile(matched_user_id)

        if cached_profile:
            logger.debug(f"Profile {matched_user_id} retrieved from cache for conversation")
            profile_data = {"display_name": cached_profile.get("display_name")}
            avatar_url = cached_profile.get("avatar_url")
        else:
            # Cache miss - fetch from database
            profile = (
                self.supabase.table("profiles")
                .select("display_name")
                .eq("id", matched_user_id)
                .limit(1)
                .execute()
            )

            photo = (
                self.supabase.table("photos")
                .select("storage_path")
                .eq("user_id", matched_user_id)
                .eq("is_primary", True)
                .limit(1)
                .execute()
            )

            profile_data = profile.data[0] if profile.data else {}
            photo_data = photo.data[0] if photo.data else {}

            avatar_url = None
            if photo_data.get("storage_path"):
                avatar_url = self.supabase.storage.from_("photos").get_public_url(
                    photo_data["storage_path"]
                )

            # Cache the profile data
            cache_data = {
                "display_name": profile_data.get("display_name"),
                "avatar_url": avatar_url,
            }
            await cache_profile(matched_user_id, cache_data)
            logger.debug(f"Profile {matched_user_id} cached for conversation")

        # Get last message
        last_msg = (
            self.supabase.table("messages")
            .select("*")
            .eq("match_id", match_data["id"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        # Count unread using read cursor
        cursor = self._get_read_cursor(UUID(match_data["id"]), user_id)
        unread_query = (
            self.supabase.table("messages")
            .select("id", count="exact")
            .eq("match_id", match_data["id"])
            .neq("sender_id", str(user_id))
        )

        if cursor and cursor.get("last_read_at"):
            unread_query = unread_query.gt("created_at", cursor["last_read_at"])

        unread = unread_query.execute()

        # Calculate expiration
        hours_until_expiry = None
        is_expiring_soon = False

        if match_data.get("expires_at") and match_data["status"].upper() == "ACTIVE":
            expires_at = datetime.fromisoformat(match_data["expires_at"].replace("Z", "+00:00"))
            now = datetime.now(UTC)
            if expires_at > now:
                hours_until_expiry = (expires_at - now).total_seconds() / 3600
                is_expiring_soon = hours_until_expiry <= 12

        last_message_at = None
        last_message_is_mine = False
        if last_msg.data:
            last_message_val = last_msg.data[0]
            last_message_at = datetime.fromisoformat(
                last_message_val["created_at"].replace("Z", "+00:00")
            )
            last_message_is_mine = last_message_val["sender_id"] == str(user_id)

        last_msg_content = last_msg.data[0].get("content", "")[:50] if last_msg.data else None

        return ConversationPreview(
            match_id=UUID(match_data["id"]),
            matched_user_id=UUID(matched_user_id),
            matched_user_display_name=profile_data.get("display_name"),
            matched_user_avatar_url=avatar_url,
            matched_at=datetime.fromisoformat(match_data["matched_at"].replace("Z", "+00:00")),
            last_message=last_msg_content,
            last_message_at=last_message_at,
            last_message_is_mine=last_message_is_mine,
            unread_count=unread.count or 0,
            has_started_chatting=match_data.get("first_message_at") is not None,
            hours_until_expiry=round(hours_until_expiry, 1) if hours_until_expiry else None,
            is_expiring_soon=is_expiring_soon,
        )

    def _get_read_cursor(self, match_id: UUID, user_id: UUID) -> dict | None:
        """
        Fetch read cursor for a user/match.

        Note: This is a synchronous method called from sync context,
        so Redis caching is not used here to avoid event loop complexity.
        """
        result = (
            self.supabase.table("message_read_cursors")
            .select("match_id, user_id, last_read_message_id, last_read_at, updated_at")
            .eq("match_id", str(match_id))
            .eq("user_id", str(user_id))
            .maybe_single()
            .execute()
        )

        if not result:
            return None

        return result.data

    def _build_read_cursor_response(self, data: dict) -> ReadCursorResponse:
        """Build ReadCursorResponse from raw data."""

        last_read_at = None
        updated_at = None

        if data.get("last_read_at"):
            last_read_at = datetime.fromisoformat(data["last_read_at"].replace("Z", "+00:00"))
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))

        return ReadCursorResponse(
            match_id=UUID(data["match_id"]),
            user_id=UUID(data["user_id"]),
            last_read_message_id=UUID(data["last_read_message_id"])
            if data.get("last_read_message_id")
            else None,
            last_read_at=last_read_at,
            updated_at=updated_at,
        )
