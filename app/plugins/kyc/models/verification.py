"""
Verification models for KYC processes.
"""

import enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, DateTime, Enum, Boolean, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship

from app.core.db import Base
from app.core.utils import generate_uuid


class VerificationStatus(str, enum.Enum):
    """Status of a KYC verification process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FRAUD_SUSPECTED = "fraud_suspected"
    ADDITIONAL_INFO_NEEDED = "additional_info_needed"


class VerificationType(str, enum.Enum):
    """Type of KYC verification."""
    BASIC = "basic"                     # Basic verification (name, DOB, address)
    STANDARD = "standard"               # Standard verification (ID document)
    ENHANCED = "enhanced"               # Enhanced verification (multiple documents, facial recognition)
    SIMPLIFIED = "simplified"           # Simplified for regions with low infrastructure
    BUSINESS = "business"               # Business entity verification
    ONGOING = "ongoing"                 # Ongoing monitoring
    

class IdentityDocument(str, enum.Enum):
    """Types of identity documents accepted."""
    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    DRIVERS_LICENSE = "drivers_license"
    VOTER_ID = "voter_id"
    RESIDENCE_PERMIT = "residence_permit"
    UTILITY_BILL = "utility_bill"
    TAX_ID = "tax_id"
    BIRTH_CERTIFICATE = "birth_certificate"
    MOBILE_VERIFICATION = "mobile_verification"
    BIOMETRIC = "biometric"
    THIRD_PARTY_REFERENCE = "third_party_reference"  # For simplified KYC


class RiskLevel(str, enum.Enum):
    """Risk level assigned to a verification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class KycVerificationDB(Base):
    """KYC verification record."""
    
    __tablename__ = "kyc_verifications"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)
    verification_type = Column(Enum(VerificationType), nullable=False)
    status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    # Verification details
    submitted_data = Column(JSON, nullable=True)  # Encrypted user-submitted data
    verification_result = Column(JSON, nullable=True)  # Results of verification
    rejection_reason = Column(Text, nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # Risk assessment
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.MEDIUM, nullable=False)
    risk_factors = Column(JSON, nullable=True)
    
    # Verification method details
    documents_provided = Column(JSON, nullable=True)  # List of document types
    verification_method = Column(String, nullable=True)  # Method used (API, manual, etc.)
    verification_provider = Column(String, nullable=True)  # Third-party provider if applicable
    
    # Security
    is_encrypted = Column(Boolean, default=True, nullable=False)
    encryption_metadata = Column(JSON, nullable=True)
    
    # User profile relationship
    profile_id = Column(String, ForeignKey("kyc_user_profiles.id"), nullable=True)
    profile = relationship("KycUserProfileDB", back_populates="verifications")
    
    # Region-specific information
    region_id = Column(String, ForeignKey("kyc_regions.id"), nullable=True)
    region = relationship("KycRegionDB", back_populates="verifications")
    
    # Admin action tracking
    reviewed_by = Column(String, nullable=True)  # Admin who reviewed
    review_date = Column(DateTime, nullable=True)
    
    # Audit trail
    audit_log = Column(JSON, nullable=True)  # Log of all status changes and actions
