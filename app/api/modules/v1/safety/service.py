"""
Safety service layer - business logic for block and report operations.

Contains all business logic for user safety including:
- Blocking/unblocking users
- Reporting users for policy violations
"""

from typing import Optional
from uuid import UUID

from supabase import Client

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ConflictError,
    BadRequestError,
    ProcessingError,
)


class SafetyService:
    """
    Service for user safety operations.

    Handles blocking and reporting users to maintain platform safety.

    Attributes:
        supabase: Authenticated Supabase client (respects RLS).
        user_id: Current authenticated user's UUID.
    """

    def __init__(self, supabase: Client, user_id: UUID):
        """
        Initialize safety service.

        Args:
            supabase: Authenticated Supabase client (respects RLS).
            user_id: Current authenticated user's ID.
        """
        self.supabase = supabase
        self.user_id = user_id

    async def block_user(self, blocked_id: UUID) -> dict:
        """
        Block a user.

        This will prevent them from appearing in discovery, hide your
        profile from them, and unmatch if currently matched.

        Args:
            blocked_id: UUID of the user to block.

        Returns:
            dict: Confirmation with blocked user ID and message.

        Raises:
            BadRequestError: If attempting to block yourself.
            ConflictError: If user is already blocked.
            ProcessingError: If blocking fails.
        """
        if self.user_id == blocked_id:
            raise BadRequestError("You cannot block yourself.")

        # Check if already blocked
        existing = self.supabase.table("blocked_users").select("id").eq(
            "blocker_id", str(self.user_id)
        ).eq("blocked_id", str(blocked_id)).execute()

        if existing.data:
            raise ConflictError("User is already blocked.")

        try:
            # Create block
            result = self.supabase.table("blocked_users").insert({
                "blocker_id": str(self.user_id),
                "blocked_id": str(blocked_id),
            }).execute()

            if not result.data:
                raise ProcessingError("Failed to block user.")

            # Unmatch if there's an active match
            self._unmatch_blocked_user(blocked_id)

            return {
                "blocked_user_id": str(blocked_id),
                "message": "User has been blocked. They will no longer appear in your discovery.",
            }
        except (BadRequestError, ConflictError):
            raise
        except Exception as e:
            raise ProcessingError(f"Failed to block user: {str(e)}")

    async def unblock_user(self, blocked_id: UUID) -> dict:
        """
        Unblock a user.

        Args:
            blocked_id: UUID of the user to unblock.

        Returns:
            dict: Confirmation with unblocked user ID.

        Raises:
            NotFoundError: If block does not exist.
            ProcessingError: If unblocking fails.
        """
        try:
            result = self.supabase.table("blocked_users").delete().eq(
                "blocker_id", str(self.user_id)
            ).eq("blocked_id", str(blocked_id)).execute()

            if not result.data:
                raise NotFoundError("Block not found.")

            return {
                "unblocked_user_id": str(blocked_id),
                "message": "User has been unblocked.",
            }
        except NotFoundError:
            raise
        except Exception as e:
            raise ProcessingError(f"Failed to unblock user: {str(e)}")

    async def get_blocked_users(self) -> dict:
        """
        Get list of blocked users with basic profile info.

        Returns:
            dict: List of blocked users with total count.
        """
        result = self.supabase.table("blocked_users").select(
            "id, blocked_id, created_at"
        ).eq("blocker_id", str(self.user_id)).order(
            "created_at", desc=True
        ).execute()

        blocked_list = []
        for item in result.data or []:
            # Get basic profile info for blocked user
            profile = self._get_basic_profile(item["blocked_id"])
            blocked_list.append({
                "id": item["id"],
                "blocked_id": item["blocked_id"],
                "blocked_user": profile,
                "created_at": item["created_at"],
            })

        return {
            "blocked_users": blocked_list,
            "total": len(blocked_list),
        }

    async def report_user(
        self,
        reported_user_id: UUID,
        reason: str,
        details: Optional[str] = None,
    ) -> dict:
        """
        Report a user for policy violation.

        Args:
            reported_user_id: UUID of the user being reported.
            reason: Report reason (SPAM, HARASSMENT, etc.).
            details: Optional additional details.

        Returns:
            dict: Report confirmation with ID and status.

        Raises:
            BadRequestError: If attempting to report yourself.
            ProcessingError: If report creation fails.
        """
        if self.user_id == reported_user_id:
            raise BadRequestError("You cannot report yourself.")

        try:
            result = self.supabase.table("reports").insert({
                "reporter_id": str(self.user_id),
                "reported_user_id": str(reported_user_id),
                "reason": reason,
                "details": details,
                "status": "PENDING",
            }).execute()

            if not result.data:
                raise ProcessingError("Failed to create report.")

            return {
                "id": result.data[0]["id"],
                "status": "PENDING",
                "message": "Thank you for reporting. Our team will review this within 24 hours.",
            }
        except BadRequestError:
            raise
        except Exception as e:
            raise ProcessingError(f"Failed to create report: {str(e)}")

    def _unmatch_blocked_user(self, blocked_id: UUID) -> None:
        """
        Unmatch with a blocked user if a match exists.

        Args:
            blocked_id: UUID of the blocked user.
        """
        try:
            self.supabase.table("matches").update({
                "status": "UNMATCHED",
                "unmatch_reason": "blocked",
            }).or_(
                f"and(user1_id.eq.{self.user_id},user2_id.eq.{blocked_id}),"
                f"and(user1_id.eq.{blocked_id},user2_id.eq.{self.user_id})"
            ).eq("status", "ACTIVE").execute()
        except Exception:
            # Don't fail the block operation if unmatch fails
            pass

    def _get_basic_profile(self, user_id: str) -> Optional[dict]:
        """
        Get basic profile info for a user.

        Args:
            user_id: UUID string of the user.

        Returns:
            dict: Basic profile with display_name, or None if not found.
        """
        try:
            result = self.supabase.table("profiles").select(
                "id, display_name"
            ).eq("id", user_id).single().execute()
            return result.data
        except Exception:
            return None
