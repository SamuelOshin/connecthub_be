"""
Chat API schemas.
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ===========================================
# REQUEST SCHEMAS
# ===========================================


class MessageCreate(BaseModel):
    """Request to send a message."""

    content: str = Field(..., min_length=1, max_length=2000)
    message_type: Literal["text", "image", "system"] = "text"


class MarkReadRequest(BaseModel):
    """Request to mark messages as read."""

    last_read_message_id: Optional[UUID] = None  # If None, mark all as read


# ===========================================
# RESPONSE SCHEMAS
# ===========================================


class MessageSender(BaseModel):
    """Info about message sender."""

    id: UUID
    display_name: Optional[str]
    avatar_url: Optional[str]


class MessageResponse(BaseModel):
    """Single message."""

    id: UUID
    match_id: UUID
    sender_id: UUID
    sender: Optional[MessageSender] = None
    content: str
    message_type: str = "text"
    created_at: datetime
    read_at: Optional[datetime] = None
    is_mine: bool = False  # Populated based on current user


class ReadCursorResponse(BaseModel):
    """Read cursor for a user within a match."""

    match_id: UUID
    user_id: UUID
    last_read_message_id: Optional[UUID] = None
    last_read_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MessageListResponse(BaseModel):
    """Paginated message list."""

    messages: list[MessageResponse]
    has_more: bool
    next_cursor: Optional[str] = None  # ISO timestamp of oldest message
    other_user_read_cursor: Optional[ReadCursorResponse] = None


class ConversationPreview(BaseModel):
    """Conversation preview for list view."""

    match_id: UUID
    matched_user_id: UUID
    matched_user_display_name: Optional[str]
    matched_user_avatar_url: Optional[str]
    matched_at: datetime
    
    # Message preview
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    last_message_is_mine: bool = False
    unread_count: int = 0
    
    # Status
    has_started_chatting: bool = False
    hours_until_expiry: Optional[float] = None
    is_expiring_soon: bool = False




class ConversationListResponse(BaseModel):
    """List of conversations."""

    conversations: list[ConversationPreview]
    total_count: int


class SendMessageResponse(BaseModel):
    """Response after sending a message."""

    message: MessageResponse
    first_message_sent: bool = False  # True if this was the first message in match


class TypingEvent(BaseModel):
    """Typing indicator event (for reference, used via Supabase Realtime)."""

    match_id: UUID
    user_id: UUID
    is_typing: bool
