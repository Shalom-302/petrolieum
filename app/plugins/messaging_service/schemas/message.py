"""
Message Schemas

This module defines Pydantic schemas for message validation and serialization.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import uuid


class AttachmentBase(BaseModel):
    """Base schema for message attachments."""
    file_name: str
    file_type: str
    file_size: int
    is_image: bool = False


class AttachmentCreate(AttachmentBase):
    """Schema for creating a new attachment."""
    pass


class AttachmentResponse(AttachmentBase):
    """Schema for attachment response."""
    id: str
    message_id: str
    file_path: str
    thumbnail_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    """Base schema for messages."""
    message_type: str = Field(..., description="Type of message: text, image, file, audio, video, location, contact, system")
    content: Optional[str] = Field(None, description="Content of the message, may be encrypted")
    message_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata based on message type")
    reply_to_message_id: Optional[str] = None


class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    conversation_id: str


class MessageUpdate(BaseModel):
    """Schema for updating a message."""
    content: Optional[str] = None
    is_deleted: Optional[bool] = None


class MessageReaction(BaseModel):
    """Schema for message reactions."""
    reaction: str = Field(..., description="Emoji reaction code")


class MessageReactionResponse(MessageReaction):
    """Schema for message reaction response."""
    id: str
    message_id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageReceiptResponse(BaseModel):
    """Schema for message receipt response."""
    id: str
    message_id: str
    user_id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(MessageBase):
    """Schema for message response."""
    id: str
    conversation_id: str
    sender_id: str
    is_encrypted: bool
    is_edited: bool
    is_deleted: bool
    is_forwarded: bool
    original_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    attachments: List[AttachmentResponse] = []
    receipts: Optional[List[MessageReceiptResponse]] = None
    reactions: Optional[List[MessageReactionResponse]] = None
    status: str = "sent"

    class Config:
        from_attributes = True


class BulkMessagesRequest(BaseModel):
    """Schema for retrieving multiple messages."""
    conversation_id: str
    limit: int = 50
    before_message_id: Optional[str] = None
    after_message_id: Optional[str] = None


class MessageSearchRequest(BaseModel):
    """Schema for searching messages."""
    query: str
    conversation_id: Optional[str] = None
    sender_id: Optional[str] = None
    message_type: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class ForwardMessageRequest(BaseModel):
    """Schema for forwarding a message."""
    message_id: str
    target_conversation_ids: List[str]
    additional_content: Optional[str] = None


class BulkDeleteMessagesRequest(BaseModel):
    """Schema for bulk deleting messages."""
    message_ids: List[str]
    delete_for_everyone: bool = False


class MessageStatusUpdateRequest(BaseModel):
    """Schema for updating message status."""
    message_ids: List[str]
    status: str = Field(..., description="Status: delivered or read")
