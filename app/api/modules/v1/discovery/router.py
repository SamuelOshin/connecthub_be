"""
Discovery API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.utils.response_payloads import success_response
from app.api.modules.v1.discovery.service import DiscoveryService
from app.api.modules.v1.discovery.schemas import (
    SwipeCreate,
    PreferencesUpdate,
)


router = APIRouter(prefix="/discovery", tags=["Discovery"])


# ===========================================
# DISCOVERY ENDPOINTS
# ===========================================


@router.get("/profiles")
async def get_discovery_profiles(
    limit: int = Query(10, ge=1, le=50),
    cursor: Optional[str] = Query(None),
    current_user_id: CurrentUserId = None,
    supabase: AuthenticatedClient = None,
):
    """
    Get discovery profiles for swiping.
    
    Returns scored profiles with match reasons.
    Uses pre-computed queue for performance.
    """

    service = DiscoveryService(supabase)
    result = await service.get_discovery_profiles(
        user_id=current_user_id,
        limit=limit,
        cursor=cursor,
    )

    return success_response(
        status_code=200,
        message="Discovery profiles retrieved",
        data=result.model_dump(),
    )


@router.post("/swipe")
async def create_swipe(
    swipe: SwipeCreate,
    current_user_id: CurrentUserId = None,
    supabase: AuthenticatedClient = None,
):
    """
    Record a swipe action.
    
    For RIGHT/SUPER_LIKE:
    - Comment is REQUIRED (min 10 characters)
    - Specify which photo/prompt the comment is about
    
    Returns match info if mutual like detected.
    """

    service = DiscoveryService(supabase)
    result = await service.create_swipe(
        user_id=current_user_id,
        swipe=swipe,
    )

    return success_response(
        status_code=201,
        message="Swipe recorded" if not result.match else "It's a match!",
        data=result.model_dump(),
    )


@router.get("/stats")
async def get_discovery_stats(
    current_user_id: CurrentUserId = None,
    supabase: AuthenticatedClient = None,
):
    """
    Get user's discovery statistics.
    
    Returns likes sent/remaining, match rate, response rate.
    """

    service = DiscoveryService(supabase)
    result = await service.get_discovery_stats(
        user_id=current_user_id,
    )

    return success_response(
        status_code=200,
        message="Discovery stats retrieved",
        data=result.model_dump(),
    )


# ===========================================
# PREFERENCES ENDPOINTS
# ===========================================


@router.get("/preferences")
async def get_preferences(
    current_user_id: CurrentUserId = None,
    supabase: AuthenticatedClient = None,
):
    """
    Get user's matching preferences.
    """

    service = DiscoveryService(supabase)
    result = await service.get_user_preferences(
        user_id=current_user_id,
    )

    return success_response(
        status_code=200,
        message="Preferences retrieved",
        data=result.model_dump(),
    )


@router.put("/preferences")
async def update_preferences(
    preferences: PreferencesUpdate,
    current_user_id: CurrentUserId = None,
    supabase: AuthenticatedClient = None,
):
    """
    Update user's matching preferences.
    """

    service = DiscoveryService(supabase)
    result = await service.update_user_preferences(
        user_id=current_user_id,
        updates=preferences.model_dump(exclude_none=True),
    )

    return success_response(
        status_code=200,
        message="Preferences updated",
        data=result.model_dump(),
    )
