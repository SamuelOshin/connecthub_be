"""
Discovery service for matching engine.
Handles discovery queue generation, swipe processing, and match detection.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from supabase import Client

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ValidationError,
    LimitExceededError,
)
from app.api.modules.v1.discovery.scoring import (
    calculate_match_score,
    get_response_badge,
    UserProfile,
    UserPreferences,
    UserScores,
    MatchScore,
)
from app.api.modules.v1.discovery.schemas import (
    DiscoveryProfile,
    DiscoveryResponse,
    SwipeCreate,
    SwipeResponse,
    MatchInfo,
    MatchScoreBreakdown,
    DiscoveryStats,
    PreferencesResponse,
)


# ===========================================
# CONFIGURATION
# ===========================================


def _calculate_age_from_birthdate(birthdate: Optional[str]) -> int:
    """Calculate age from birthdate string (YYYY-MM-DD format). Returns 25 as default."""
    if not birthdate:
        return 25
    try:
        birth = datetime.strptime(birthdate[:10], "%Y-%m-%d")
        today = datetime.now()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return max(18, min(99, age))  # Clamp to 18-99
    except (ValueError, TypeError):
        return 25

DAILY_LIKE_LIMIT_FREE = 10
DAILY_LIKE_LIMIT_PREMIUM = 50
DAILY_SUPER_LIKE_LIMIT = 1
MATCH_EXPIRY_HOURS = 72
MIN_COMMENT_LENGTH = 10


# ===========================================
# DISCOVERY SERVICE
# ===========================================


class DiscoveryService:
    """Service for discovery and matching operations."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def get_discovery_profiles(
        self,
        user_id: UUID,
        limit: int = 10,
        cursor: Optional[str] = None,
    ) -> DiscoveryResponse:
        """
        Get discovery profiles for a user.
        Uses pre-computed queue or generates on-the-fly.
        """

        # Get user's profile and preferences
        viewer_profile = await self._get_user_profile(user_id)
        viewer_prefs = await self._get_user_preferences(user_id)
        viewer_scores = await self._get_user_scores(user_id)

        # Get or refresh discovery queue
        queue = await self._get_or_refresh_queue(user_id)

        # Apply cursor pagination
        if cursor:
            queue = [item for item in queue if item["position"] > int(cursor)]

        # Limit results
        queue = queue[:limit]

        # Build response profiles
        profiles = []
        for item in queue:
            candidate = await self._get_candidate_profile(item["candidate_id"])
            if candidate:
                profiles.append(candidate)

        # Get remaining likes
        likes_today = await self._count_likes_today(user_id)
        daily_limit = await self._get_daily_limit(user_id)

        return DiscoveryResponse(
            profiles=profiles,
            next_cursor=str(queue[-1]["position"]) if queue else None,
            remaining_likes_today=max(0, daily_limit - likes_today),
            daily_like_limit=daily_limit,
        )

    async def create_swipe(
        self,
        user_id: UUID,
        swipe: SwipeCreate,
    ) -> SwipeResponse:
        """
        Record a swipe action.
        
        For RIGHT/SUPER_LIKE:
        - Comment is REQUIRED (min 10 characters)
        - Must specify which photo/prompt the comment is about
        
        Returns match info if mutual like detected.
        """

        # Validate comment requirement for likes
        # If it's a match (they liked us first), we don't strictly require a comment
        if swipe.direction in ["RIGHT", "SUPER_LIKE"]:
            if not swipe.comment or len(swipe.comment) < MIN_COMMENT_LENGTH:
                # Check if they already liked us
                incoming_like = self.supabase.table("swipes").select("id").eq(
                    "liker_id", str(swipe.profile_id)
                ).eq("liked_id", str(user_id)).in_(
                    "direction", ["RIGHT", "SUPER_LIKE"]
                ).maybe_single().execute()

                # Fix: Handle case where execute() returns None (though unlikely, it's causing the crash)
                is_match = False
                if incoming_like and hasattr(incoming_like, 'data') and incoming_like.data:
                    is_match = True

                if not is_match:
                    raise ValidationError(
                        message=f"Please include a thoughtful comment (at least {MIN_COMMENT_LENGTH} characters)",
                        code="COMMENT_REQUIRED",
                    )

        # Check daily like limit
        likes_today = await self._count_likes_today(user_id)
        daily_limit = await self._get_daily_limit(user_id)

        if swipe.direction in ["RIGHT", "SUPER_LIKE"] and likes_today >= daily_limit:
            raise LimitExceededError(
                message="Daily like limit reached. Try again tomorrow!",
                code="DAILY_LIMIT_EXCEEDED",
            )

        # Check super like limit
        if swipe.direction == "SUPER_LIKE":
            super_likes_today = await self._count_super_likes_today(user_id)
            if super_likes_today >= DAILY_SUPER_LIKE_LIMIT:
                raise LimitExceededError(
                    message="Daily super like limit reached.",
                    code="SUPER_LIKE_LIMIT_EXCEEDED",
                )

        # Check if already swiped
        existing = self.supabase.table("swipes").select("id").eq(
            "liker_id", str(user_id)
        ).eq("liked_id", str(swipe.profile_id)).execute()

        if existing.data:
            raise ValidationError(
                message="You've already swiped on this profile",
                code="ALREADY_SWIPED",
            )

        # Create swipe record
        swipe_data = {
            "liker_id": str(user_id),
            "liked_id": str(swipe.profile_id),
            "direction": swipe.direction,
            "comment": swipe.comment,
            "comment_target": swipe.comment_target,
            "time_spent_viewing_ms": swipe.time_spent_viewing_ms,
            "profile_scroll_depth": swipe.profile_scroll_depth,
        }

        self.supabase.table("swipes").insert(swipe_data).execute()

        # Remove from discovery queue
        self.supabase.table("discovery_queue").delete().eq(
            "user_id", str(user_id)
        ).eq("candidate_id", str(swipe.profile_id)).execute()

        # Check for mutual like
        match = None
        if swipe.direction in ["RIGHT", "SUPER_LIKE"]:
            match = await self._check_and_create_match(user_id, swipe.profile_id)

        return SwipeResponse(
            success=True,
            match=match,
            remaining_likes_today=max(0, daily_limit - likes_today - 1),
        )

    async def _check_and_create_match(
        self,
        user1_id: UUID,
        user2_id: UUID,
    ) -> Optional[MatchInfo]:
        """
        Check if there's a mutual like and create match.
        """

        # Check if other user has liked us
        reverse_swipe = self.supabase.table("swipes").select("*").eq(
            "liker_id", str(user2_id)
        ).eq("liked_id", str(user1_id)).in_(
            "direction", ["RIGHT", "SUPER_LIKE"]
        ).execute()

        if not reverse_swipe.data:
            return None

        # Create match!
        # Use consistent ordering (smaller UUID first)
        ordered_ids = sorted([str(user1_id), str(user2_id)])

        match_data = {
            "user1_id": ordered_ids[0],
            "user2_id": ordered_ids[1],
            "matched_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=MATCH_EXPIRY_HOURS)).isoformat(),
            "status": "ACTIVE",
        }

        result = self.supabase.table("matches").insert(match_data).execute()
        match_id = result.data[0]["id"]

        # Get matched user info
        matched_user = self.supabase.table("profiles").select(
            "id, display_name"
        ).eq("id", str(user2_id)).single().execute()

        # Get primary photo (using correct column names)
        photo = self.supabase.table("photos").select("storage_path").eq(
            "user_id", str(user2_id)
        ).eq("is_primary", True).maybe_single().execute()

        # Get both users' comments
        our_swipe = self.supabase.table("swipes").select("comment").eq(
            "liker_id", str(user1_id)
        ).eq("liked_id", str(user2_id)).single().execute()

        their_comment = reverse_swipe.data[0].get("comment")

        # Convert comments to messages to start conversation
        messages_to_insert = []
        now = datetime.now(timezone.utc)
        
        # 1. Their comment (from first swipe)
        if their_comment:
            messages_to_insert.append({
                "match_id": match_id,
                "sender_id": str(user2_id),
                "content": their_comment,
                "message_type": "text",
                # Set slightly in past to ensure order
                "created_at": (now - timedelta(milliseconds=100)).isoformat(),
            })

        # 2. Your comment (from second swipe/match)
        our_comment = our_swipe.data.get("comment") if our_swipe.data else None
        if our_comment:
            messages_to_insert.append({
                "match_id": match_id,
                "sender_id": str(user1_id),
                "content": our_comment,
                "message_type": "text",
                "created_at": now.isoformat(),
            })

        if messages_to_insert:
            self.supabase.table("messages").insert(messages_to_insert).execute()
            
            # Update match status to reflect active conversation
            self.supabase.table("matches").update({
                "first_message_at": now.isoformat(),
            }).eq("id", match_id).execute()

        return MatchInfo(
            id=match_id,
            matched_user_id=user2_id,
            matched_user_name=matched_user.data.get("display_name") if matched_user.data else None,
            matched_user_photo_url=photo.data.get("storage_path") if photo.data else None,
            matched_at=datetime.fromisoformat(match_data["matched_at"]),
            expires_at=datetime.fromisoformat(match_data["expires_at"]),
            your_comment=our_swipe.data.get("comment") if our_swipe.data else None,
            their_comment=their_comment,
        )

    async def get_discovery_stats(self, user_id: UUID) -> DiscoveryStats:
        """Get user's discovery statistics."""

        likes_today = await self._count_likes_today(user_id)
        daily_limit = await self._get_daily_limit(user_id)
        super_likes_today = await self._count_super_likes_today(user_id)

        # Get user scores for response rate
        user_scores = await self._get_user_scores(user_id)

        # Count profiles viewed today (all swipes)
        today = datetime.now(timezone.utc).date().isoformat()
        swipes_today = self.supabase.table("swipes").select(
            "id", count="exact"
        ).eq("liker_id", str(user_id)).gte(
            "created_at", today
        ).execute()

        # Calculate match rate
        total_likes = self.supabase.table("swipes").select(
            "id", count="exact"
        ).eq("liker_id", str(user_id)).in_(
            "direction", ["RIGHT", "SUPER_LIKE"]
        ).execute()

        total_matches = self.supabase.table("matches").select(
            "id", count="exact"
        ).or_(
            f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
        ).execute()

        likes_count = total_likes.count or 0
        matches_count = total_matches.count or 0
        match_rate = (matches_count / likes_count * 100) if likes_count > 0 else 0.0

        return DiscoveryStats(
            likes_sent_today=likes_today,
            likes_remaining_today=max(0, daily_limit - likes_today),
            daily_like_limit=daily_limit,
            super_likes_remaining=max(0, DAILY_SUPER_LIKE_LIMIT - super_likes_today),
            profiles_viewed_today=swipes_today.count or 0,
            match_rate=round(match_rate, 1),
            response_rate=round(user_scores.response_rate * 100, 1),
        )

    async def get_user_preferences(self, user_id: UUID) -> PreferencesResponse:
        """Get user's matching preferences."""

        prefs = await self._get_user_preferences(user_id)

        return PreferencesResponse(
            min_age=prefs.min_age,
            max_age=prefs.max_age,
            max_distance_km=prefs.max_distance_km,
            gender_preferences=prefs.gender_preferences,
            preferred_height_min_cm=None,  # Not in basic UserPreferences
            preferred_height_max_cm=None,
            preferred_education=[],
            preferred_religion=[],
            preferred_smoking=None,
            preferred_drinking=None,
            preferred_children=None,
            show_verified_only=False,
        )

    async def update_user_preferences(
        self,
        user_id: UUID,
        updates: dict,
    ) -> PreferencesResponse:
        """Update user's matching preferences."""

        # Check if preferences exist
        existing = self.supabase.table("user_preferences").select("id").eq(
            "user_id", str(user_id)
        ).maybe_single().execute()

        if existing.data:
            # Update
            self.supabase.table("user_preferences").update({
                **updates,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("user_id", str(user_id)).execute()
        else:
            # Create
            self.supabase.table("user_preferences").insert({
                "user_id": str(user_id),
                **updates,
            }).execute()

        return await self.get_user_preferences(user_id)

    # ===========================================
    # PRIVATE HELPERS
    # ===========================================

    async def _get_user_profile(self, user_id: UUID) -> UserProfile:
        """Get user profile for scoring."""

        result = self.supabase.table("profiles").select("*").eq(
            "id", str(user_id)
        ).maybe_single().execute()

        if not result.data:
            raise NotFoundError(message="Profile not found", code="PROFILE_NOT_FOUND")

        data = result.data
        return UserProfile(
            id=data["id"],
            age=_calculate_age_from_birthdate(data.get("birthdate")),
            gender=data.get("gender"),
            location_lat=0,  # PostGIS location not parsed yet
            location_lng=0,  # PostGIS location not parsed yet
            bio=data.get("bio"),
            prompts=data.get("prompts", []) or [],
            is_verified=data.get("is_verified", False),
        )

    async def _get_user_preferences(self, user_id: UUID) -> UserPreferences:
        """Get user preferences or defaults."""

        result = self.supabase.table("user_preferences").select("*").eq(
            "user_id", str(user_id)
        ).maybe_single().execute()

        if result and result.data:
            data = result.data
            return UserPreferences(
                min_age=data.get("min_age", 18),
                max_age=data.get("max_age", 99),
                max_distance_km=data.get("max_distance_km", 50),
                gender_preferences=data.get("gender_preferences", []) or [],
            )

        return UserPreferences()

    async def _get_user_scores(self, user_id: UUID) -> UserScores:
        """Get user behavioral scores or defaults."""

        result = self.supabase.table("user_scores").select("*").eq(
            "user_id", str(user_id)
        ).maybe_single().execute()

        if result and result.data:
            data = result.data
            last_active = None
            if data.get("last_active"):
                last_active = datetime.fromisoformat(data["last_active"].replace("Z", "+00:00"))

            return UserScores(
                response_rate=data.get("response_rate", 0.5),
                avg_response_time_hours=data.get("avg_response_time_hours"),
                message_quality_score=data.get("message_quality_score", 0.5),
                comment_quality_avg=data.get("comment_quality_avg", 0.5),
                profile_completion=data.get("profile_completion", 0.0),
                photo_quality_avg=data.get("photo_quality_avg", 0.5),
                dates_from_matches_ratio=data.get("dates_from_matches_ratio", 0.0),
                positive_feedback_ratio=data.get("positive_feedback_ratio", 0.5),
                last_active=last_active,
                ghost_count=data.get("ghost_count", 0),
            )

        return UserScores()

    async def _get_or_refresh_queue(self, user_id: UUID) -> list[dict]:
        """Get discovery queue or generate if stale/empty."""

        # Check for existing queue
        result = self.supabase.table("discovery_queue").select("*").eq(
            "user_id", str(user_id)
        ).gt("expires_at", datetime.now(timezone.utc).isoformat()).order(
            "position"
        ).limit(50).execute()

        if result.data and len(result.data) >= 10:
            return result.data

        # Generate new queue
        await self._generate_discovery_queue(user_id)

        # Fetch fresh queue
        result = self.supabase.table("discovery_queue").select("*").eq(
            "user_id", str(user_id)
        ).order("position").limit(50).execute()

        return result.data or []

    async def _generate_discovery_queue(self, user_id: UUID) -> None:
        """Generate discovery queue using PostGIS and scoring."""
        
        # Use service role client to bypass RLS for queue management
        from supabase import create_client
        admin_client = create_client(settings.supabase_url, settings.supabase_service_role_key)

        viewer_profile = await self._get_user_profile(user_id)
        viewer_prefs = await self._get_user_preferences(user_id)
        viewer_scores = await self._get_user_scores(user_id)

        # Clear old queue - use admin client
        admin_client.table("discovery_queue").delete().eq(
            "user_id", str(user_id)
        ).execute()

        # Get already swiped profiles
        swiped = self.supabase.table("swipes").select("liked_id").eq(
            "liker_id", str(user_id)
        ).execute()
        swiped_ids = [s["liked_id"] for s in swiped.data] if swiped.data else []

        # Find candidates using SQL with PostGIS
        # Query all profiles except current user
        candidates_query = self.supabase.table("profiles").select("*").neq(
            "id", str(user_id)
        )

        # Apply basic filters
        # Note: Age filtering removed - profiles table uses 'birthdate' not 'age'
        # Age filtering should be done in Python after fetching or via SQL function
        if viewer_prefs.gender_preferences:
            candidates_query = candidates_query.in_("gender", viewer_prefs.gender_preferences)

        candidates = candidates_query.limit(200).execute()

        if not candidates.data:
            return

        # Score and rank candidates
        scored = []
        for candidate_data in candidates.data:
            if candidate_data["id"] in swiped_ids:
                continue

            candidate_profile = UserProfile(
                id=candidate_data["id"],
                age=_calculate_age_from_birthdate(candidate_data.get("birthdate")),
                gender=candidate_data.get("gender"),
                location_lat=0,  # PostGIS location not parsed yet
                location_lng=0,  # PostGIS location not parsed yet
                bio=candidate_data.get("bio"),
                prompts=candidate_data.get("prompts", []) or [],
                is_verified=candidate_data.get("is_verified", False),
            )

            candidate_prefs = await self._get_user_preferences(UUID(candidate_data["id"]))
            candidate_scores = await self._get_user_scores(UUID(candidate_data["id"]))

            # Calculate distance (simple approximation)
            distance_km = self._calculate_distance(
                viewer_profile.location_lat,
                viewer_profile.location_lng,
                candidate_profile.location_lat,
                candidate_profile.location_lng,
            )

            if distance_km > viewer_prefs.max_distance_km:
                continue

            # Calculate match score
            score = calculate_match_score(
                viewer_profile=viewer_profile,
                viewer_prefs=viewer_prefs,
                viewer_scores=viewer_scores,
                candidate_profile=candidate_profile,
                candidate_prefs=candidate_prefs,
                candidate_scores=candidate_scores,
                distance_km=distance_km,
            )

            scored.append({
                "candidate_id": candidate_data["id"],
                "score": score,
                "distance_km": distance_km,
            })

        # Sort by score
        scored.sort(key=lambda x: x["score"].final_score, reverse=True)

        # Insert into queue
        queue_entries = []
        for i, item in enumerate(scored[:50]):
            score = item["score"]
            queue_entries.append({
                "user_id": str(user_id),
                "candidate_id": item["candidate_id"],
                "final_score": score.final_score,
                "preference_overlap_score": score.breakdown.get("preference_overlap"),
                "behavioral_compatibility_score": score.breakdown.get("behavioral_compatibility"),
                "effort_score": score.breakdown.get("effort_score"),
                "activity_freshness_score": score.breakdown.get("activity_freshness"),
                "feedback_history_score": score.breakdown.get("feedback_history"),
                "exploration_score": score.breakdown.get("exploration"),
                "match_reasons": score.reasons,
                "position": i,
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            })

        if queue_entries:
            # Use admin client to bypass RLS for insert
            admin_client.table("discovery_queue").insert(queue_entries).execute()

    async def _get_candidate_profile(self, candidate_id: str) -> Optional[DiscoveryProfile]:
        """Build discovery profile from queue entry."""

        # Get profile
        profile = self.supabase.table("profiles").select("*").eq(
            "id", candidate_id
        ).single().execute()

        if not profile.data:
            return None

        # Get photos (using correct column names)
        photos = self.supabase.table("photos").select("*").eq(
            "user_id", candidate_id
        ).order("order_index").execute()

        # Get queue entry for scores
        entry = self.supabase.table("discovery_queue").select("*").eq(
            "candidate_id", candidate_id
        ).maybe_single().execute()

        # Get user scores for response badge
        scores = await self._get_user_scores(UUID(candidate_id))

        data = profile.data
        entry_data = entry.data or {}

        return DiscoveryProfile(
            id=UUID(data["id"]),
            display_name=data.get("display_name"),
            age=data.get("age", 25),
            gender=data.get("gender"),
            bio=data.get("bio"),
            prompts=data.get("prompts", []) or [],
            photos=[{
                "id": p["id"],
                "url": self.supabase.storage.from_("photos").get_public_url(p["storage_path"]),
                "position": p["order_index"],
            } for p in (photos.data or [])],
            distance_km=0,  # Would be calculated from PostGIS
            is_verified=data.get("is_verified", False),
            match_score=entry_data.get("final_score", 0.5),
            match_reasons=entry_data.get("match_reasons", []),
            score_breakdown=MatchScoreBreakdown(
                preference_overlap=entry_data.get("preference_overlap_score", 0.5),
                behavioral_compatibility=entry_data.get("behavioral_compatibility_score", 0.5),
                effort_score=entry_data.get("effort_score", 0.5),
                activity_freshness=entry_data.get("activity_freshness_score", 0.5),
                feedback_history=entry_data.get("feedback_history_score", 0.5),
                exploration=entry_data.get("exploration_score", 0.5),
            ) if entry_data else None,
            response_badge=get_response_badge(scores.response_rate),
        )

    async def _count_likes_today(self, user_id: UUID) -> int:
        """Count likes sent today."""

        today = datetime.now(timezone.utc).date().isoformat()
        result = self.supabase.table("swipes").select(
            "id", count="exact"
        ).eq("liker_id", str(user_id)).in_(
            "direction", ["RIGHT", "SUPER_LIKE"]
        ).gte("created_at", today).execute()

        return result.count or 0

    async def _count_super_likes_today(self, user_id: UUID) -> int:
        """Count super likes sent today."""

        today = datetime.now(timezone.utc).date().isoformat()
        result = self.supabase.table("swipes").select(
            "id", count="exact"
        ).eq("liker_id", str(user_id)).eq(
            "direction", "SUPER_LIKE"
        ).gte("created_at", today).execute()

        return result.count or 0

    async def _get_daily_limit(self, user_id: UUID) -> int:
        """Get user's daily like limit based on subscription."""

        # TODO: Check user subscription status
        return DAILY_LIKE_LIMIT_FREE

    def _calculate_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float,
    ) -> float:
        """Calculate distance between two points in km (haversine formula)."""

        import math

        if lat1 == 0 and lng1 == 0:
            return 0
        if lat2 == 0 and lng2 == 0:
            return 0

        R = 6371  # Earth's radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c
