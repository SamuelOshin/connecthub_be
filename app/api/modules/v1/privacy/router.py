"""
Privacy API Router - GDPR Compliance Endpoints.

Provides endpoints for:
- Data export (GDPR Article 20)
- Account deletion (GDPR Article 17)
"""

from fastapi import APIRouter

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.utils.response_payloads import success_response
from .service import PrivacyService
from .schemas import AccountDeletionRequest

router = APIRouter(prefix="/privacy", tags=["Privacy & GDPR"])


@router.get("/export")
async def export_user_data(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Export all user data (GDPR Article 20 - Right to Data Portability).

    Returns a complete JSON export of profile, photos, matches,
    messages, swipes, preferences, and feedback.
    """
    service = PrivacyService(supabase, user_id)
    data = await service.export_user_data()

    return success_response(
        status_code=200,
        message="Data export generated successfully.",
        data=data,
    )


@router.post("/delete-request")
async def request_account_deletion(
    request: AccountDeletionRequest,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """
    Request account deletion (GDPR Article 17 - Right to Erasure).

    Initiates a 30-day grace period before permanent deletion.
    User can cancel the request within this period.
    """
    service = PrivacyService(supabase, user_id)
    result = await service.request_deletion(reason=request.reason)

    return success_response(
        status_code=201,
        message="Deletion request created.",
        data=result,
    )


@router.delete("/cancel-deletion")
async def cancel_deletion_request(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """Cancel a pending account deletion request."""
    service = PrivacyService(supabase, user_id)
    result = await service.cancel_deletion()

    return success_response(
        status_code=200,
        message="Deletion request cancelled.",
        data=result,
    )


@router.get("/deletion-status")
async def get_deletion_status(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """Check if there's a pending deletion request."""
    service = PrivacyService(supabase, user_id)
    status = await service.get_deletion_status()

    return success_response(
        status_code=200,
        message="Deletion status retrieved.",
        data=status or {"has_pending_deletion": False},
    )
