"""
Alert schemas definition.

This module contains Pydantic models for business alerts to handle
request validation and response serialization.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator

class AlertBase(BaseModel):
    """Base schema with common alert attributes."""
    entity_type: str = Field(..., description="Type of entity (company, user, etc.)")
    entity_id: str = Field(..., description="ID of the entity")
    alert_type: str = Field(..., description="Type of alert (missing_financial_data, etc.)")
    severity: str = Field(..., description="Alert severity (critical, warning, info)")
    message: str = Field(..., description="Alert message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional alert details")

class AlertCreate(AlertBase):
    """Schema for creating a new alert."""
    status: str = Field("active", description="Alert status (active, acknowledged, resolved)")

class AlertUpdate(BaseModel):
    """Schema for updating an existing alert."""
    status: Optional[str] = Field(None, description="New alert status")
    message: Optional[str] = Field(None, description="Updated alert message")
    severity: Optional[str] = Field(None, description="Updated alert severity")
    details: Optional[Dict[str, Any]] = Field(None, description="Updated alert details")
    
    @validator('status')
    def validate_status(cls, v):
        """Validate that status is a valid value."""
        if v and v not in ['active', 'acknowledged', 'resolved']:
            raise ValueError("Status must be one of: active, acknowledged, resolved")
        return v

class AlertResponse(AlertBase):
    """Schema for alert responses."""
    id: str = Field(..., description="Alert ID")
    status: str = Field(..., description="Alert status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    acknowledged_at: Optional[datetime] = Field(None, description="Acknowledgment timestamp")
    acknowledged_by: Optional[str] = Field(None, description="User ID who acknowledged the alert")
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True
        
class AlertFilter(BaseModel):
    """Schema for filtering alerts in list endpoints."""
    entity_type: Optional[str] = Field(None, description="Filter by entity type")
    entity_id: Optional[str] = Field(None, description="Filter by entity ID")
    alert_type: Optional[str] = Field(None, description="Filter by alert type")
    severity: Optional[str] = Field(None, description="Filter by severity")
    status: Optional[str] = Field(None, description="Filter by status")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date (before)")

class PaginatedAlertResponse(BaseModel):
    """Schema for paginated alert responses."""
    items: List[AlertResponse] = Field(..., description="List of alerts")
    total: int = Field(..., description="Total number of alerts matching filters")
    page: int = Field(1, description="Current page number")
    size: int = Field(..., description="Page size")
