"""
Multi-factor authentication models for the advanced authentication plugin.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum, Integer, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import enum

from app.core.db import Base

class MFAMethodType(enum.Enum):
    """Types of MFA methods supported."""
    TOTP = "totp"  # Time-based One-Time Password
    SMS = "sms"    # SMS verification
    EMAIL = "email"  # Email verification
    BACKUP_CODES = "backup_codes"  # Backup recovery codes
    PUSH = "push"  # Push notification to mobile device
    HARDWARE_TOKEN = "hardware_token"  # Hardware security keys (like YubiKey)


class MFAMethod(Base):
    """
    MFA methods configured for a user.
    """
    __tablename__ = "auth_mfa_method"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    method_type = Column(Enum(MFAMethodType), nullable=False)
    name = Column(String(100), nullable=True)
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Method-specific data (encrypted secret for TOTP, masked phone for SMS, etc.)
    secret = Column(String, nullable=True)
    data = Column(JSON, nullable=True)  # Changed from JSONB to standard JSON for compatibility
    
    # Audit information
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="mfa_methods")
    
    def __repr__(self):
        return f"<MFAMethod {self.method_type.value} for {self.user_id}>"


class VerificationCode(Base):
    """
    Temporary verification codes for password reset, account verification, etc.
    """
    __tablename__ = "auth_verification_code"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    code = Column(String(64), nullable=False)
    purpose = Column(String(50), nullable=False)  # verification, password_reset, login, etc.
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<VerificationCode {self.purpose} for {self.user_id}>"
