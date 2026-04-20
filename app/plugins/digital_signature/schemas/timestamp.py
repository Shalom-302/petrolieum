"""
Pydantic schemas for secure timestamps.

This module contains Pydantic models for validating and serializing
data related to cryptographic timestamps in API requests and responses.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TimestampBase(BaseModel):
    """Base model for timestamp data."""
    description: Optional[str] = Field(None, description="Optional description of the timestamp")


class TimestampCreate(TimestampBase):
    """Model for creating a new timestamp."""
    data_source: Optional[str] = Field(None, description="Source of the data being timestamped")
    
    class Config:
        json_schema_extra = {
            "example": {
                "data_source": "quarterly_report.pdf",
                "description": "Timestamp for Q1 financial report"
            }
        }


class TimestampResponse(BaseModel):
    """Model for timestamp response data."""
    id: str = Field(..., description="Unique identifier of the timestamp")
    timestamp: datetime = Field(..., description="Timestamp value")
    data_source: Optional[str] = Field(None, description="Source of the timestamped data")
    data_hash: str = Field(..., description="Hash of the timestamped data")
    description: Optional[str] = Field(None, description="Description of the timestamp")
    status: str = Field(..., description="Status of the timestamp operation")
    error: Optional[str] = Field(None, description="Error message if status is failed")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2025-03-16T19:30:45Z",
                "data_source": "quarterly_report.pdf",
                "data_hash": "5d41402abc4b2a76b9719d911017c592",
                "description": "Timestamp for Q1 financial report",
                "status": "completed"
            }
        }


class TimestampVerify(BaseModel):
    """Model for timestamp verification request."""
    timestamp_id: str = Field(..., description="ID of the timestamp to verify")
    data: Optional[str] = Field(None, description="Base64-encoded data to verify against the timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp_id": "123e4567-e89b-12d3-a456-426614174000",
                "data": "YmFzZTY0IGVuY29kZWQgZGF0YSBoZXJl"
            }
        }


class TimestampVerifyResponse(BaseModel):
    """Model for timestamp verification response."""
    verified: bool = Field(..., description="Whether the timestamp is valid")
    timestamp: Optional[datetime] = Field(None, description="Timestamp value")
    data_hash: Optional[str] = Field(None, description="Hash of the timestamped data")
    issuer: Optional[str] = Field(None, description="Issuer of the timestamp")
    error: Optional[str] = Field(None, description="Error message if verification failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "verified": True,
                "timestamp": "2025-03-16T19:30:45Z",
                "data_hash": "5d41402abc4b2a76b9719d911017c592",
                "issuer": "KAAPI Timestamping Authority"
            }
        }
