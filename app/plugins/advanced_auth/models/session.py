"""
Session and token models for the advanced authentication plugin.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.core.db import Base

class Session(Base):
    """
    User session model for tracking active sessions.
    """
    __tablename__ = "auth_session"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    refresh_token = Column(String, unique=True, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    refresh_token_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Device and location information
    device_type = Column(String(50), nullable=True)
    device_name = Column(String(100), nullable=True)
    browser = Column(String(100), nullable=True)
    browser_version = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)
    os_version = Column(String(50), nullable=True)
    ip_address = Column(String(50), nullable=True)  # Changed from INET to String for compatibility
    location = Column(String(100), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<Session {self.id} ({self.user_id})>"


class AccessToken(Base):
    """
    Access token model for OAuth clients and API access.
    """
    __tablename__ = "auth_access_token"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    scope = Column(String, nullable=True)
    client_id = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="access_tokens")
    
    def __repr__(self):
        return f"<AccessToken {self.id} ({self.user_id})>"
