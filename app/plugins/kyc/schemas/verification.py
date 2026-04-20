"""
Schemas for KYC verification processes.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, validator, EmailStr, constr
from enum import Enum

from ..models.verification import VerificationStatus, VerificationType, IdentityDocument, RiskLevel


# Enums as string literals for API schemas
class VerificationStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FRAUD_SUSPECTED = "fraud_suspected"
    ADDITIONAL_INFO_NEEDED = "additional_info_needed"


class VerificationTypeEnum(str, Enum):
    BASIC = "basic"
    STANDARD = "standard"
    ENHANCED = "enhanced"
    SIMPLIFIED = "simplified"
    BUSINESS = "business"
    ONGOING = "ongoing"


class IdentityDocumentEnum(str, Enum):
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
    THIRD_PARTY_REFERENCE = "third_party_reference"


class RiskLevelEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentSubmission(BaseModel):
    """Schema for document submission."""
    document_type: IdentityDocumentEnum
    document_id: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    document_data: Optional[Dict[str, Any]] = None
    is_verified: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "national_id",
                "document_id": "ABC123456",
                "issue_date": "2020-01-01",
                "expiry_date": "2030-01-01",
                "issuing_authority": "National ID Authority",
                "document_data": {"front_image_url": "url_to_image", "back_image_url": "url_to_image"},
                "is_verified": False
            }
        }


class ThirdPartyReference(BaseModel):
    """Schema for third-party reference used in simplified KYC."""
    reference_type: str = Field(..., description="Type of reference (e.g., community leader, bank officer)")
    reference_name: str = Field(..., description="Name of the reference person")
    reference_id: Optional[str] = None
    reference_contact: str = Field(..., description="Contact information for the reference")
    relationship: str = Field(..., description="Relationship to the applicant")
    verification_notes: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "reference_type": "community_leader",
                "reference_name": "John Doe",
                "reference_id": "CL123456",
                "reference_contact": "+1234567890",
                "relationship": "Village Chief",
                "verification_notes": "Confirmed identity via phone call"
            }
        }


class VerificationCreate(BaseModel):
    """Schema for creating a KYC verification."""
    user_id: str = Field(..., description="ID of the user being verified")
    verification_type: VerificationTypeEnum = Field(..., description="Type of verification to perform")
    submitted_data: Optional[Dict[str, Any]] = Field(None, description="User submitted data for verification")
    documents_provided: Optional[List[DocumentSubmission]] = None
    third_party_references: Optional[List[ThirdPartyReference]] = None
    region_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_encrypted: bool = True
    
    @validator('submitted_data')
    def validate_submitted_data(cls, v, values):
        """Validate that appropriate data is submitted based on verification type."""
        if not v:
            return v
            
        verification_type = values.get('verification_type')
        
        # Simplified KYC requires at least basic personal information
        if verification_type == VerificationTypeEnum.SIMPLIFIED:
            if not v.get('full_name') or not v.get('contact_information'):
                raise ValueError("Simplified KYC requires at least full name and contact information")
        
        # Enhanced KYC requires more detailed information
        if verification_type == VerificationTypeEnum.ENHANCED:
            required_fields = ['full_name', 'date_of_birth', 'address', 'nationality']
            missing = [f for f in required_fields if f not in v]
            if missing:
                raise ValueError(f"Enhanced KYC missing required fields: {', '.join(missing)}")
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "verification_type": "standard",
                "submitted_data": {
                    "full_name": "John Doe",
                    "date_of_birth": "1990-01-01",
                    "nationality": "US",
                    "address": {
                        "street": "123 Main St",
                        "city": "Anytown",
                        "country": "US",
                        "postal_code": "12345"
                    }
                },
                "documents_provided": [
                    {
                        "document_type": "passport",
                        "document_id": "P123456",
                        "issue_date": "2015-01-01",
                        "expiry_date": "2025-01-01",
                        "issuing_authority": "US State Department"
                    }
                ],
                "region_id": "region123",
                "is_encrypted": True
            }
        }


class VerificationUpdate(BaseModel):
    """Schema for updating a KYC verification."""
    status: Optional[VerificationStatusEnum] = None
    verification_result: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    review_notes: Optional[str] = None
    risk_level: Optional[RiskLevelEnum] = None
    risk_factors: Optional[Dict[str, Any]] = None
    documents_provided: Optional[List[DocumentSubmission]] = None
    third_party_references: Optional[List[ThirdPartyReference]] = None
    reviewed_by: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "approved",
                "verification_result": {
                    "identity_match": True,
                    "document_authenticity": True,
                    "verification_score": 0.95
                },
                "risk_level": "low",
                "review_notes": "All documents verified successfully"
            }
        }


class VerificationResponse(BaseModel):
    """Schema for KYC verification response."""
    id: str
    user_id: str
    verification_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    risk_level: str
    verification_method: Optional[str] = None
    is_encrypted: bool
    
    # Only include non-sensitive data in the response
    documents_count: Optional[int] = None
    region_name: Optional[str] = None
    simplified_kyc: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "ver123",
                "user_id": "user123",
                "verification_type": "standard",
                "status": "approved",
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-02T14:30:00",
                "expires_at": "2024-01-01T12:00:00",
                "risk_level": "low",
                "verification_method": "document_verification",
                "is_encrypted": True,
                "documents_count": 2,
                "region_name": "North America",
                "simplified_kyc": False
            }
        }


class VerificationList(BaseModel):
    """Schema for list of KYC verifications."""
    items: List[VerificationResponse]
    total: int
    page: int
    size: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "ver123",
                        "user_id": "user123",
                        "verification_type": "standard",
                        "status": "approved",
                        "created_at": "2023-01-01T12:00:00",
                        "updated_at": "2023-01-02T14:30:00",
                        "expires_at": "2024-01-01T12:00:00",
                        "risk_level": "low",
                        "verification_method": "document_verification",
                        "is_encrypted": True,
                        "documents_count": 2,
                        "region_name": "North America",
                        "simplified_kyc": False
                    }
                ],
                "total": 1,
                "page": 1,
                "size": 10
            }
        }
