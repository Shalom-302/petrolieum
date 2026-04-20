"""
Pydantic schemas for digital signatures.

This module contains Pydantic models for validating and serializing
data related to digital signatures in API requests and responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SignatureBase(BaseModel):
    """Base model for signature data."""
    description: Optional[str] = Field(None, description="Optional description of the signature")
    signature_type: str = Field("standard", description="Type of signature (qualified, advanced, standard)")


class SignatureCreate(SignatureBase):
    """Model for creating a new signature."""
    document_name: str = Field(..., description="Name of the document to sign")
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_name": "contract.pdf",
                "description": "Employment contract signature",
                "signature_type": "qualified"
            }
        }


class SignatureResponse(BaseModel):
    """Model for signature response data."""
    id: Optional[str] = Field(None, description="Unique identifier of the signature")
    document_name: str = Field(..., description="Name of the signed document")
    signature_timestamp: datetime = Field(..., description="When the document was signed")
    signature_type: str = Field(..., description="Type of signature")
    status: str = Field(..., description="Status of the signature operation")
    error: Optional[str] = Field(None, description="Error message if status is failed")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "document_name": "contract.pdf",
                "signature_timestamp": "2025-03-16T19:30:45Z",
                "signature_type": "qualified",
                "status": "completed"
            }
        }


class SignatureVerify(BaseModel):
    """Model for signature verification request."""
    signature_id: str = Field(..., description="ID of the signature to verify")
    
    class Config:
        json_schema_extra = {
            "example": {
                "signature_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class SignatureVerifyResponse(BaseModel):
    """Model for signature verification response."""
    verified: bool = Field(..., description="Whether the signature is valid")
    document_name: Optional[str] = Field(None, description="Name of the signed document")
    signature_timestamp: Optional[datetime] = Field(None, description="When the document was signed")
    signer_info: Optional[Dict[str, Any]] = Field(None, description="Information about the signer")
    signature_type: Optional[str] = Field(None, description="Type of signature")
    error: Optional[str] = Field(None, description="Error message if verification failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "verified": True,
                "document_name": "contract.pdf",
                "signature_timestamp": "2025-03-16T19:30:45Z",
                "signer_info": {
                    "name": "John Doe",
                    "organization": "KAAPI Inc."
                },
                "signature_type": "qualified"
            }
        }


class BatchSignatureRequest(BaseModel):
    """Model for batch signature request."""
    document_ids: List[str] = Field(..., description="IDs of documents to sign")
    description: Optional[str] = Field(None, description="Description to apply to all signatures")
    signature_type: str = Field("standard", description="Type of signature to apply to all documents")
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_ids": ["doc1", "doc2", "doc3"],
                "description": "Batch signing of quarterly reports",
                "signature_type": "qualified"
            }
        }


class EvidenceCreate(BaseModel):
    """Model for creating a new evidence package."""
    signature_id: str = Field(..., description="ID of the signature to create evidence for")
    include_certificate_chain: bool = Field(True, description="Whether to include the certificate chain")
    include_timestamp_proof: bool = Field(True, description="Whether to include timestamp proof")
    
    class Config:
        json_schema_extra = {
            "example": {
                "signature_id": "123e4567-e89b-12d3-a456-426614174000",
                "include_certificate_chain": True,
                "include_timestamp_proof": True
            }
        }


class EvidenceResponse(BaseModel):
    """Model for evidence package response."""
    id: str = Field(..., description="Unique identifier of the evidence package")
    signature_id: str = Field(..., description="ID of the related signature")
    created_at: datetime = Field(..., description="When the evidence package was created")
    evidence_format: str = Field(..., description="Format of the evidence package")
    is_long_term: bool = Field(..., description="Whether this is a long-term preservation evidence")
    expires_at: Optional[datetime] = Field(None, description="When the evidence expires")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "signature_id": "123e4567-e89b-12d3-a456-426614174000",
                "created_at": "2025-03-16T19:30:45Z",
                "evidence_format": "ETSI-AdES",
                "is_long_term": False,
                "expires_at": "2026-03-16T19:30:45Z"
            }
        }
