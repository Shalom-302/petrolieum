"""
User model for the advanced authentication plugin.
"""
from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime, JSON, Table, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.core.db import Base

# Association table for user-groups
user_group = Table(
    "user_group",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True),
    Column("group_id", UUID(as_uuid=True), ForeignKey("auth_group.id"), primary_key=True)
)

class User(Base):
    """
    User model with enhanced security and authentication features.
    """
    __tablename__ = "user"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Nullable for OAuth-only users
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    
    # Security and audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Profile and preferences
    profile_picture = Column(String, nullable=True)
    locale = Column(String(10), default="en-US")
    timezone = Column(String(50), default="UTC")
    
    # Authentication and provider data
    primary_auth_provider = Column(String(50), default="email")
    auth_provider_data = Column(JSON, nullable=True)
    
    # Personal data (potentially sensitive, should be encrypted)
    phone_number = Column(String, nullable=True)
    ssn = Column(String, nullable=True)  # Social Security Number
    date_of_birth = Column(DateTime, nullable=True)
    
    # Token management
    refresh_token = Column(String, nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)
    
    # Role for permission management
    role_id = Column(UUID(as_uuid=True), ForeignKey("auth_role.id"), nullable=False)
    role = relationship("Role", back_populates="users")
    
    # Many-to-many relationship with groups
    groups = relationship("Group", secondary=user_group, back_populates="users")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization")
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    access_tokens = relationship("AccessToken", back_populates="user", cascade="all, delete-orphan")
    mfa_methods = relationship("MFAMethod", back_populates="user", cascade="all, delete-orphan")
    push_subscriptions = relationship("PushSubscription", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.username} ({self.id})>"
