"""
Profile service layer - business logic for profile operations.

Contains all business logic for profile management including:
- Profile CRUD operations
- Location updates with PostGIS
- Activity tracking
"""

from datetime import date
from typing import Optional
from uuid import UUID

from supabase import Client

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    AlreadyExistsError,
    ProcessingError,
)
from .schemas import (
    ProfileCreate,
    ProfileUpdate,
    LocationUpdate,
)


class ProfileService:
    """
    Service for profile operations.

    Handles all business logic related to user profiles including
    CRUD operations, location updates, and activity tracking.

    Attributes:
        supabase: Authenticated Supabase client (respects RLS).
        user_id: Current authenticated user's UUID.
    """

    def __init__(self, supabase: Client, user_id: UUID):
        """
        Initialize profile service.

        Args:
            supabase: Authenticated Supabase client (respects RLS).
            user_id: Current authenticated user's ID.
        """
        self.supabase = supabase
        self.user_id = user_id

    async def get_my_profile(self) -> dict:
        """
        Get the current user's profile.

        Returns:
            dict: Profile data with computed fields (age, primary_photo_url).

        Raises:
            NotFoundError: If profile does not exist for this user.
        """
        response = self.supabase.table("profiles").select(
            "*, photos(id, storage_path, order_index, is_primary, moderation_status)"
        ).eq("id", str(self.user_id)).maybe_single().execute()

        if not response or not response.data:
            raise NotFoundError("Profile not found. Please complete onboarding.")

        profile = response.data
        profile["age"] = self._calculate_age(profile.get("birthdate"))
        profile["primary_photo_url"] = self._get_primary_photo_url(profile.get("photos", []))

        return profile

    async def create_profile(self, data: ProfileCreate) -> dict:
        """
        Create a new profile during onboarding.

        Args:
            data: Profile creation data with display_name, birthdate, gender, etc.

        Returns:
            dict: The newly created profile data.

        Raises:
            AlreadyExistsError: If profile already exists for this user.
            ProcessingError: If database operation fails.
        """
        # Check if profile already exists
        existing = self.supabase.table("profiles").select("id").eq(
            "id", str(self.user_id)
        ).execute()

        if existing.data:
            raise AlreadyExistsError("Profile already exists for this user.")

        profile_data = {
            "id": str(self.user_id),
            "display_name": data.display_name,
            "birthdate": data.birthdate.isoformat(),
            "gender": data.gender,
            "looking_for": data.looking_for,
            "bio": data.bio,
        }

        try:
            response = self.supabase.table("profiles").insert(profile_data).execute()

            if not response.data:
                raise ProcessingError("Failed to create profile.")

            return response.data[0]
        except Exception as e:
            if "already exists" in str(e).lower():
                raise AlreadyExistsError("Profile already exists for this user.")
            raise ProcessingError(f"Failed to create profile: {str(e)}")

    async def update_profile(self, data: ProfileUpdate) -> dict:
        """
        Update the current user's profile.

        Args:
            data: Partial profile update data.

        Returns:
            dict: The updated profile data.

        Raises:
            NotFoundError: If profile does not exist.
            ProcessingError: If database operation fails.
        """
        update_data = data.model_dump(exclude_none=True)

        # Handle nested objects
        if "preferences" in update_data and data.preferences:
            update_data["preferences"] = data.preferences.model_dump()
        if "prompts" in update_data and data.prompts:
            update_data["prompts"] = [p.model_dump() for p in data.prompts]

        if not update_data:
            # No updates provided, return existing profile
            return await self.get_my_profile()

        response = self.supabase.table("profiles").update(update_data).eq(
            "id", str(self.user_id)
        ).execute()

        if not response.data:
            raise NotFoundError("Profile not found.")

        return response.data[0]

    async def update_location(self, location: LocationUpdate) -> None:
        """
        Update the user's location using PostGIS.

        Args:
            location: Location data with latitude and longitude.

        Raises:
            ProcessingError: If location update fails.
        """
        # Create PostGIS POINT geometry
        point_wkt = f"SRID=4326;POINT({location.longitude} {location.latitude})"

        try:
            response = self.supabase.rpc(
                "update_profile_location",
                {
                    "user_id": str(self.user_id),
                    "location_wkt": point_wkt,
                }
            ).execute()

            # Fallback: direct update if RPC doesn't exist
            if not response.data:
                self.supabase.table("profiles").update({
                    "location": f"SRID=4326;POINT({location.longitude} {location.latitude})",
                    "last_active": "now()",
                }).eq("id", str(self.user_id)).execute()
        except Exception as e:
            raise ProcessingError(f"Failed to update location: {str(e)}")

    async def update_last_active(self) -> None:
        """
        Update the last_active timestamp.

        Used for activity tracking to determine user's online status.

        Raises:
            ProcessingError: If update fails.
        """
        try:
            self.supabase.table("profiles").update({
                "last_active": "now()"
            }).eq("id", str(self.user_id)).execute()
        except Exception as e:
            raise ProcessingError(f"Failed to update activity: {str(e)}")

    async def get_profile_by_id(self, profile_id: UUID) -> dict:
        """
        Get a public profile by ID.

        Args:
            profile_id: UUID of the profile to retrieve.

        Returns:
            dict: Public profile data with computed fields.

        Raises:
            NotFoundError: If profile does not exist.
        """
        response = self.supabase.table("profiles").select(
            "id, display_name, birthdate, gender, bio, prompts, is_verified, "
            "photos(storage_path, order_index)"
        ).eq("id", str(profile_id)).single().execute()

        if not response.data:
            raise NotFoundError("Profile not found.")

        profile = response.data
        profile["age"] = self._calculate_age(profile.get("birthdate"))
        profile["photos"] = self._get_photo_urls(profile.get("photos", []))

        return profile

    def _calculate_age(self, birthdate_str: Optional[str]) -> Optional[int]:
        """
        Calculate age from birthdate string.

        Args:
            birthdate_str: ISO format date string (YYYY-MM-DD).

        Returns:
            int: Calculated age in years, or None if birthdate not provided.
        """
        if not birthdate_str:
            return None

        birthdate = date.fromisoformat(birthdate_str)
        today = date.today()
        return today.year - birthdate.year - (
            (today.month, today.day) < (birthdate.month, birthdate.day)
        )

    def _get_primary_photo_url(self, photos: list) -> Optional[str]:
        """
        Get the primary photo URL.

        Args:
            photos: List of photo records.

        Returns:
            str: Signed URL for the primary photo, or None if no photos.
        """
        if not photos:
            return None

        primary = next((p for p in photos if p.get("is_primary")), None)
        if not primary:
            primary = min(photos, key=lambda p: p.get("order_index", 999), default=None)

        if primary and primary.get("storage_path"):
            return self._get_signed_url(primary["storage_path"])
        return None

    def _get_photo_urls(self, photos: list) -> list[str]:
        """
        Get signed URLs for all photos.

        Args:
            photos: List of photo records.

        Returns:
            list[str]: List of signed URLs sorted by order_index.
        """
        sorted_photos = sorted(photos, key=lambda p: p.get("order_index", 999))
        return [
            self._get_signed_url(p["storage_path"])
            for p in sorted_photos
            if p.get("storage_path")
        ]

    def _get_signed_url(self, storage_path: str) -> str:
        """
        Generate a signed URL for a storage path.

        Args:
            storage_path: Path to the file in Supabase storage.

        Returns:
            str: Signed URL with 1 hour expiry, or empty string on error.
        """
        try:
            response = self.supabase.storage.from_("photos").create_signed_url(
                storage_path, 3600  # 1 hour expiry
            )
            return response.get("signedURL", "")
        except Exception:
            return ""
