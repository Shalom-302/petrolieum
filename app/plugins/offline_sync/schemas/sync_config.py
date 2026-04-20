"""
Schemas for synchronization configurations.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator


class SyncConfigBase(BaseModel):
    """Base model for sync configurations."""
    auto_sync_enabled: bool = Field(default=True, description="Enable automatic synchronization")
    sync_on_connectivity: bool = Field(default=True, description="Sync when connectivity is restored")
    sync_interval_minutes: int = Field(default=15, description="Interval between sync attempts")
    max_offline_storage_mb: int = Field(default=100, description="Maximum local storage in MB")
    conflict_resolution_strategy: str = Field(default="server_wins", description="Strategy for resolving conflicts")
    prioritize_by_endpoint: Optional[Dict[str, str]] = Field(None, description="Map endpoints to priorities")
    
    @validator('sync_interval_minutes')
    def validate_interval(cls, v):
        if v < 1:
            raise ValueError("Sync interval must be at least 1 minute")
        return v
    
    @validator('max_offline_storage_mb')
    def validate_storage(cls, v):
        if v < 10:
            raise ValueError("Max storage must be at least 10 MB")
        return v
    
    @validator('conflict_resolution_strategy')
    def validate_strategy(cls, v):
        valid_strategies = ["server_wins", "client_wins", "newest_wins", "manual_resolution"]
        if v not in valid_strategies:
            raise ValueError(f"Invalid conflict resolution strategy. Must be one of: {', '.join(valid_strategies)}")
        return v


class SyncConfigCreate(SyncConfigBase):
    """Model for creating a new sync configuration."""
    user_id: str = Field(..., description="ID of the user who owns this configuration")


class SyncConfigUpdate(SyncConfigBase):
    """Model for updating a sync configuration."""
    pass


class SyncConfigInDB(SyncConfigBase):
    """Model with database fields."""
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyncConfigResponse(SyncConfigInDB):
    """Response model for sync configurations."""
    pass
