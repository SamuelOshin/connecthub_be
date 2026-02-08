"""
Photos API router.

Handles all photo-related endpoints including:
- Get user's photos
- Upload URL generation
- Photo CRUD operations
- Photo reordering
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.utils.response_payloads import success_response
from .schemas import (
    PhotoCreate,
    PhotoUpdate,
    PhotoReorder,
)
from .service import PhotoService


router = APIRouter(prefix="/photos", tags=["Photos"])


@router.get("/")
async def get_my_photos(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get all photos for the current user.

    Args:
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with list of photos.
    """
    service = PhotoService(supabase, user_id)
    photos = await service.get_my_photos()

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Photos retrieved successfully.",
        data={"photos": photos},
    )


get_my_photos._custom_errors = ["401", "500"]
get_my_photos._custom_success = {
    "status_code": 200,
    "description": "Photos retrieved successfully.",
}


@router.post("/upload-url")
async def get_upload_url(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get a signed URL for uploading a new photo.

    Args:
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with upload URL and storage path.

    Raises:
        RateLimitExceededError: If maximum photo limit is reached.
    """
    service = PhotoService(supabase, user_id)
    result = await service.create_upload_url()

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Upload URL generated successfully.",
        data=result,
    )


get_upload_url._custom_errors = ["400", "401", "429", "500"]
get_upload_url._custom_success = {
    "status_code": 200,
    "description": "Upload URL generated successfully.",
}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_photo(
    data: PhotoCreate,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Create a photo record after successful upload.

    Args:
        data: Photo creation data with storage_path, order_index, and is_primary.
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with created photo.

    Raises:
        ProcessingError: If photo creation fails.
    """
    service = PhotoService(supabase, user_id)
    photo = await service.create_photo(
        storage_path=data.storage_path,
        order_index=data.order_index,
        is_primary=data.is_primary,
    )

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Photo created successfully.",
        data=photo,
    )


create_photo._custom_errors = ["400", "401", "422", "500"]
create_photo._custom_success = {
    "status_code": 201,
    "description": "Photo created successfully.",
}


@router.patch("/{photo_id}")
async def update_photo(
    photo_id: UUID,
    data: PhotoUpdate,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Update a photo's order or primary status.

    Args:
        photo_id: UUID of the photo to update.
        data: Photo update data with order_index and/or is_primary.
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with updated photo.

    Raises:
        NotFoundError: If photo does not exist or is not owned by user.
    """
    service = PhotoService(supabase, user_id)
    photo = await service.update_photo(
        photo_id=photo_id,
        order_index=data.order_index,
        is_primary=data.is_primary,
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Photo updated successfully.",
        data=photo,
    )


update_photo._custom_errors = ["400", "401", "404", "422", "500"]
update_photo._custom_success = {
    "status_code": 200,
    "description": "Photo updated successfully.",
}


@router.post("/reorder")
async def reorder_photos(
    data: PhotoReorder,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Reorder photos by providing ordered list of photo IDs.

    Args:
        data: Reorder data with list of photo IDs in desired order.
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with reordered photos.
    """
    service = PhotoService(supabase, user_id)
    photos = await service.reorder_photos(data.photo_ids)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Photos reordered successfully.",
        data={"photos": photos},
    )


reorder_photos._custom_errors = ["400", "401", "422", "500"]
reorder_photos._custom_success = {
    "status_code": 200,
    "description": "Photos reordered successfully.",
}


@router.delete("/{photo_id}", status_code=status.HTTP_200_OK)
async def delete_photo(
    photo_id: UUID,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Delete a photo.

    Args:
        photo_id: UUID of the photo to delete.
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response confirming deletion.

    Raises:
        NotFoundError: If photo does not exist or is not owned by user.
    """
    service = PhotoService(supabase, user_id)
    await service.delete_photo(photo_id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Photo deleted successfully.",
        data={"photo_id": str(photo_id)},
    )


delete_photo._custom_errors = ["401", "404", "500"]
delete_photo._custom_success = {
    "status_code": 200,
    "description": "Photo deleted successfully.",
}
