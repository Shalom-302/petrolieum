"""
Conversation Schemas

This module defines Pydantic schemas for conversation validation and serialization.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import uuid

from .message import MessageResponse


class ParticipantBase(BaseModel):
    """Base schema for conversation participants."""
    user_id: str
    role: str = "member"


class ParticipantResponse(ParticipantBase):
    """Schema for participant response."""
    joined_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class UserConversationSettingsBase(BaseModel):
    """Base schema for user conversation settings."""
    is_muted: Optional[bool] = False
    is_pinned: Optional[bool] = False
    is_archived: Optional[bool] = False
    custom_name: Optional[str] = None
    theme_color: Optional[str] = None
    notification_level: Optional[str] = "all"
    last_read_message_id: Optional[str] = None
    last_read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    profile_picture: Optional[str] = None


class UserConversationSettingsUpdate(UserConversationSettingsBase):
    """Schema for updating user conversation settings."""
    pass


class UserConversationSettingsResponse(UserConversationSettingsBase):
    """Schema for user conversation settings response."""
    id: str
    user_id: str
    conversation_id: str
    role: str
    last_read_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationBase(BaseModel):
    """Base schema for conversations."""
    conversation_type: str = Field(..., description="Type of conversation: direct, group, broadcast")
    title: Optional[str] = None
    avatar_url: Optional[str] = None
    is_encrypted: bool = True
    conversation_metadata: Optional[Dict[str, Any]] = None


class DirectConversationCreate(BaseModel):
    """Schema for creating a new direct conversation."""
    recipient_id: str
    is_encrypted: bool = True
    initial_message: Optional[str] = None


class GroupConversationCreate(ConversationBase):
    """Schema for creating a new group conversation."""
    participant_ids: List[str]
    description: Optional[str] = None
    max_participants: int = 100
    is_public: bool = False
    join_mode: str = "invite_only"
    message_permission: str = "all_members"
    who_can_invite: str = "admins"
    who_can_remove: str = "admins"


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""
    title: Optional[str] = None
    avatar_url: Optional[str] = None
    conversation_metadata: Optional[Dict[str, Any]] = None


class GroupConversationUpdate(ConversationUpdate):
    """Schema for updating a group conversation."""
    description: Optional[str] = None
    is_public: Optional[bool] = None
    join_mode: Optional[str] = None
    message_permission: Optional[str] = None
    who_can_invite: Optional[str] = None
    who_can_remove: Optional[str] = None


class ConversationMemberAction(BaseModel):
    """Schema for adding or removing a conversation member."""
    user_id: str
    role: Optional[str] = "member"


class ConversationResponse(ConversationBase):
    """Schema for conversation response."""
    id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None
    participants: List[UserConversationSettingsResponse] = []
    last_message: Optional[MessageResponse] = None
    unread_count: Optional[int] = 0

    class Config:
        from_attributes = True


class GroupConversationResponse(ConversationResponse):
    """Schema for group conversation response with additional settings."""
    description: Optional[str] = None
    max_participants: int
    is_public: bool
    join_mode: str
    message_permission: str
    who_can_invite: str
    who_can_remove: str

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Schema for list of conversations."""
    conversations: List[ConversationResponse]
    total: int
    page: int
    size: int


class UserBlockBase(BaseModel):
    """Base schema for blocked users."""
    blocked_id: str
    reason: Optional[str] = None


class UserBlockResponse(UserBlockBase):
    """Schema for blocked user response."""
    id: str
    blocker_id: str
    blocked_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatUserResponse(BaseModel):
    """Schema for user information in chat context."""
    id: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_picture: Optional[str] = None
    last_seen: Optional[datetime] = None
    
    class Config:
        from_attributes = True
