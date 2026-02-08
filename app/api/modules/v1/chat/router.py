"""
Chat API router.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.core.dependencies import CurrentUserId, AuthenticatedClient
from app.api.modules.v1.chat.schemas import (
    MessageCreate,
    MessageListResponse,
    ConversationListResponse,
    SendMessageResponse,
    MarkReadRequest,
)
from app.api.modules.v1.chat.service import ChatService


router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get all conversations (active matches) with message previews.
    """
    service = ChatService(supabase)
    return await service.get_conversations(
        user_id=user_id,
        limit=limit,
    )


@router.get("/{match_id}/messages", response_model=MessageListResponse)
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
    return await service.get_messages(
        user_id=user_id,
        match_id=match_id,
        cursor=cursor,
        limit=limit,
    )


@router.post("/{match_id}/messages", response_model=SendMessageResponse)
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
    return await service.send_message(
        user_id=user_id,
        match_id=match_id,
        message_data=message,
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
    return {"marked_read": count}
