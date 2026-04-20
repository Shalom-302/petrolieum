"""
Validation schemas for the privacy compliance plugin
"""

from pydantic import BaseModel, Field, EmailStr, validator, HttpUrl, UUID4
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum
import uuid


class DataRequestType(str, Enum):
    """Types of GDPR data requests"""
    ACCESS = "access"      # Request for data access
    DELETION = "deletion"  # Request for data deletion
    CORRECTION = "correction"  # Request for data correction
    PORTABILITY = "portability"  # Request for data portability


class DataRequestStatus(str, Enum):
    """Statuses of GDPR data requests"""
    PENDING = "pending"        # Pending processing
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"    # Processing completed
    REJECTED = "rejected"      # Request rejected
    EXPIRED = "expired"        # Request expired


class ConsentType(str, Enum):
    """Types of consent"""
    COOKIE = "cookie"           # Cookie consent
    MARKETING = "marketing"     # Marketing consent
    THIRD_PARTY = "third_party" # Third-party consent
    TERMS = "terms"             # Terms of service acceptance
    PRIVACY = "privacy"         # Privacy policy acceptance


class CookieCategoryBase(BaseModel):
    """Base schema for cookie categories"""
    name: str = Field(..., description="Category name", example="Marketing")
    description: str = Field(..., description="Category description", 
                           example="These cookies enable us to deliver personalized advertisements")
    is_necessary: bool = Field(False, description="Whether the category is necessary for site functionality")


class CookieCategoryCreate(CookieCategoryBase):
    """Schema for creating a cookie category"""
    pass


class CookieCategoryRead(CookieCategoryBase):
    """Schema for reading a cookie category"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CookieBase(BaseModel):
    """Base schema for cookies"""
    name: str = Field(..., description="Cookie name", example="_ga")
    domain: str = Field(..., description="Cookie domain", example=".example.com")
    purpose: str = Field(..., description="Cookie purpose", 
                       example="Used by Google Analytics to distinguish users")
    duration: str = Field(..., description="Cookie lifetime", example="2 years")
    provider: Optional[str] = Field(None, description="Cookie provider", example="Google Analytics")
    category_id: int = Field(..., description="Cookie category ID")


class CookieCreate(CookieBase):
    """Schema for creating a cookie"""
    pass


class CookieRead(CookieBase):
    """Schema for reading a cookie"""
    id: int
    created_at: datetime
    updated_at: datetime
    category: CookieCategoryRead
    
    class Config:
        from_attributes = True


class CookieSettingsBase(BaseModel):
    """Base schema for cookie consent configuration"""
    consent_expiry_days: int = Field(180, description="Consent validity period in days")
    block_until_consent: bool = Field(False, description="Block page loading until consent is given")


class CookieSettingsUpdate(BaseModel):
    """Schema for updating cookie consent configuration"""
    consent_expiry_days: Optional[int] = None
    block_until_consent: Optional[bool] = None


class CookieSettingsRead(CookieSettingsBase):
    """Schema for reading cookie consent configuration"""
    id: int
    created_at: datetime
    updated_at: datetime
    categories: List[CookieCategoryRead]
    
    class Config:
        from_attributes = True


class UserConsentBase(BaseModel):
    """Base schema for user consent"""
    consent_type: ConsentType
    consent_details: Optional[Dict[str, Any]] = None
    ip_address: str
    user_agent: str


class UserConsentCreate(UserConsentBase):
    """Schema for creating user consent"""
    user_id: Optional[UUID4] = None


class UserConsentRead(UserConsentBase):
    """Schema for reading user consent"""
    id: int
    user_id: Optional[UUID4]
    consented_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class CookieConsentSubmit(BaseModel):
    """Schema for submitting cookie consent"""
    necessary: bool = True
    preferences: bool = False
    statistics: bool = False
    marketing: bool = False
    accept_all: bool = False
    reject_all: bool = False


class DataRequestBase(BaseModel):
    """Base schema for GDPR data requests"""
    email: EmailStr = Field(..., description="Email of the person making the request")
    request_type: DataRequestType
    request_details: Optional[str] = Field(None, description="Additional request details")


class DataRequestCreate(DataRequestBase):
    """Schema for creating a GDPR data request"""
    pass


class DataRequestUpdate(BaseModel):
    """Schema for updating a GDPR data request"""
    status: Optional[DataRequestStatus] = None
    verification_token: Optional[str] = None
    verification_expires: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DataRequestRead(DataRequestBase):
    """Schema for reading a GDPR data request"""
    id: int
    user_id: Optional[UUID4]
    status: DataRequestStatus
    created_at: datetime
    updated_at: datetime
    verified_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ExportedDataBase(BaseModel):
    """Base schema for exported data"""
    data_request_id: int
    file_path: Optional[str] = None
    expires_at: datetime


class ExportedDataCreate(ExportedDataBase):
    """Schema for creating exported data"""
    data_content: Optional[str] = None
    encryption_key: Optional[str] = None


class ExportedDataRead(ExportedDataBase):
    """Schema for reading exported data"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class DataProcessingRecordBase(BaseModel):
    """Base schema for processing records"""
    activity_name: str
    purpose: str
    data_categories: List[str]
    data_subjects: List[str]
    recipients: Optional[List[str]] = None
    transfers: Optional[List[Dict[str, str]]] = None
    retention_period: str
    security_measures: List[str]
    legal_basis: str


class DataProcessingRecordCreate(DataProcessingRecordBase):
    """Schema for creating a processing record"""
    pass


class DataProcessingRecordRead(DataProcessingRecordBase):
    """Schema for reading a processing record"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PrivacyPolicyBase(BaseModel):
    """Base schema for privacy policies"""
    version: str
    content: str
    is_active: bool = False


class PrivacyPolicyCreate(PrivacyPolicyBase):
    """Schema for creating a privacy policy"""
    created_by: Optional[int] = None


class PrivacyPolicyRead(PrivacyPolicyBase):
    """Schema for reading a privacy policy"""
    id: int
    created_at: datetime
    activated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AnonymizationRequest(BaseModel):
    """Schema for an anonymization request"""
    entity_type: str = Field(..., description="Type of entity to anonymize", example="user")
    entity_id: int = Field(..., description="ID of the entity to anonymize")
    fields: List[str] = Field(..., description="Fields to anonymize", example=["email", "phone", "address"])
    method: str = Field("pseudonymize", description="Anonymization method", 
                       example="pseudonymize, hash, redact, generalize")
    reason: Optional[str] = Field(None, description="Reason for anonymization", 
                                example="GDPR deletion request")


class AnonymizationLogRead(BaseModel):
    """Schema for reading an anonymization log"""
    id: int
    entity_type: str
    entity_id: int
    fields_anonymized: List[str]
    anonymization_method: str
    reason: Optional[str]
    performed_by: Optional[int]
    performed_at: datetime
    
    class Config:
        from_attributes = True
