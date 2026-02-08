"""
Safety API Router - Block & Report Endpoints.

Provides endpoints for:
- Blocking/unblocking users
- Reporting policy violations
"""

from uuid import UUID

from fastapi import APIRouter

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.utils.response_payloads import success_response
from .service import SafetyService
from .schemas import ReportUserRequest

router = APIRouter(prefix="/safety", tags=["Safety"])


@router.post("/block/{user_id}")
async def block_user(
    user_id: UUID,
    current_user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Block a user.

    This will remove them from your discovery, hide your profile
    from them, and unmatch if you were matched.
    """
    service = SafetyService(supabase, current_user_id)
    result = await service.block_user(blocked_id=user_id)

    return success_response(
        status_code=201,
        message="User blocked successfully.",
        data=result,
    )


@router.delete("/block/{user_id}")
async def unblock_user(
    user_id: UUID,
    current_user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """Unblock a user."""
    service = SafetyService(supabase, current_user_id)
    result = await service.unblock_user(blocked_id=user_id)

    return success_response(
        status_code=200,
        message="User unblocked successfully.",
        data=result,
    )


@router.get("/blocked")
async def get_blocked_users(
    current_user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """Get list of users you have blocked."""
    service = SafetyService(supabase, current_user_id)
    result = await service.get_blocked_users()

    return success_response(
        status_code=200,
        message="Blocked users retrieved.",
        data=result,
    )


@router.post("/report")
async def report_user(
    request: ReportUserRequest,
    current_user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Report a user for policy violation.

    Reasons:
    - SPAM: Promotional content or spam messages
    - HARASSMENT: Abusive or threatening behavior
    - INAPPROPRIATE_CONTENT: Explicit or offensive content
    - FAKE_PROFILE: Impersonation or catfishing
    - UNDERAGE: User appears to be under 18
    - OTHER: Other violation
    """
    service = SafetyService(supabase, current_user_id)
    result = await service.report_user(
        reported_user_id=request.reported_user_id,
        reason=request.reason,
        details=request.details,
    )

    return success_response(
        status_code=201,
        message="Report submitted successfully.",
        data=result,
    )
