"""
Conversation Models

This module defines database models for conversations, including direct conversations
and group chats.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime
from typing import List, Optional

from app.core.db import Base


# Association table for conversation participants
conversation_participants = Table(
    "messaging_conversation_participants",
    Base.metadata,
    Column("conversation_id", String(36), ForeignKey("messaging_conversations.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(36), primary_key=True),
    Column("role", String(20), default="member"),  # 'member', 'admin', 'owner'
    Column("joined_at", DateTime, default=datetime.utcnow),
    Column("is_active", Boolean, default=True)
)


class ConversationType(enum.Enum):
    """Enum for conversation types."""
    DIRECT = "direct"   # One-to-one conversation
    GROUP = "group"     # Group conversation
    BROADCAST = "broadcast"  # One-to-many broadcast


class ConversationDB(Base):
    """Database model for conversations."""
    __tablename__ = "messaging_conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_type = Column(String(20), nullable=False)
    title = Column(String(255), nullable=True)  # For group chats
    avatar_url = Column(String(512), nullable=True)  # For group chats
    created_by = Column(String(36), nullable=False)
    is_encrypted = Column(Boolean, default=True)
    conversation_metadata = Column(JSON, nullable=True)  # For additional settings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)
    
    # Relationships
    messages = relationship("MessageDB", back_populates="conversation", cascade="all, delete-orphan")
    participants = relationship("UserConversationSettingsDB", back_populates="conversation", cascade="all, delete-orphan")
    group_settings = relationship("GroupChatDB", back_populates="conversation", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation {self.id} of type {self.conversation_type}>"


class UserConversationSettingsDB(Base):
    """Database model for user-specific conversation settings."""
    __tablename__ = "messaging_user_conversation_settings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    conversation_id = Column(String(36), ForeignKey("messaging_conversations.id", ondelete="CASCADE"), nullable=False)
    is_muted = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)  # Flag pour le soft delete
    custom_name = Column(String(255), nullable=True)  # For user to rename conversations
    theme_color = Column(String(20), nullable=True)  # For chat theme
    notification_level = Column(String(20), default="all")  # 'all', 'mentions', 'none'
    last_read_message_id = Column(String(36), nullable=True)
    unread_count = Column(Integer, default=0)  # Nombre de messages non lus
    role = Column(String(20), default="member")  # 'member', 'admin', 'owner'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversation = relationship("ConversationDB", back_populates="participants")
    
    def __repr__(self):
        return f"<UserConversationSettings for user {self.user_id} in conversation {self.conversation_id}>"


class GroupChatDB(Base):
    """Database model for group chat additional settings."""
    __tablename__ = "messaging_group_settings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("messaging_conversations.id", ondelete="CASCADE"), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    max_participants = Column(Integer, default=100)
    is_public = Column(Boolean, default=False)
    join_mode = Column(String(20), default="invite_only")  # 'invite_only', 'approval', 'open'
    message_permission = Column(String(20), default="all_members")  # 'all_members', 'admins_only'
    who_can_invite = Column(String(20), default="admins")  # 'admins', 'all_members'
    who_can_remove = Column(String(20), default="admins")  # 'admins', 'all_members'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    conversation = relationship("ConversationDB", back_populates="group_settings")
    
    def __repr__(self):
        return f"<GroupChat settings for conversation {self.conversation_id}>"


# Blocking model for users who block others
class UserBlockDB(Base):
    """Database model for blocked users."""
    __tablename__ = "messaging_user_blocks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    blocker_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    blocked_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserBlock {self.id} - {self.blocker_id} blocked {self.blocked_id}>"
