"""
Profile API router.

Handles all profile-related endpoints including:
- Get/create/update user profile
- Location updates
- Heartbeat (activity tracking)
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.core.custom_exceptions.exceptions import NotFoundError, AlreadyExistsError
from app.api.utils.response_payloads import success_response
from .schemas import (
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    LocationUpdate,
)
from .service import ProfileService


router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("/me")
async def get_my_profile(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get the current user's profile.

    Args:
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with profile data.

    Raises:
        NotFoundError: If profile does not exist.
    """
    service = ProfileService(supabase, user_id)
    profile = await service.get_my_profile()

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Profile retrieved successfully.",
        data=profile,
    )


get_my_profile._custom_errors = ["401", "404", "500"]
get_my_profile._custom_success = {
    "status_code": 200,
    "description": "Profile retrieved successfully.",
}


@router.post("/me", status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: ProfileCreate,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Create a profile during onboarding.

    Args:
        data: Profile creation data with display_name, birthdate, etc.
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with created profile.

    Raises:
        AlreadyExistsError: If profile already exists for this user.
    """
    service = ProfileService(supabase, user_id)
    profile = await service.create_profile(data)

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Profile created successfully.",
        data=profile,
    )


create_profile._custom_errors = ["400", "401", "409", "422", "500"]
create_profile._custom_success = {
    "status_code": 201,
    "description": "Profile created successfully.",
}


@router.patch("/me")
async def update_profile(
    data: ProfileUpdate,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Update the current user's profile.

    Args:
        data: Partial profile update data.
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with updated profile.

    Raises:
        NotFoundError: If profile does not exist.
    """
    service = ProfileService(supabase, user_id)
    profile = await service.update_profile(data)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Profile updated successfully.",
        data=profile,
    )


update_profile._custom_errors = ["400", "401", "404", "422", "500"]
update_profile._custom_success = {
    "status_code": 200,
    "description": "Profile updated successfully.",
}


@router.put("/me/location")
async def update_location(
    data: LocationUpdate,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Update the current user's location.

    Args:
        data: Location data with latitude and longitude.
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response confirming update.
    """
    service = ProfileService(supabase, user_id)
    await service.update_location(data)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Location updated successfully.",
        data={"status": "location_updated"},
    )


update_location._custom_errors = ["400", "401", "422", "500"]
update_location._custom_success = {
    "status_code": 200,
    "description": "Location updated successfully.",
}


@router.post("/me/heartbeat")
async def heartbeat(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Update last_active timestamp (call periodically from app).

    Args:
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response.
    """
    service = ProfileService(supabase, user_id)
    await service.update_last_active()

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Heartbeat recorded.",
        data={"status": "ok"},
    )


heartbeat._custom_errors = ["401", "500"]
heartbeat._custom_success = {
    "status_code": 200,
    "description": "Heartbeat recorded successfully.",
}


@router.get("/{profile_id}")
async def get_profile(
    profile_id: UUID,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get a public profile by ID.

    Args:
        profile_id: UUID of the profile to retrieve.
        user_id: Current authenticated user's ID (from JWT).
        supabase: Authenticated Supabase client.

    Returns:
        JSONResponse: Standardized success response with profile data.

    Raises:
        NotFoundError: If profile does not exist.
    """
    service = ProfileService(supabase, user_id)
    profile = await service.get_profile_by_id(profile_id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Profile retrieved successfully.",
        data=profile,
    )


get_profile._custom_errors = ["401", "404", "500"]
get_profile._custom_success = {
    "status_code": 200,
    "description": "Profile retrieved successfully.",
}
