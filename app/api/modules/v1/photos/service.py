"""
Photo service layer - business logic for photo operations.

Contains all business logic for photo management including:
- Photo CRUD operations
- Upload URL generation
- Photo reordering
- Storage management
"""

import uuid
from typing import Optional
from uuid import UUID

from supabase import Client

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    RateLimitExceededError,
    ProcessingError,
)


class PhotoService:
    """
    Service for photo operations.

    Handles all business logic related to user photos including
    CRUD operations, upload URL generation, and reordering.

    Attributes:
        supabase: Authenticated Supabase client (respects RLS).
        user_id: Current authenticated user's UUID.
        MAX_PHOTOS: Maximum number of photos allowed per user.
    """

    MAX_PHOTOS = 6

    def __init__(self, supabase: Client, user_id: UUID):
        """
        Initialize photo service.

        Args:
            supabase: Authenticated Supabase client (respects RLS).
            user_id: Current authenticated user's ID.
        """
        self.supabase = supabase
        self.user_id = user_id

    async def get_my_photos(self) -> list[dict]:
        """
        Get all photos for the current user.

        Returns:
            list[dict]: List of photo records with signed URLs, sorted by order_index.
        """
        response = self.supabase.table("photos").select("*").eq(
            "user_id", str(self.user_id)
        ).order("order_index").execute()

        photos = response.data or []

        # Add signed URLs
        for photo in photos:
            photo["url"] = self._get_signed_url(photo["storage_path"])

        return photos

    async def get_photo_count(self) -> int:
        """
        Get the number of photos for the current user.

        Returns:
            int: Total count of photos.
        """
        response = self.supabase.table("photos").select(
            "id", count="exact"
        ).eq("user_id", str(self.user_id)).execute()

        return response.count or 0

    async def create_upload_url(self) -> dict:
        """
        Generate a signed upload URL for a new photo.

        Returns:
            dict: Contains upload_url, storage_path, and expires_in.

        Raises:
            RateLimitExceededError: If maximum photo limit is reached.
        """
        # Check photo limit
        count = await self.get_photo_count()
        if count >= self.MAX_PHOTOS:
            raise RateLimitExceededError(
                f"Maximum {self.MAX_PHOTOS} photos allowed. "
                "Please delete an existing photo to upload a new one."
            )

        # Generate unique file path
        file_id = str(uuid.uuid4())
        storage_path = f"{self.user_id}/{file_id}.webp"

        # Create signed upload URL
        response = self.supabase.storage.from_("photos").create_signed_upload_url(
            storage_path
        )

        return {
            "upload_url": response.get("signedURL", ""),
            "storage_path": storage_path,
            "expires_in": 3600,
        }

    async def create_photo(
        self,
        storage_path: str,
        order_index: int = 0,
        is_primary: bool = False,
    ) -> dict:
        """
        Create a photo record after successful upload.

        Args:
            storage_path: Path to the uploaded file in storage.
            order_index: Position in the photo gallery (0-based).
            is_primary: Whether this should be the primary/profile photo.

        Returns:
            dict: The newly created photo record with signed URL.

        Raises:
            ProcessingError: If photo creation fails.
        """
        # If this is the first photo or marked as primary, set as primary
        count = await self.get_photo_count()
        if count == 0:
            is_primary = True

        photo_data = {
            "user_id": str(self.user_id),
            "storage_path": storage_path,
            "order_index": order_index if order_index else count,
            "is_primary": is_primary,
            "moderation_status": "approved",  # Auto-approve for MVP; add moderation later
        }

        # If setting as primary, unset others
        if is_primary:
            await self._unset_primary()

        try:
            response = self.supabase.table("photos").insert(photo_data).execute()

            if not response.data:
                raise ProcessingError("Failed to create photo record.")

            photo = response.data[0]
            photo["url"] = self._get_signed_url(photo["storage_path"])

            return photo
        except Exception as e:
            raise ProcessingError(f"Failed to create photo: {str(e)}")

    async def update_photo(
        self,
        photo_id: UUID,
        order_index: Optional[int] = None,
        is_primary: Optional[bool] = None,
    ) -> dict:
        """
        Update a photo's order or primary status.

        Args:
            photo_id: UUID of the photo to update.
            order_index: New position in the gallery (optional).
            is_primary: New primary status (optional).

        Returns:
            dict: The updated photo record with signed URL.

        Raises:
            NotFoundError: If photo does not exist or is not owned by user.
        """
        # Verify ownership
        existing = await self._get_photo_if_owned(photo_id)
        if not existing:
            raise NotFoundError("Photo not found.")

        update_data = {}
        if order_index is not None:
            update_data["order_index"] = order_index
        if is_primary is not None:
            update_data["is_primary"] = is_primary
            if is_primary:
                await self._unset_primary()

        if not update_data:
            existing["url"] = self._get_signed_url(existing["storage_path"])
            return existing

        response = self.supabase.table("photos").update(update_data).eq(
            "id", str(photo_id)
        ).execute()

        if not response.data:
            raise NotFoundError("Photo not found.")

        photo = response.data[0]
        photo["url"] = self._get_signed_url(photo["storage_path"])

        return photo

    async def reorder_photos(self, photo_ids: list[UUID]) -> list[dict]:
        """
        Reorder photos by updating their order_index.

        The first photo (position 0) is automatically set as primary.

        Args:
            photo_ids: List of photo UUIDs in the desired order.

        Returns:
            list[dict]: All photos with updated order, including signed URLs.
        """
        # First unset all primary flags
        await self._unset_primary()

        for index, photo_id in enumerate(photo_ids):
            # Set is_primary=True for the first photo (position 0)
            update_data = {"order_index": index, "is_primary": index == 0}
            self.supabase.table("photos").update(update_data).eq(
                "id", str(photo_id)
            ).eq("user_id", str(self.user_id)).execute()

        return await self.get_my_photos()

    async def delete_photo(self, photo_id: UUID) -> None:
        """
        Delete a photo from storage and database.

        Args:
            photo_id: UUID of the photo to delete.

        Raises:
            NotFoundError: If photo does not exist or is not owned by user.
        """
        # Verify ownership and get storage path
        existing = await self._get_photo_if_owned(photo_id)
        if not existing:
            raise NotFoundError("Photo not found.")

        storage_path = existing.get("storage_path")
        was_primary = existing.get("is_primary", False)

        # Delete from storage
        if storage_path:
            try:
                self.supabase.storage.from_("photos").remove([storage_path])
            except Exception:
                # Continue even if storage deletion fails
                pass

        # Delete from database
        self.supabase.table("photos").delete().eq("id", str(photo_id)).execute()

        # If was primary, set a new primary
        if was_primary:
            photos = await self.get_my_photos()
            if photos:
                await self.update_photo(UUID(photos[0]["id"]), is_primary=True)

    async def _get_photo_if_owned(self, photo_id: UUID) -> Optional[dict]:
        """
        Get a photo only if owned by current user.

        Args:
            photo_id: UUID of the photo to retrieve.

        Returns:
            dict: Photo record if owned by user, None otherwise.
        """
        response = self.supabase.table("photos").select("*").eq(
            "id", str(photo_id)
        ).eq("user_id", str(self.user_id)).single().execute()

        return response.data

    async def _unset_primary(self) -> None:
        """
        Unset primary flag on all user's photos.

        Used before setting a new primary photo.
        """
        self.supabase.table("photos").update({
            "is_primary": False
        }).eq("user_id", str(self.user_id)).execute()

    def _get_signed_url(self, storage_path: str) -> str:
        """
        Get public URL for a storage path.
        
        Note: Renamed to match usage but methods calls it _get_signed_url.
        Switching to public URL for consistency with DiscoveryService.
        """
        try:
            return self.supabase.storage.from_("photos").get_public_url(storage_path)
        except Exception:
            return ""
