"""
Schemas for KYC region configurations.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, validator
from enum import Enum

from ..models.region import InfrastructureLevel


class InfrastructureLevelEnum(str, Enum):
    """Infrastructure level of a region affecting KYC requirements."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class DocumentRequirement(BaseModel):
    """Schema for document requirements by verification type."""
    required: List[str] = Field([], description="List of required document types")
    alternative: List[str] = Field([], description="Alternative documents that can be used")
    min_documents: int = Field(1, description="Minimum number of documents required")
    
    class Config:
        json_schema_extra = {
            "example": {
                "required": ["passport", "national_id"],
                "alternative": ["drivers_license", "voter_id"],
                "min_documents": 1
            }
        }


class SimplifiedKycSettings(BaseModel):
    """Schema for simplified KYC settings."""
    enabled: bool = Field(True, description="Whether simplified KYC is enabled for this region")
    transaction_threshold: Optional[int] = Field(None, description="Maximum transaction amount for simplified KYC")
    required_references: int = Field(1, description="Number of trusted references required")
    accepted_referee_types: List[str] = Field(..., description="Types of accepted referees")
    verification_methods: List[str] = Field(..., description="Methods to verify references")
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "transaction_threshold": 500,
                "required_references": 1,
                "accepted_referee_types": ["community_leader", "bank_officer", "government_official"],
                "verification_methods": ["phone_verification", "in_person_verification"]
            }
        }


class RegionCreate(BaseModel):
    """Schema for creating a KYC region configuration."""
    name: str = Field(..., description="Region name")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")
    infrastructure_level: InfrastructureLevelEnum = Field(..., description="Infrastructure level of the region")
    
    # Document requirements by verification type
    required_documents: Dict[str, DocumentRequirement] = Field(
        ..., 
        description="Document requirements for each verification type"
    )
    
    # Simplified KYC settings
    simplified_kyc_enabled: bool = Field(False, description="Whether simplified KYC is enabled")
    simplified_requirements: Optional[SimplifiedKycSettings] = None
    
    # Additional settings
    verification_expiry_days: int = Field(365, description="Days until verification expires")
    regulatory_requirements: Optional[str] = None
    description: Optional[str] = None
    
    @validator('country_code')
    def validate_country_code(cls, v):
        if len(v) != 2 or not v.isalpha():
            raise ValueError("Country code must be ISO 3166-1 alpha-2 format (e.g., 'US')")
        return v.upper()
    
    @validator('simplified_requirements')
    def validate_simplified_requirements(cls, v, values):
        if values.get('simplified_kyc_enabled') and not v:
            raise ValueError("Simplified KYC requirements must be provided when simplified KYC is enabled")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "East Africa",
                "country_code": "KE",
                "infrastructure_level": "low",
                "required_documents": {
                    "standard": {
                        "required": ["national_id", "passport"],
                        "alternative": ["voter_id", "birth_certificate"],
                        "min_documents": 1
                    },
                    "simplified": {
                        "required": ["mobile_verification"],
                        "alternative": ["third_party_reference"],
                        "min_documents": 1
                    }
                },
                "simplified_kyc_enabled": True,
                "simplified_requirements": {
                    "enabled": True,
                    "transaction_threshold": 500,
                    "required_references": 1,
                    "accepted_referee_types": ["community_leader", "bank_officer"],
                    "verification_methods": ["phone_verification"]
                },
                "verification_expiry_days": 365,
                "regulatory_requirements": "Local regulations allow simplified KYC for transactions under $500.",
                "description": "Region covering East African countries with low digital infrastructure."
            }
        }


class RegionUpdate(BaseModel):
    """Schema for updating a KYC region configuration."""
    name: Optional[str] = None
    infrastructure_level: Optional[InfrastructureLevelEnum] = None
    required_documents: Optional[Dict[str, DocumentRequirement]] = None
    alternative_documents: Optional[Dict[str, List[str]]] = None
    simplified_kyc_enabled: Optional[bool] = None
    simplified_requirements: Optional[SimplifiedKycSettings] = None
    verification_expiry_days: Optional[int] = None
    regulatory_requirements: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "infrastructure_level": "medium",
                "simplified_kyc_enabled": True,
                "verification_expiry_days": 730,
                "description": "Updated description for East Africa region."
            }
        }


class RegionResponse(BaseModel):
    """Schema for KYC region configuration response."""
    id: str
    name: str
    country_code: str
    infrastructure_level: str
    created_at: datetime
    updated_at: datetime
    simplified_kyc_enabled: bool
    verification_expiry_days: int
    description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "region123",
                "name": "East Africa",
                "country_code": "KE",
                "infrastructure_level": "low",
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-02T14:30:00",
                "simplified_kyc_enabled": True,
                "verification_expiry_days": 365,
                "description": "Region covering East African countries with low digital infrastructure."
            }
        }


class RegionList(BaseModel):
    """Schema for list of KYC region configurations."""
    items: List[RegionResponse]
    total: int
    page: int
    size: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "region123",
                        "name": "East Africa",
                        "country_code": "KE",
                        "infrastructure_level": "low",
                        "created_at": "2023-01-01T12:00:00",
                        "updated_at": "2023-01-02T14:30:00",
                        "simplified_kyc_enabled": True,
                        "verification_expiry_days": 365,
                        "description": "Region covering East African countries with low digital infrastructure."
                    }
                ],
                "total": 1,
                "page": 1,
                "size": 10
            }
        }
