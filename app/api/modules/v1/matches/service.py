"""
Matches service for match management.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from supabase import Client, create_client

from app.api.core.config import settings

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ForbiddenError,
)
from app.api.modules.v1.matches.schemas import (
    MatchDetail,
    MatchListItem,
    MatchListResponse,
    MatchedUserInfo,
    UnmatchResponse,
)
from app.api.modules.v1.discovery.scoring import get_response_badge


EXPIRING_SOON_HOURS = 12


class MatchesService:
    """Service for match management operations."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def get_matches(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> MatchListResponse:
        """
        Get all matches for a user.
        """

        query = self.supabase.table("matches").select("*").or_(
            f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
        )

        if status:
            query = query.eq("status", status)

        query = query.order("matched_at", desc=True).limit(limit)
        result = query.execute()

        matches = []
        active_count = 0
        expiring_soon_count = 0

        for match_data in result.data or []:
            match_item = await self._build_match_list_item(
                match_data, user_id
            )
            matches.append(match_item)

            if match_data["status"].upper() == "ACTIVE":
                active_count += 1
                if match_item.is_expiring_soon:
                    expiring_soon_count += 1

        return MatchListResponse(
            matches=matches,
            total_count=len(matches),
            active_count=active_count,
            expiring_soon_count=expiring_soon_count,
        )

    async def get_match(self, user_id: UUID, match_id: UUID) -> MatchDetail:
        """
        Get detailed match information.
        """

        result = self.supabase.table("matches").select("*").eq(
            "id", str(match_id)
        ).single().execute()

        if not result.data:
            raise NotFoundError(message="Match not found", code="MATCH_NOT_FOUND")

        match_data = result.data

        # Verify user is part of this match
        if str(user_id) not in [match_data["user1_id"], match_data["user2_id"]]:
            raise ForbiddenError(
                message="You are not part of this match",
                code="NOT_YOUR_MATCH",
            )

        return await self._build_match_detail(match_data, user_id)

    async def unmatch(self, user_id: UUID, match_id: UUID) -> UnmatchResponse:
        """
        Unmatch with a user.
        """

        # Get match
        result = self.supabase.table("matches").select("*").eq(
            "id", str(match_id)
        ).single().execute()

        if not result.data:
            raise NotFoundError(message="Match not found", code="MATCH_NOT_FOUND")

        match_data = result.data

        # Verify user is part of this match
        if str(user_id) not in [match_data["user1_id"], match_data["user2_id"]]:
            raise ForbiddenError(
                message="You are not part of this match",
                code="NOT_YOUR_MATCH",
            )

        # Update match status
        self.supabase.table("matches").update({
            "status": "UNMATCHED",
            "unmatched_by": str(user_id),
            "unmatched_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", str(match_id)).execute()

        return UnmatchResponse(
            success=True,
            message="Successfully unmatched",
        )

    async def get_stats(self, user_id: UUID) -> dict:
        """
        Get match statistics for UI badges.
        Uses Redis caching to reduce database load.
        
        Returns:
        - active_count: Number of active matches
        - likes_you_count: Number of users who liked you (waiting for your swipe)
        - unread_messages_count: Total unread messages across all matches
        """
        from app.api.core.redis_client import (
            get_cached_match_stats,
            cache_match_stats,
        )
        from app.api.core.logging import get_logger
        
        logger = get_logger(__name__)
        user_id_str = str(user_id)
        
        # Try to get from cache first
        try:
            cached = await get_cached_match_stats(user_id_str)
            if cached is not None:
                logger.debug(f"Match stats cache hit for user {user_id_str}")
                return cached
        except Exception as e:
            logger.warning(f"Redis cache read failed, falling back to DB: {e}")
        
        # Cache miss - query database
        logger.debug(f"Match stats cache miss for user {user_id_str}")
        
        # Count active matches
        matches_result = self.supabase.table("matches").select(
            "id", count="exact"
        ).or_(
            f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
        ).ilike("status", "active").execute()
        
        active_count = matches_result.count or 0

        # Use service role to bypass RLS - users can't see swipes where they are liked_id
        admin_client = create_client(settings.supabase_url, settings.supabase_service_role_key)

        # Count users who liked you but you haven't swiped on
        # These are swipes where you are the liked_id, but you haven't liked them back
        
        # Get all users who swiped right on you
        liked_you = admin_client.table("swipes").select("liker_id").eq(
            "liked_id", str(user_id)
        ).in_("direction", ["RIGHT", "SUPER_LIKE"]).execute()
        
        liker_ids = [s["liker_id"] for s in (liked_you.data or [])]
        
        # Get users you've already swiped on
        your_swipes = admin_client.table("swipes").select("liked_id").eq(
            "liker_id", str(user_id)
        ).execute()
        
        swiped_ids = set(s["liked_id"] for s in (your_swipes.data or []))
        
        # Pending likes = users who liked you minus users you've already swiped
        pending_likes = [lid for lid in liker_ids if lid not in swiped_ids]
        likes_you_count = len(pending_likes)

        # Count unread messages using read cursors (same approach as chat service)
        # A message is "unread" if it was sent after the user's last read cursor
        match_ids = [m["id"] for m in (matches_result.data or [])]
        unread_messages_count = 0
        if match_ids:
            for match_id in match_ids:
                # Get user's read cursor for this match
                cursor = self.supabase.table("message_read_cursors").select(
                    "last_read_at"
                ).eq("match_id", match_id).eq(
                    "user_id", str(user_id)
                ).maybe_single().execute()
                
                # Count messages from others after the cursor
                unread_query = self.supabase.table("messages").select(
                    "id", count="exact"
                ).eq("match_id", match_id).neq("sender_id", str(user_id))
                
                if cursor and cursor.data and cursor.data.get("last_read_at"):
                    unread_query = unread_query.gt("created_at", cursor.data["last_read_at"])
                
                unread_result = unread_query.execute()
                unread_messages_count += unread_result.count or 0

        stats = {
            "active_count": active_count,
            "likes_you_count": likes_you_count,
            "unread_messages_count": unread_messages_count,
        }
        
        # Cache the result
        try:
            await cache_match_stats(user_id_str, stats)
            logger.debug(f"Match stats cached for user {user_id_str}")
        except Exception as e:
            logger.warning(f"Failed to cache match stats: {e}")
        
        return stats

    async def get_likes_you(self, user_id: UUID) -> List[dict]:
        """
        Get full profiles of users who liked the current user.
        
        Returns:
            List of profile dicts with photos, bio, age, etc.
        """
        # Use service role client to bypass RLS - users can't see swipes where they are liked_id
        admin_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        
        # Get all users who swiped right on you
        liked_you = admin_client.table("swipes").select(
            "liker_id, direction, comment, created_at"
        ).eq(
            "liked_id", str(user_id)
        ).in_("direction", ["RIGHT", "SUPER_LIKE"]).order(
            "created_at", desc=True
        ).execute()
        
        liker_ids = [s["liker_id"] for s in (liked_you.data or [])]
        
        # Get users you've already swiped on (to filter them out)
        your_swipes = admin_client.table("swipes").select("liked_id").eq(
            "liker_id", str(user_id)
        ).execute()
        
        swiped_ids = set(s["liked_id"] for s in (your_swipes.data or []))
        
        # Build profiles for pending likers
        profiles = []
        for swipe in (liked_you.data or []):
            liker_id = swipe["liker_id"]
            if liker_id in swiped_ids:
                continue  # Skip users you've already swiped on
                
            profile = await self._build_liker_profile(
                liker_id=liker_id,
                direction=swipe["direction"],
                comment=swipe.get("comment"),
                liked_at=swipe["created_at"],
            )
            if profile:
                profiles.append(profile)
        
        return profiles

    async def _build_liker_profile(
        self,
        liker_id: str,
        direction: str,
        comment: Optional[str],
        liked_at: str,
    ) -> Optional[dict]:
        """
        Build a profile dict for someone who liked you.
        """
        # Get profile
        profile = self.supabase.table("profiles").select("*").eq(
            "id", liker_id
        ).single().execute()
        
        if not profile.data:
            return None
        
        # Get photos
        photos = self.supabase.table("photos").select("*").eq(
            "user_id", liker_id
        ).order("order_index").execute()
        
        data = profile.data
        
        return {
            "id": data["id"],
            "display_name": data.get("display_name"),
            "age": data.get("age", 25),
            "gender": data.get("gender"),
            "bio": data.get("bio"),
            "prompts": data.get("prompts", []) or [],
            "photos": [{
                "id": p["id"],
                "url": self.supabase.storage.from_("photos").get_public_url(p["storage_path"]),
                "position": p["order_index"],
            } for p in (photos.data or [])],
            "passions": data.get("passions", []) or [],
            "is_verified": data.get("is_verified", False),
            "is_super_like": direction == "SUPER_LIKE",
            "their_comment": comment,
            "liked_at": liked_at,
        }

    # ===========================================
    # PRIVATE HELPERS
    # ===========================================

    async def _build_match_list_item(
        self,
        match_data: dict,
        user_id: UUID,
    ) -> MatchListItem:
        """Build match list item from raw data."""

        # Determine which user is the match
        matched_user_id = (
            match_data["user2_id"]
            if match_data["user1_id"] == str(user_id)
            else match_data["user1_id"]
        )

        matched_user = await self._get_matched_user_info(matched_user_id)

        # Get last message
        last_message = await self._get_last_message(match_data["id"], user_id)

        # Calculate expiration
        hours_until_expiry = None
        is_expiring_soon = False

        if match_data.get("expires_at") and match_data["status"].upper() == "ACTIVE":
            expires_at = datetime.fromisoformat(
                match_data["expires_at"].replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            if expires_at > now:
                hours_until_expiry = (expires_at - now).total_seconds() / 3600
                is_expiring_soon = hours_until_expiry <= EXPIRING_SOON_HOURS

        return MatchListItem(
            id=UUID(match_data["id"]),
            matched_user=matched_user,
            matched_at=datetime.fromisoformat(
                match_data["matched_at"].replace("Z", "+00:00")
            ),
            status=match_data["status"],
            last_message_preview=last_message.get("preview") if last_message else None,
            last_message_at=last_message.get("sent_at") if last_message else None,
            unread_count=last_message.get("unread_count", 0) if last_message else 0,
            has_started_chatting=match_data.get("first_message_at") is not None,
            hours_until_expiry=round(hours_until_expiry, 1) if hours_until_expiry else None,
            is_expiring_soon=is_expiring_soon,
        )

    async def _build_match_detail(
        self,
        match_data: dict,
        user_id: UUID,
    ) -> MatchDetail:
        """Build detailed match info from raw data."""

        # Determine which user is the match
        matched_user_id = (
            match_data["user2_id"]
            if match_data["user1_id"] == str(user_id)
            else match_data["user1_id"]
        )

        matched_user = await self._get_matched_user_info(matched_user_id)

        # Get opening comments from swipes
        our_swipe = self.supabase.table("swipes").select("comment").eq(
            "liker_id", str(user_id)
        ).eq("liked_id", matched_user_id).maybe_single().execute()

        their_swipe = self.supabase.table("swipes").select("comment").eq(
            "liker_id", matched_user_id
        ).eq("liked_id", str(user_id)).maybe_single().execute()

        # Get match reasons from discovery queue (if still available)
        queue_entry = self.supabase.table("discovery_queue").select(
            "match_reasons"
        ).eq("user_id", str(user_id)).eq(
            "candidate_id", matched_user_id
        ).maybe_single().execute()

        # Get last message
        last_message = await self._get_last_message(match_data["id"], user_id)

        # Calculate expiration
        hours_until_expiry = None
        is_expiring_soon = False
        expires_at = None

        if match_data.get("expires_at"):
            expires_at = datetime.fromisoformat(
                match_data["expires_at"].replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            if expires_at > now:
                hours_until_expiry = (expires_at - now).total_seconds() / 3600
                is_expiring_soon = hours_until_expiry <= EXPIRING_SOON_HOURS

        first_message_at = None
        if match_data.get("first_message_at"):
            first_message_at = datetime.fromisoformat(
                match_data["first_message_at"].replace("Z", "+00:00")
            )

        their_opening_comment = None
        if their_swipe and hasattr(their_swipe, 'data') and their_swipe.data:
            their_opening_comment = their_swipe.data.get("comment")

        return MatchDetail(
            id=UUID(match_data["id"]),
            matched_user=matched_user,
            matched_at=datetime.fromisoformat(
                match_data["matched_at"].replace("Z", "+00:00")
            ),
            expires_at=expires_at,
            status=match_data["status"],
            your_opening_comment=our_swipe.data.get("comment") if our_swipe.data else None,
            their_opening_comment=their_opening_comment,
            match_reasons=queue_entry.data.get("match_reasons", []) if queue_entry and hasattr(queue_entry, 'data') and queue_entry.data else [],
            first_message_at=first_message_at,
            last_message_at=last_message.get("sent_at") if last_message else None,
            last_message_preview=last_message.get("preview") if last_message else None,
            unread_count=last_message.get("unread_count", 0) if last_message else 0,
            hours_until_expiry=round(hours_until_expiry, 1) if hours_until_expiry else None,
            is_expiring_soon=is_expiring_soon,
        )

    async def _get_matched_user_info(self, user_id: str) -> MatchedUserInfo:
        """Get matched user basic info."""

        profile = self.supabase.table("profiles").select(
            "id, display_name"
        ).eq("id", user_id).single().execute()

        photo = self.supabase.table("photos").select("storage_path").eq(
            "user_id", user_id
        ).eq("is_primary", True).maybe_single().execute()

        # Generate public URL for photo
        photo_url = None
        if photo.data and photo.data.get("storage_path"):
            photo_url = self.supabase.storage.from_("photos").get_public_url(
                photo.data["storage_path"]
            )

        # Get response rate for badge
        scores = self.supabase.table("user_scores").select(
            "response_rate"
        ).eq("user_id", user_id).maybe_single().execute()

        response_rate = 0.5
        if scores and hasattr(scores, 'data') and scores.data:
            response_rate = scores.data.get("response_rate", 0.5)

        return MatchedUserInfo(
            id=UUID(profile.data["id"]) if profile.data else UUID(user_id),
            display_name=profile.data.get("display_name") if profile.data else None,
            age=profile.data.get("age") if profile.data else None,
            primary_photo_url=photo_url,
            response_badge=get_response_badge(response_rate),
        )

    async def _get_last_message(
        self,
        match_id: str,
        user_id: UUID,
    ) -> Optional[dict]:
        """Get last message in match conversation."""

        result = self.supabase.table("messages").select("*").eq(
            "match_id", match_id
        ).order("created_at", desc=True).limit(1).maybe_single().execute()

        if not result or not result.data:
            return None

        msg = result.data

        # Count unread using read cursor (not read_at column)
        cursor = self.supabase.table("message_read_cursors").select(
            "last_read_at"
        ).eq("match_id", match_id).eq(
            "user_id", str(user_id)
        ).maybe_single().execute()
        
        unread_query = self.supabase.table("messages").select(
            "id", count="exact"
        ).eq("match_id", match_id).neq("sender_id", str(user_id))
        
        if cursor and cursor.data and cursor.data.get("last_read_at"):
            unread_query = unread_query.gt("created_at", cursor.data["last_read_at"])
        
        unread = unread_query.execute()

        return {
            "preview": msg.get("content", "")[:50],
            "sent_at": datetime.fromisoformat(
                msg["created_at"].replace("Z", "+00:00")
            ) if msg.get("created_at") else None,
            "unread_count": unread.count or 0,
        }
