"""
User profile models for KYC processes.
"""

import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Enum, Boolean, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.core.db import Base
from app.core.utils import generate_uuid


class ProfileStatus(str, enum.Enum):
    """Status of a KYC user profile."""
    DRAFT = "draft"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    BLACKLISTED = "blacklisted"


class KycUserProfileDB(Base):
    """KYC user profile containing identity details."""
    
    __tablename__ = "kyc_user_profiles"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=False, unique=True, index=True)
    
    # Status and timestamps
    status = Column(Enum(ProfileStatus), default=ProfileStatus.DRAFT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Basic personal information (encrypted)
    full_name = Column(String, nullable=True)
    date_of_birth = Column(String, nullable=True)  # Stored as string for encryption
    nationality = Column(String, nullable=True)
    address = Column(JSON, nullable=True)
    phone_number = Column(String, nullable=True)
    email = Column(String, nullable=True)
    
    # Advanced fields
    tax_id = Column(String, nullable=True)
    occupation = Column(String, nullable=True)
    employer = Column(String, nullable=True)
    source_of_funds = Column(String, nullable=True)
    politically_exposed = Column(Boolean, default=False, nullable=True)
    
    # Security fields
    is_encrypted = Column(Boolean, default=True, nullable=False)
    encryption_metadata = Column(JSON, nullable=True)
    last_verified_at = Column(DateTime, nullable=True)
    
    # Region-specific information
    region_id = Column(String, ForeignKey("kyc_regions.id"), nullable=True)
    region = relationship("KycRegionDB", back_populates="profiles")
    
    # Relationships
    verifications = relationship("KycVerificationDB", back_populates="profile", cascade="all, delete-orphan")
    
    # Audit trail
    audit_log = Column(JSON, nullable=True)  # Log of all changes
    
    # References (for simplified KYC)
    references = Column(JSON, nullable=True)  # List of trusted references for simplified KYC
