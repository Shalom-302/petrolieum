"""
Schemas for synchronization operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
from ..models.base import SyncStatus, SyncPriority


class SyncOperationBase(BaseModel):
    """Base model for sync operations."""
    endpoint: str = Field(..., description="API endpoint for the operation")
    method: str = Field(..., description="HTTP method (GET, POST, PUT, DELETE, etc.)")
    payload: Optional[Dict[str, Any]] = Field(None, description="Request payload data")
    headers: Optional[Dict[str, str]] = Field(None, description="Request headers")
    query_params: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    priority: SyncPriority = Field(default=SyncPriority.NORMAL, description="Priority level")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class SyncOperationCreate(SyncOperationBase):
    """Model for creating a new sync operation."""
    user_id: str = Field(..., description="ID of the user who owns this operation")
    batch_id: Optional[str] = Field(None, description="Batch ID if part of a batch")
    
    # Security enhancements
    is_encrypted: bool = Field(default=False, description="Whether the payload is encrypted")
    encryption_metadata: Optional[Dict[str, Any]] = Field(None, description="Encryption metadata")
    
    @validator('payload', 'headers', 'query_params', pre=True)
    def ensure_json_serializable(cls, v):
        """Ensure data is JSON serializable and sanitized."""
        # Security implementation would be here to sanitize inputs
        return v


class SyncOperationUpdate(BaseModel):
    """Model for updating a sync operation."""
    status: Optional[SyncStatus] = Field(None, description="Updated status")
    priority: Optional[SyncPriority] = Field(None, description="Updated priority")
    retry_count: Optional[int] = Field(None, description="Number of retry attempts")
    last_error: Optional[str] = Field(None, description="Last error message")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Response data after sync")
    response_status: Optional[int] = Field(None, description="HTTP status code of response")


class SyncOperationInDB(SyncOperationBase):
    """Model with database fields."""
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    status: SyncStatus
    retry_count: int
    last_error: Optional[str] = None
    is_encrypted: bool
    encryption_metadata: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    response_status: Optional[int] = None
    batch_id: Optional[str] = None

    class Config:
        from_attributes = True


class SyncOperationResponse(SyncOperationInDB):
    """Response model for sync operations."""
    pass


class SyncOperationList(BaseModel):
    """Model for list of sync operations."""
    total: int
    items: List[SyncOperationResponse]
