"""
Data templates for the privacy compliance plugin
"""

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from enum import Enum as PyEnum
import uuid

from app.core.db import Base


class DataRequestType(PyEnum):
    """Types of data requests under GDPR"""
    ACCESS = "access"      # Request for access to data
    DELETION = "deletion"  # Request for deletion of data
    CORRECTION = "correction"  # Request for correction
    PORTABILITY = "portability"  # Request for portability


class DataRequestStatus(PyEnum):
    """Status of data requests under GDPR"""
    PENDING = "pending"        # Pending processing
    PROCESSING = "processing"  # Processing in progress
    COMPLETED = "completed"    # Processing completed
    REJECTED = "rejected"      # Request rejected
    EXPIRED = "expired"        # Request expired


class ConsentType(PyEnum):
    """Types of consent under GDPR"""
    COOKIE = "cookie"           # Consent to cookies
    MARKETING = "marketing"     # Consent to marketing
    THIRD_PARTY = "third_party" # Consent to third-party
    TERMS = "terms"             # Acceptance of terms of use
    PRIVACY = "privacy"         # Acceptance of privacy policy


# Table association for cookie categories and their parameters
cookie_category_settings = Table(
    "privacy_cookie_category_settings",
    Base.metadata,
    Column("settings_id", Integer, ForeignKey("privacy_cookie_settings.id")),
    Column("category_id", Integer, ForeignKey("privacy_cookie_categories.id"))
)


class CookieCategory(Base):
    """Cookie categories (necessary, preferences, statistics, marketing)"""
    __tablename__ = "privacy_cookie_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    is_necessary = Column(Boolean, default=False)  # Cookies necessary cannot be rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation with cookie parameters
    cookies = relationship("Cookie", back_populates="category")


class Cookie(Base):
    """Detailed information on each cookie used by the application"""
    __tablename__ = "privacy_cookies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False)
    purpose = Column(Text, nullable=False)
    duration = Column(String(50), nullable=False)  # ex: "1 day", "session", "1 year"
    provider = Column(String(255), nullable=True)  # ex: "Google Analytics"
    category_id = Column(Integer, ForeignKey("privacy_cookie_categories.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation with category
    category = relationship("CookieCategory", back_populates="cookies")


class CookieSettings(Base):
    """Cookie consent configuration and default settings"""
    __tablename__ = "privacy_cookie_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    consent_expiry_days = Column(Integer, default=180)  # Consent valid for 6 months by default
    block_until_consent = Column(Boolean, default=False)  # Whether to block content until consent is given
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation with cookie categories
    categories = relationship(
        "CookieCategory", 
        secondary=cookie_category_settings,
        backref="settings"
    )


class UserConsent(Base):
    """User consent registration"""
    __tablename__ = "privacy_user_consents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)  # Null for non-logged-in user
    consent_type = Column(String(50), nullable=False)  # Ex: "cookie", "marketing", "terms"
    consent_details = Column(Text, nullable=True)  # JSON with consent details
    ip_address = Column(String(50), nullable=False)
    user_agent = Column(String(255), nullable=False)
    consented_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    
    # Reference to the user if logged in
    user = relationship("User", backref="consents", primaryjoin="UserConsent.user_id == User.id")


class DataRequest(Base):
    """Data requests under GDPR"""
    __tablename__ = "privacy_data_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)  # Null for email requests
    email = Column(String(255), nullable=False)
    request_type = Column(String(20), nullable=False)  # Utilise DataRequestType
    request_details = Column(Text, nullable=True)
    verification_token = Column(String(255), nullable=True)
    verification_expires = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default=DataRequestStatus.PENDING.value)
    request_ip = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Reference to the user if logged in
    user = relationship("User", backref="data_requests", primaryjoin="DataRequest.user_id == User.id")
    
    # Relation with exported data
    exported_data = relationship("ExportedData", back_populates="data_request", uselist=False)


class ExportedData(Base):
    """Exported data after a GDPR access request"""
    __tablename__ = "privacy_exported_data"
    
    id = Column(Integer, primary_key=True, index=True)
    data_request_id = Column(Integer, ForeignKey("privacy_data_requests.id"), nullable=False)
    data_content = Column(Text, nullable=True)  # JSON containing the data or null if encrypted
    file_path = Column(String(255), nullable=True)  # Path to the exported file
    encryption_key = Column(String(255), nullable=True)  # Encryption key if applicable
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # Download link expiration date
    
    # Relation with the request
    data_request = relationship("DataRequest", back_populates="exported_data")


class DataProcessingRecord(Base):
    """Data processing record (required by Article 30 of the GDPR)"""
    __tablename__ = "privacy_data_processing_records"
    
    id = Column(Integer, primary_key=True, index=True)
    activity_name = Column(String(255), nullable=False)
    purpose = Column(Text, nullable=False)
    data_categories = Column(Text, nullable=False)  # JSON with data categories
    data_subjects = Column(Text, nullable=False)  # JSON with categories of persons concerned
    recipients = Column(Text, nullable=True)  # JSON with data recipients
    transfers = Column(Text, nullable=True)  # JSON with transfers outside the EU
    retention_period = Column(String(255), nullable=False)
    security_measures = Column(Text, nullable=False)
    legal_basis = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrivacyPolicy(Base):
    """Privacy policy versions"""
    __tablename__ = "privacy_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    
    # Reference to the user who created the version
    creator = relationship("User", backref="privacy_policies", primaryjoin="PrivacyPolicy.created_by == User.id")


class AnonymizationLog(Base):
    """Anonymization log"""
    __tablename__ = "privacy_anonymization_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)  # Ex: "user", "order", "comment"
    entity_id = Column(Integer, nullable=False)
    fields_anonymized = Column(Text, nullable=False)  # JSON with anonymized fields
    anonymization_method = Column(String(50), nullable=False)  # "hash", "pseudonymize", "redact", etc.
    reason = Column(String(255), nullable=True)
    performed_by = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    performed_at = Column(DateTime, default=datetime.utcnow)
    
    # Reference to the user who performed the anonymization
    performer = relationship("User", backref="anonymization_logs", primaryjoin="AnonymizationLog.performed_by == User.id")
