"""
Message Models

This module defines database models for messages, including direct messages,
group messages, and message attachments.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime
from typing import List, Optional

from app.core.db import Base


class MessageType(enum.Enum):
    """Enum for message types."""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    CONTACT = "contact"
    SYSTEM = "system"


class MessageStatusType(enum.Enum):
    """Enum for message delivery status."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageDB(Base):
    """Database model for messages."""
    __tablename__ = "messaging_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("messaging_conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(String(36), nullable=False, index=True)
    message_type = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)  # Encrypted content for privacy
    message_metadata = Column(JSON, nullable=True)  # For additional data based on message type
    is_encrypted = Column(Boolean, default=True)
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_forwarded = Column(Boolean, default=False)
    original_message_id = Column(String(36), nullable=True)  # For forwarded messages
    reply_to_message_id = Column(String(36), ForeignKey("messaging_messages.id"), nullable=True)  # For reply messages
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversation = relationship("ConversationDB", back_populates="messages")
    attachments = relationship("MessageAttachmentDB", back_populates="message", cascade="all, delete-orphan")
    receipts = relationship("MessageReceiptDB", back_populates="message", cascade="all, delete-orphan")
    reactions = relationship("MessageReactionDB", back_populates="message", cascade="all, delete-orphan")
    delivery_statuses = relationship("MessageDeliveryStatusDB", back_populates="message", cascade="all, delete-orphan")
    reply_to = relationship("MessageDB", remote_side=[id], foreign_keys=[reply_to_message_id], backref="replies")
    
    def __repr__(self):
        return f"<Message {self.id} in conversation {self.conversation_id}>"


class MessageAttachmentDB(Base):
    """Database model for message attachments."""
    __tablename__ = "messaging_attachments"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("messaging_messages.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(512), nullable=False)  # Path to file in storage
    is_image = Column(Boolean, default=False)
    thumbnail_path = Column(String(512), nullable=True)  # For image/video previews
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    message = relationship("MessageDB", back_populates="attachments")
    
    def __repr__(self):
        return f"<Attachment {self.id} for message {self.message_id}>"


class MessageReceiptDB(Base):
    """Database model for message delivery and read receipts."""
    __tablename__ = "messaging_receipts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("messaging_messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    status = Column(String(20), nullable=False)  # 'delivered' or 'read'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    message = relationship("MessageDB", back_populates="receipts")
    
    def __repr__(self):
        return f"<Receipt {self.id} for message {self.message_id} by user {self.user_id}>"


class MessageReactionDB(Base):
    """Database model for message reactions (emoji responses)."""
    __tablename__ = "messaging_reactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("messaging_messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    reaction = Column(String(20), nullable=False)  # emoji code
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    message = relationship("MessageDB", back_populates="reactions")
    
    def __repr__(self):
        return f"<Reaction {self.id} for message {self.message_id} by user {self.user_id}>"
