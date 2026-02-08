"""
Matches API endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.utils.response_payloads import success_response
from app.api.modules.v1.matches.service import MatchesService


router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("")
async def get_matches(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
    status: Optional[str] = Query(None, pattern="^(ACTIVE|EXPIRED|UNMATCHED)$"),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get all matches for the current user.
    
    Filter by status: ACTIVE, EXPIRED, UNMATCHED
    """

    service = MatchesService(supabase)
    result = await service.get_matches(
        user_id=user_id,
        status=status,
        limit=limit,
    )

    return success_response(
        status_code=200,
        message="Matches retrieved",
        data=result.model_dump(),
    )


# NOTE: Static routes like /likes-you and /stats MUST come before /{match_id}
@router.get("/likes-you")
async def get_likes_you(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get profiles of users who liked you.
    
    Returns full profile data for each user who has swiped right on you
    but you haven't swiped on yet. Useful for "Who Liked You" feature.
    """
    service = MatchesService(supabase)
    profiles = await service.get_likes_you(user_id=user_id)

    return success_response(
        status_code=200,
        message="Likes retrieved",
        data={"profiles": profiles, "count": len(profiles)},
    )


# NOTE: /stats MUST come before /{match_id} to avoid route conflict
@router.get("/stats")
async def get_match_stats(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get match-related statistics for sidebar badges.
    
    Returns:
    - active_count: Number of active matches
    - likes_you_count: Number of users who liked you (pending likes)
    """
    service = MatchesService(supabase)
    result = await service.get_stats(user_id=user_id)

    return success_response(
        status_code=200,
        message="Match stats retrieved",
        data=result,
    )


@router.get("/{match_id}")
async def get_match(
    match_id: UUID,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Get detailed match information.
    
    Includes:
    - Matched user info
    - Opening comments from both users
    - Match reasons
    - Expiration status
    - Chat preview
    """

    service = MatchesService(supabase)
    result = await service.get_match(
        user_id=user_id,
        match_id=match_id,
    )

    return success_response(
        status_code=200,
        message="Match details retrieved",
        data=result.model_dump(),
    )


@router.delete("/{match_id}")
async def unmatch(
    match_id: UUID,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Unmatch with a user.
    
    This will:
    - Set match status to UNMATCHED
    - Hide the conversation from both users
    """

    service = MatchesService(supabase)
    result = await service.unmatch(
        user_id=user_id,
        match_id=match_id,
    )

    return success_response(
        status_code=200,
        message=result.message,
        data=result.model_dump(),
    )
