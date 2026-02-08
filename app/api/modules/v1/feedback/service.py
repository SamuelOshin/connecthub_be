"""
Feedback service for 'We Connected' system.
Updates user scores based on real-world outcomes.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from supabase import Client

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ForbiddenError,
    ValidationError,
)
from app.api.modules.v1.feedback.schemas import (
    ConnectionFeedbackCreate,
    FeedbackResponse,
    FeedbackSummary,
    PendingFeedbackResponse,
    PendingFeedbackItem,
    FeedbackMatchInfo,
)


# Minimum days since match before requesting feedback
FEEDBACK_DELAY_DAYS = 3


class FeedbackService:
    """Service for connection feedback operations."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def get_pending_feedback(
        self,
        user_id: UUID,
    ) -> PendingFeedbackResponse:
        """
        Get matches that need feedback.
        Only returns matches older than FEEDBACK_DELAY_DAYS without existing feedback.
        """

        cutoff_date = (
            datetime.now(timezone.utc) - timedelta(days=FEEDBACK_DELAY_DAYS)
        ).isoformat()

        # Get matches older than cutoff without feedback from this user
        matches = self.supabase.table("matches").select("*").or_(
            f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
        ).eq("status", "ACTIVE").lt("matched_at", cutoff_date).execute()

        pending = []
        for match_data in matches.data or []:
            # Check if user already submitted feedback
            existing = self.supabase.table("connection_feedback").select("id").eq(
                "match_id", match_data["id"]
            ).eq("user_id", str(user_id)).maybe_single().execute()

            if existing.data:
                continue  # Already submitted

            # Get matched user info
            matched_user_id = (
                match_data["user2_id"]
                if match_data["user1_id"] == str(user_id)
                else match_data["user1_id"]
            )

            profile = self.supabase.table("profiles").select(
                "display_name"
            ).eq("id", matched_user_id).single().execute()

            photo = self.supabase.table("photos").select("photo_url").eq(
                "profile_id", matched_user_id
            ).eq("is_primary", True).maybe_single().execute()

            matched_at = datetime.fromisoformat(
                match_data["matched_at"].replace("Z", "+00:00")
            )
            days_since = (datetime.now(timezone.utc) - matched_at).days

            name = profile.data.get("display_name", "them") if profile.data else "them"

            pending.append(PendingFeedbackItem(
                match=FeedbackMatchInfo(
                    id=UUID(match_data["id"]),
                    matched_user_name=name,
                    matched_user_photo_url=photo.data.get("photo_url") if photo.data else None,
                    matched_at=matched_at,
                    days_since_match=days_since,
                ),
                prompt_text=f"How's it going with {name}?",
                reminder_count=0,  # TODO: Track reminder count
            ))

        return PendingFeedbackResponse(
            pending=pending,
            total_count=len(pending),
        )

    async def submit_feedback(
        self,
        user_id: UUID,
        feedback: ConnectionFeedbackCreate,
    ) -> FeedbackResponse:
        """
        Submit connection feedback for a match.
        This updates the other user's behavioral scores.
        """

        # Verify match exists and user is part of it
        match = self.supabase.table("matches").select("*").eq(
            "id", str(feedback.match_id)
        ).single().execute()

        if not match.data:
            raise NotFoundError(message="Match not found", code="MATCH_NOT_FOUND")

        if str(user_id) not in [match.data["user1_id"], match.data["user2_id"]]:
            raise ForbiddenError(
                message="You are not part of this match",
                code="NOT_YOUR_MATCH",
            )

        # Check if already submitted
        existing = self.supabase.table("connection_feedback").select("id").eq(
            "match_id", str(feedback.match_id)
        ).eq("user_id", str(user_id)).maybe_single().execute()

        if existing.data:
            raise ValidationError(
                message="You've already submitted feedback for this match",
                code="FEEDBACK_ALREADY_SUBMITTED",
            )

        # Create feedback record
        feedback_data = {
            "match_id": str(feedback.match_id),
            "user_id": str(user_id),
            "did_you_meet": feedback.did_you_meet,
            "meeting_type": feedback.meeting_type,
            "would_meet_again": feedback.would_meet_again,
            "connection_quality": feedback.connection_quality,
            "positive_factors": feedback.positive_factors or [],
            "negative_factors": feedback.negative_factors or [],
            "notes": feedback.notes,
        }

        result = self.supabase.table("connection_feedback").insert(
            feedback_data
        ).execute()

        feedback_id = result.data[0]["id"]

        # Update match to record feedback
        update_field = (
            "user1_feedback_id"
            if match.data["user1_id"] == str(user_id)
            else "user2_feedback_id"
        )
        self.supabase.table("matches").update({
            update_field: feedback_id,
            "feedback_requested_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", str(feedback.match_id)).execute()

        # Update other user's scores based on feedback
        other_user_id = (
            match.data["user2_id"]
            if match.data["user1_id"] == str(user_id)
            else match.data["user1_id"]
        )

        await self._update_user_scores_from_feedback(
            other_user_id, feedback
        )

        # Generate thank you message
        if feedback.did_you_meet and feedback.connection_quality and feedback.connection_quality >= 4:
            thank_you = "Thanks for sharing! We're glad it went well. Your feedback helps us make better matches! 🎉"
        elif feedback.did_you_meet:
            thank_you = "Thanks for the feedback! This helps us improve your future matches."
        else:
            thank_you = "Thanks for letting us know. We'll use this to improve your matches."

        return FeedbackResponse(
            id=UUID(feedback_id),
            match_id=feedback.match_id,
            submitted_at=datetime.now(timezone.utc),
            thank_you_message=thank_you,
        )

    async def get_feedback(
        self,
        user_id: UUID,
        match_id: UUID,
    ) -> Optional[FeedbackSummary]:
        """
        Get feedback submitted by this user for a match.
        """

        result = self.supabase.table("connection_feedback").select("*").eq(
            "match_id", str(match_id)
        ).eq("user_id", str(user_id)).maybe_single().execute()

        if not result.data:
            return None

        data = result.data
        return FeedbackSummary(
            id=UUID(data["id"]),
            match_id=UUID(data["match_id"]),
            did_you_meet=data["did_you_meet"],
            meeting_type=data["meeting_type"],
            would_meet_again=data.get("would_meet_again"),
            connection_quality=data.get("connection_quality"),
            positive_factors=data.get("positive_factors", []),
            negative_factors=data.get("negative_factors", []),
            submitted_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
        )

    # ===========================================
    # PRIVATE HELPERS
    # ===========================================

    async def _update_user_scores_from_feedback(
        self,
        user_id: str,
        feedback: ConnectionFeedbackCreate,
    ) -> None:
        """
        Update user's behavioral scores based on feedback.
        This is the 'secret sauce' that trains our algorithm on real outcomes.
        """

        # Get current scores
        scores = self.supabase.table("user_scores").select("*").eq(
            "user_id", user_id
        ).maybe_single().execute()

        if not scores.data:
            # Create initial scores
            self.supabase.table("user_scores").insert({
                "user_id": user_id,
                "response_rate": 0.5,
                "positive_feedback_ratio": 0.5,
                "dates_from_matches_ratio": 0.0,
            }).execute()
            scores = self.supabase.table("user_scores").select("*").eq(
                "user_id", user_id
            ).single().execute()

        current = scores.data

        # Count total feedbacks for this user
        total_feedbacks = self.supabase.table("connection_feedback").select(
            "id", count="exact"
        ).eq("user_id", user_id).execute()
        feedback_count = (total_feedbacks.count or 0) + 1

        # 1. Update dates_from_matches_ratio
        current_ratio = current.get("dates_from_matches_ratio", 0.0)
        new_outcome = 1.0 if feedback.did_you_meet else 0.0
        new_dates_ratio = self._recalculate_ratio(
            current_ratio, new_outcome, feedback_count
        )

        # 2. Update positive_feedback_ratio
        current_positive = current.get("positive_feedback_ratio", 0.5)
        if feedback.connection_quality:
            if feedback.connection_quality >= 4:
                outcome = 1.0
            elif feedback.connection_quality <= 2:
                outcome = 0.0
            else:
                outcome = 0.5
        else:
            outcome = 0.5

        new_positive_ratio = self._recalculate_ratio(
            current_positive, outcome, feedback_count
        )

        # 3. Track ghosting
        ghost_count = current.get("ghost_count", 0)
        if feedback.negative_factors and "ghosted" in feedback.negative_factors:
            ghost_count += 1

        # Update scores
        self.supabase.table("user_scores").update({
            "dates_from_matches_ratio": new_dates_ratio,
            "positive_feedback_ratio": new_positive_ratio,
            "ghost_count": ghost_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("user_id", user_id).execute()

    def _recalculate_ratio(
        self,
        current: float,
        new_outcome: float,
        total_count: int,
    ) -> float:
        """
        Recalculate a rolling ratio with a new outcome.
        Uses weighted average with increasing sample size.
        """

        if total_count <= 1:
            return new_outcome

        # Weighted average: give more weight to recent feedback
        weight = min(0.3, 1.0 / total_count)
        return (1 - weight) * current + weight * new_outcome
