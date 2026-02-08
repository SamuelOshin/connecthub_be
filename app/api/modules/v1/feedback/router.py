"""
Feedback API endpoints for 'We Connected' system.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.core.supabase import get_supabase_client
from app.api.utils.response_payloads import success_response
from app.api.modules.v1.feedback.service import FeedbackService
from app.api.modules.v1.feedback.schemas import ConnectionFeedbackCreate


router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.get("/pending")
async def get_pending_feedback(
    current_user: dict = Depends(lambda: {"id": "temp"}),  # TODO: Add auth
    supabase=Depends(get_supabase_client),
):
    """
    Get matches that need feedback.
    
    Returns matches older than 3 days without submitted feedback.
    Use this to prompt users for "We Connected" feedback.
    """

    service = FeedbackService(supabase)
    result = await service.get_pending_feedback(
        user_id=UUID(current_user["id"]),
    )

    return success_response(
        status_code=200,
        message="Pending feedback retrieved",
        data=result.model_dump(),
    )


@router.post("")
async def submit_feedback(
    feedback: ConnectionFeedbackCreate,
    current_user: dict = Depends(lambda: {"id": "temp"}),  # TODO: Add auth
    supabase=Depends(get_supabase_client),
):
    """
    Submit connection feedback for a match.
    
    This helps us improve match quality by learning from real outcomes.
    
    Questions:
    - Did you meet? (required)
    - Meeting type: VIDEO_CALL, IN_PERSON, STILL_CHATTING, NO_CONTACT
    - Would you meet again? (if met)
    - Connection quality (1-5 stars, if met)
    - What worked/didn't work?
    """

    service = FeedbackService(supabase)
    result = await service.submit_feedback(
        user_id=UUID(current_user["id"]),
        feedback=feedback,
    )

    return success_response(
        status_code=201,
        message=result.thank_you_message,
        data=result.model_dump(),
    )


@router.get("/{match_id}")
async def get_feedback(
    match_id: UUID,
    current_user: dict = Depends(lambda: {"id": "temp"}),  # TODO: Add auth
    supabase=Depends(get_supabase_client),
):
    """
    Get feedback you submitted for a match.
    """

    service = FeedbackService(supabase)
    result = await service.get_feedback(
        user_id=UUID(current_user["id"]),
        match_id=match_id,
    )

    if not result:
        return success_response(
            status_code=200,
            message="No feedback submitted yet",
            data=None,
        )

    return success_response(
        status_code=200,
        message="Feedback retrieved",
        data=result.model_dump(),
    )
