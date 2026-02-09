"""
Chat API router.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.utils.response_payloads import success_response
from app.api.modules.v1.chat.schemas import (
    MessageCreate,
    MarkReadRequest,
)
from app.api.modules.v1.chat.service import ChatService


router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations")
async def get_conversations(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get all conversations (active matches) with message previews.
    """
    service = ChatService(supabase)
    result = await service.get_conversations(
        user_id=user_id,
        limit=limit,
    )
    return success_response(
        status_code=200,
        message="Conversations retrieved",
        data=result.model_dump(),
    )


@router.get("/{match_id}/messages")
async def get_messages(
    match_id: UUID,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
    cursor: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get paginated messages for a match.
    Use cursor for pagination (ISO timestamp).
    """
    service = ChatService(supabase)
    result = await service.get_messages(
        user_id=user_id,
        match_id=match_id,
        cursor=cursor,
        limit=limit,
    )
    return success_response(
        status_code=200,
        message="Messages retrieved",
        data=result.model_dump(),
    )


@router.post("/{match_id}/messages")
async def send_message(
    match_id: UUID,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
    message: MessageCreate,
):
    """
    Send a message in a match conversation.
    
    If this is the first message, it will extend the match expiration.
    """
    service = ChatService(supabase)
    result = await service.send_message(
        user_id=user_id,
        match_id=match_id,
        message_data=message,
    )
    return success_response(
        status_code=201,
        message="Message sent",
        data=result.model_dump(),
    )


@router.post("/{match_id}/read")
async def mark_messages_read(
    match_id: UUID,
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
    body: Optional[MarkReadRequest] = None,
):
    """
    Mark messages as read in a conversation.
    """
    service = ChatService(supabase)
    count = await service.mark_as_read(
        user_id=user_id,
        match_id=match_id,
        last_read_message_id=body.last_read_message_id if body else None,
    )
    return success_response(
        status_code=200,
        message="Messages marked as read",
        data={"marked_read": count},
    )

