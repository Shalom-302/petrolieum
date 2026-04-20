"""
Schemas for KYC user profiles.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, validator, EmailStr, constr
from enum import Enum

from ..models.user_profile import ProfileStatus


class ProfileStatusEnum(str, Enum):
    """Status of a KYC user profile."""
    DRAFT = "draft"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    BLACKLISTED = "blacklisted"


class AddressSchema(BaseModel):
    """Schema for address information."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    postal_code: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "street": "123 Main St",
                "city": "Anytown",
                "state": "State",
                "country": "US",
                "postal_code": "12345"
            }
        }


class ReferenceCreate(BaseModel):
    """Schema for creating a trusted reference for simplified KYC."""
    reference_type: str = Field(..., description="Type of reference (e.g., community leader, bank officer)")
    full_name: str = Field(..., description="Full name of the reference")
    contact_info: str = Field(..., description="Contact information (phone or email)")
    position: Optional[str] = Field(None, description="Position or role of the reference")
    organization: Optional[str] = Field(None, description="Organization the reference belongs to")
    verification_method: str = Field(..., description="How the reference was verified")
    relationship: str = Field(..., description="Relationship to the applicant")
    
    class Config:
        json_schema_extra = {
            "example": {
                "reference_type": "community_leader",
                "full_name": "John Doe",
                "contact_info": "+1234567890",
                "position": "Village Elder",
                "organization": "Local Community Council",
                "verification_method": "phone_verification",
                "relationship": "Community leader"
            }
        }


class UserProfileCreate(BaseModel):
    """Schema for creating a KYC user profile."""
    user_id: str = Field(..., description="ID of the user this profile belongs to")
    full_name: str = Field(..., description="Full legal name")
    date_of_birth: Optional[str] = Field(None, description="Date of birth in YYYY-MM-DD format")
    nationality: Optional[str] = Field(None, description="Nationality (ISO 3166-1 alpha-2 country code)")
    address: Optional[AddressSchema] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    
    # Additional information
    tax_id: Optional[str] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
    source_of_funds: Optional[str] = None
    politically_exposed: Optional[bool] = False
    
    # Region-specific
    region_id: Optional[str] = None
    
    # Simplified KYC references
    references: Optional[List[ReferenceCreate]] = None
    
    # Security
    is_encrypted: bool = True
    
    @validator('date_of_birth')
    def validate_date_format(cls, v):
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in format YYYY-MM-DD")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "full_name": "John Doe",
                "date_of_birth": "1990-01-01",
                "nationality": "US",
                "address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "state": "State",
                    "country": "US",
                    "postal_code": "12345"
                },
                "phone_number": "+1234567890",
                "email": "john.doe@example.com",
                "tax_id": "123-45-6789",
                "occupation": "Software Engineer",
                "employer": "Tech Company",
                "source_of_funds": "Employment",
                "politically_exposed": False,
                "region_id": "region123",
                "is_encrypted": True
            }
        }


class UserProfileUpdate(BaseModel):
    """Schema for updating a KYC user profile."""
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    address: Optional[AddressSchema] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    
    # Additional information
    tax_id: Optional[str] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
    source_of_funds: Optional[str] = None
    politically_exposed: Optional[bool] = None
    
    # Status
    status: Optional[ProfileStatusEnum] = None
    
    # Simplified KYC references
    references: Optional[List[ReferenceCreate]] = None
    
    @validator('date_of_birth')
    def validate_date_format(cls, v):
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in format YYYY-MM-DD")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "John Doe",
                "phone_number": "+1987654321",
                "occupation": "Senior Software Engineer",
                "status": "complete"
            }
        }


class UserProfileResponse(BaseModel):
    """Schema for KYC user profile response."""
    id: str
    user_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    # Only include essential fields with personal data masked
    full_name: str
    nationality: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    
    # Simplified KYC indicator
    has_references: bool = False
    reference_count: int = 0
    
    # Region information
    region_name: Optional[str] = None
    infrastructure_level: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "profile123",
                "user_id": "user123",
                "status": "verified",
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-02T14:30:00",
                "full_name": "John Doe",
                "nationality": "US",
                "last_verified_at": "2023-01-02T14:30:00",
                "has_references": True,
                "reference_count": 2,
                "region_name": "East Africa",
                "infrastructure_level": "medium"
            }
        }


class UserProfileList(BaseModel):
    """Paginated list of KYC user profiles."""
    items: List[UserProfileResponse]
    total: int
    page: int
    size: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "profile123",
                        "user_id": "user123",
                        "status": "verified",
                        "created_at": "2023-01-01T12:00:00",
                        "updated_at": "2023-01-02T14:30:00",
                        "full_name": "John Doe",
                        "nationality": "US",
                        "last_verified_at": "2023-01-02T14:30:00",
                        "has_references": True,
                        "reference_count": 2,
                        "region_name": "East Africa",
                        "infrastructure_level": "medium"
                    }
                ],
                "total": 50,
                "page": 1,
                "size": 10
            }
        }
