"""
Alert rule schemas definition.

This module contains Pydantic models for alert rules to handle
request validation and response serialization.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator

class RuleBase(BaseModel):
    """Base schema with common rule attributes."""
    name: str = Field(..., description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    entity_type: str = Field(..., description="Type of entity this rule applies to")
    alert_type: str = Field(..., description="Type of alert this rule generates")
    condition: Dict[str, Any] = Field(..., description="Condition logic for alert detection")
    severity: str = Field(..., description="Alert severity (critical, warning, info)")
    message_template: str = Field(..., description="Template for alert messages")
    check_frequency: str = Field("daily", description="Frequency for checking this rule")
    priority: int = Field(100, description="Priority for execution order")

class RuleCreate(RuleBase):
    """Schema for creating a new alert rule."""
    is_active: bool = Field(True, description="Whether this rule is active")

class RuleUpdate(BaseModel):
    """Schema for updating an existing alert rule."""
    name: Optional[str] = Field(None, description="Updated rule name")
    description: Optional[str] = Field(None, description="Updated rule description")
    condition: Optional[Dict[str, Any]] = Field(None, description="Updated condition logic")
    severity: Optional[str] = Field(None, description="Updated alert severity")
    message_template: Optional[str] = Field(None, description="Updated message template")
    is_active: Optional[bool] = Field(None, description="Updated active status")
    check_frequency: Optional[str] = Field(None, description="Updated check frequency")
    priority: Optional[int] = Field(None, description="Updated priority")
    
    @validator('severity')
    def validate_severity(cls, v):
        """Validate that severity is a valid value."""
        if v and v not in ['critical', 'warning', 'info']:
            raise ValueError("Severity must be one of: critical, warning, info")
        return v
    
    @validator('check_frequency')
    def validate_frequency(cls, v):
        """Validate that check frequency is a valid value."""
        if v and v not in ['hourly', 'daily', 'weekly']:
            raise ValueError("Check frequency must be one of: hourly, daily, weekly")
        return v

class RuleResponse(RuleBase):
    """Schema for rule responses."""
    id: str = Field(..., description="Rule ID")
    is_active: bool = Field(..., description="Whether this rule is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="User ID of creator")
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True

class RuleFilter(BaseModel):
    """Schema for filtering rules in list endpoints."""
    entity_type: Optional[str] = Field(None, description="Filter by entity type")
    alert_type: Optional[str] = Field(None, description="Filter by alert type")
    severity: Optional[str] = Field(None, description="Filter by severity")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    check_frequency: Optional[str] = Field(None, description="Filter by check frequency")

class PaginatedRuleResponse(BaseModel):
    """Schema for paginated rule responses."""
    items: List[RuleResponse] = Field(..., description="List of rules")
    total: int = Field(..., description="Total number of rules matching filters")
    page: int = Field(1, description="Current page number")
    size: int = Field(..., description="Page size")
