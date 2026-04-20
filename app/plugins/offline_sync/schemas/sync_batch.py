"""
Schemas for synchronization batches.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from ..models.base import SyncStatus, SyncPriority


class SyncBatchBase(BaseModel):
    """Base model for sync batches."""
    name: Optional[str] = Field(None, description="Optional name for the batch")
    description: Optional[str] = Field(None, description="Optional description")
    priority: SyncPriority = Field(default=SyncPriority.NORMAL, description="Priority level")


class SyncBatchCreate(SyncBatchBase):
    """Model for creating a new sync batch."""
    user_id: str = Field(..., description="ID of the user who owns this batch")


class SyncBatchUpdate(BaseModel):
    """Model for updating a sync batch."""
    name: Optional[str] = Field(None, description="Updated name")
    description: Optional[str] = Field(None, description="Updated description")
    status: Optional[SyncStatus] = Field(None, description="Updated status")
    priority: Optional[SyncPriority] = Field(None, description="Updated priority")


class SyncBatchInDB(SyncBatchBase):
    """Model with database fields."""
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    status: SyncStatus

    class Config:
        from_attributes = True


class SyncBatchResponse(SyncBatchInDB):
    """Response model for sync batches."""
    operation_count: int = Field(0, description="Number of operations in this batch")


class SyncBatchList(BaseModel):
    """Model for list of sync batches."""
    total: int
    items: List[SyncBatchResponse]
