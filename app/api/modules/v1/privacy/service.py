"""
Privacy service layer - business logic for GDPR privacy operations.

Contains all business logic for privacy management including:
- User data export (GDPR Article 20)
- Account deletion requests (GDPR Article 17)
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import hashlib

from supabase import Client

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ConflictError,
    ProcessingError,
)


class PrivacyService:
    """
    Service for GDPR privacy operations.

    Handles data export and account deletion with 30-day grace period.

    Attributes:
        supabase: Authenticated Supabase client (respects RLS).
        user_id: Current authenticated user's UUID.
    """

    def __init__(self, supabase: Client, user_id: UUID):
        """
        Initialize privacy service.

        Args:
            supabase: Authenticated Supabase client (respects RLS).
            user_id: Current authenticated user's ID.
        """
        self.supabase = supabase
        self.user_id = user_id

    async def export_user_data(self) -> dict:
        """
        Export all user data for GDPR compliance.

        Returns:
            dict: Complete data package containing profile, photos, matches,
                  messages, swipes, preferences, and feedback.

        Raises:
            ProcessingError: If data export fails.
        """
        try:
            export_data = {
                "export_id": self._generate_export_id(),
                "user_id": str(self.user_id),
                "generated_at": datetime.utcnow().isoformat(),
                "profile": {},
                "photos": [],
                "matches": [],
                "messages": [],
                "swipes": [],
                "preferences": None,
                "feedback": [],
            }

            # Get profile
            profile_resp = self.supabase.table("profiles").select("*").eq(
                "id", str(self.user_id)
            ).single().execute()
            if profile_resp.data:
                export_data["profile"] = profile_resp.data

            # Get photos
            photos_resp = self.supabase.table("photos").select("*").eq(
                "user_id", str(self.user_id)
            ).execute()
            export_data["photos"] = photos_resp.data or []

            # Get matches
            matches_resp = self.supabase.table("matches").select("*").or_(
                f"user1_id.eq.{self.user_id},user2_id.eq.{self.user_id}"
            ).execute()
            export_data["matches"] = matches_resp.data or []

            # Get messages sent by user
            messages_resp = self.supabase.table("messages").select("*").eq(
                "sender_id", str(self.user_id)
            ).execute()
            export_data["messages"] = messages_resp.data or []

            # Get swipes
            swipes_resp = self.supabase.table("swipes").select("*").eq(
                "liker_id", str(self.user_id)
            ).execute()
            export_data["swipes"] = swipes_resp.data or []

            # Get preferences
            prefs_resp = self.supabase.table("user_preferences").select("*").eq(
                "user_id", str(self.user_id)
            ).single().execute()
            if prefs_resp.data:
                export_data["preferences"] = prefs_resp.data

            # Get feedback
            feedback_resp = self.supabase.table("connection_feedback").select("*").eq(
                "user_id", str(self.user_id)
            ).execute()
            export_data["feedback"] = feedback_resp.data or []

            return export_data
        except Exception as e:
            raise ProcessingError(f"Failed to export user data: {str(e)}")

    async def request_deletion(self, reason: Optional[str] = None) -> dict:
        """
        Request account deletion with 30-day grace period.

        Args:
            reason: Optional reason for leaving.

        Returns:
            dict: Deletion request details with scheduled date.

        Raises:
            ConflictError: If there's already a pending deletion request.
            ProcessingError: If request creation fails.
        """
        # Check for existing request
        existing = self.supabase.table("account_deletion_requests").select("id").eq(
            "user_id", str(self.user_id)
        ).eq("status", "PENDING").execute()

        if existing.data:
            raise ConflictError("You already have a pending deletion request.")

        # Create deletion request
        scheduled_at = datetime.utcnow() + timedelta(days=30)

        try:
            result = self.supabase.table("account_deletion_requests").insert({
                "user_id": str(self.user_id),
                "reason": reason,
                "status": "PENDING",
                "scheduled_deletion_at": scheduled_at.isoformat(),
            }).execute()

            if not result.data:
                raise ProcessingError("Failed to create deletion request.")

            return {
                "id": result.data[0]["id"],
                "status": "PENDING",
                "scheduled_deletion_at": scheduled_at.isoformat(),
                "message": f"Your account is scheduled for deletion on "
                           f"{scheduled_at.strftime('%B %d, %Y')}. "
                           f"You can cancel this request within 30 days.",
            }
        except ConflictError:
            raise
        except Exception as e:
            raise ProcessingError(f"Failed to create deletion request: {str(e)}")

    async def cancel_deletion(self) -> dict:
        """
        Cancel a pending account deletion request.

        Returns:
            dict: Confirmation of cancellation.

        Raises:
            NotFoundError: If no pending deletion request exists.
            ProcessingError: If cancellation fails.
        """
        try:
            result = self.supabase.table("account_deletion_requests").update({
                "status": "CANCELLED"
            }).eq("user_id", str(self.user_id)).eq("status", "PENDING").execute()

            if not result.data:
                raise NotFoundError("No pending deletion request found.")

            return {
                "success": True,
                "message": "Your account deletion request has been cancelled.",
            }
        except NotFoundError:
            raise
        except Exception as e:
            raise ProcessingError(f"Failed to cancel deletion: {str(e)}")

    async def get_deletion_status(self) -> Optional[dict]:
        """
        Get current deletion request status if any.

        Returns:
            dict: Pending deletion details, or None if no request.
        """
        result = self.supabase.table("account_deletion_requests").select("*").eq(
            "user_id", str(self.user_id)
        ).eq("status", "PENDING").single().execute()

        if result.data:
            return {
                "has_pending_deletion": True,
                "scheduled_deletion_at": result.data["scheduled_deletion_at"],
                "requested_at": result.data["requested_at"],
            }
        return None

    def _generate_export_id(self) -> str:
        """
        Generate a unique export ID.

        Returns:
            str: 16-character hex export identifier.
        """
        return hashlib.sha256(
            f"{self.user_id}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
