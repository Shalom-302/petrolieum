"""
Region models for KYC processes.
"""

import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Enum, Boolean, JSON, Integer, Text
from sqlalchemy.orm import relationship

from app.core.db import Base
from app.core.utils import generate_uuid


class InfrastructureLevel(str, enum.Enum):
    """Infrastructure level of a region affecting KYC requirements."""
    HIGH = "high"             # High infrastructure (developed countries)
    MEDIUM = "medium"         # Medium infrastructure (developing countries with good digital presence)
    LOW = "low"               # Low infrastructure (regions with limited digital/banking infrastructure)
    VERY_LOW = "very_low"     # Very low infrastructure (regions with minimal digital access)


class KycRegionDB(Base):
    """Region configuration for KYC processes."""
    
    __tablename__ = "kyc_regions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False, unique=True, index=True)
    country_code = Column(String(2), nullable=False, index=True)
    
    # Infrastructure details
    infrastructure_level = Column(Enum(InfrastructureLevel), nullable=False)
    
    # Created and updated timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Verification requirements
    required_documents = Column(JSON, nullable=False)  # List of required document types by verification type
    alternative_documents = Column(JSON, nullable=True)  # Alternative documents when standard ones unavailable
    simplified_kyc_threshold = Column(Integer, nullable=True)  # Transaction amount threshold for simplified KYC
    
    # Region-specific rules
    regulatory_requirements = Column(Text, nullable=True)  # Description of local regulations
    risk_assessment_rules = Column(JSON, nullable=True)  # Region-specific risk assessment configurations
    verification_expiry_days = Column(Integer, default=365, nullable=False)  # Days until verification expires
    
    # Relationships
    verifications = relationship("KycVerificationDB", back_populates="region")
    profiles = relationship("KycUserProfileDB", back_populates="region")
    
    # Simplified KYC settings
    simplified_kyc_enabled = Column(Boolean, default=False, nullable=False)
    simplified_requirements = Column(JSON, nullable=True)  # Custom requirements for simplified process
    trusted_referee_types = Column(JSON, nullable=True)  # Types of accepted third-party referees
    
    # Documentation & display
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
