"""
Push Notifications Schemas

This module defines the Pydantic schemas for notification operations,
implementing robust request validation as part of the standardized security approach.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator, root_validator
import re


class NotificationBase(BaseModel):
    """Base schema for notification data."""
    title: str = Field(..., min_length=1, max_length=255, description="Notification title")
    body: str = Field(..., min_length=1, max_length=4000, description="Notification body text")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data payload")
    priority: Optional[str] = Field("normal", description="Notification priority (high, normal)")
    ttl: Optional[int] = Field(None, ge=60, le=2592000, description="Time to live in seconds (1-30 days)")
    collapse_key: Optional[str] = Field(None, max_length=255, description="Key for grouping notifications")
    
    @validator('priority')
    def validate_priority(cls, v):
        """Validate priority value."""
        allowed_priorities = ['high', 'normal']
        if v and v.lower() not in allowed_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(allowed_priorities)}")
        return v.lower() if v else "normal"
    
    @validator('data')
    def validate_data(cls, v):
        """Validate data payload for security."""
        if v:
            # Check data payload size
            import json
            data_json = json.dumps(v)
            if len(data_json) > 4096:
                raise ValueError("Data payload exceeds maximum size (4KB)")
            
            # Check for sensitive patterns in keys
            sensitive_patterns = ['password', 'token', 'secret', 'credit', 'card',
                               'auth', 'private', 'key', 'certificate']
            for key in v.keys():
                if any(pattern in key.lower() for pattern in sensitive_patterns):
                    raise ValueError(f"Data contains sensitive key: {key}")
        
        return v


class NotificationCreate(NotificationBase):
    """Schema for creating a new notification."""
    user_ids: List[str] = Field(..., min_items=1, description="User IDs to receive the notification")
    scheduled_for: Optional[datetime] = Field(None, description="When to send the notification")
    
    @validator('user_ids')
    def validate_user_ids(cls, v):
        """Validate user IDs."""
        if not v:
            raise ValueError("At least one user ID is required")
        
        for user_id in v:
            if not user_id or len(user_id) < 3:
                raise ValueError("Invalid user ID format")
        
        # Limit number of recipients for performance
        if len(v) > 1000:
            raise ValueError("Maximum of 1000 users per request")
        
        return v
    
    @validator('scheduled_for')
    def validate_scheduled_time(cls, v):
        """Validate scheduled time is in the future."""
        if v and v < datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v


class NotificationTemplateCreate(BaseModel):
    """Schema for creating a notification template."""
    name: str = Field(..., min_length=1, max_length=100, description="Template name/identifier")
    title_template: str = Field(..., min_length=1, max_length=255, description="Template for notification title")
    body_template: str = Field(..., min_length=1, max_length=4000, description="Template for notification body")
    data_template: Optional[Dict[str, Any]] = Field(None, description="Template for notification data payload")
    description: Optional[str] = Field(None, description="Template description")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate template name."""
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError("Template name must contain only alphanumeric characters, underscores, hyphens, and dots")
        return v
    
    @validator('title_template', 'body_template')
    def validate_template_format(cls, v, values, **kwargs):
        """Validate template format with placeholders."""
        if v and '{{' in v and '}}' not in v:
            raise ValueError("Invalid template format: unclosed placeholder")
        return v
    
    @validator('data_template')
    def validate_data_template(cls, v):
        """Validate data template for security."""
        if v:
            # Check for sensitive patterns in keys
            sensitive_patterns = ['password', 'token', 'secret', 'credit', 'card',
                               'auth', 'private', 'key', 'certificate']
            for key in v.keys():
                if any(pattern in key.lower() for pattern in sensitive_patterns):
                    raise ValueError(f"Data template contains sensitive key: {key}")
        
        return v


class TemplateNotificationCreate(BaseModel):
    """Schema for creating a notification from a template."""
    template_id: str = Field(..., description="ID of the template to use")
    user_ids: List[str] = Field(..., min_items=1, description="User IDs to receive the notification")
    template_data: Dict[str, Any] = Field({}, description="Data to apply to the template")
    priority: Optional[str] = Field("normal", description="Notification priority (high, normal)")
    scheduled_for: Optional[datetime] = Field(None, description="When to send the notification")
    
    @validator('user_ids')
    def validate_user_ids(cls, v):
        """Validate user IDs."""
        if not v:
            raise ValueError("At least one user ID is required")
        
        for user_id in v:
            if not user_id or len(user_id) < 3:
                raise ValueError("Invalid user ID format")
        
        # Limit number of recipients for performance
        if len(v) > 1000:
            raise ValueError("Maximum of 1000 users per request")
        
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        """Validate priority value."""
        allowed_priorities = ['high', 'normal']
        if v and v.lower() not in allowed_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(allowed_priorities)}")
        return v.lower() if v else "normal"
    
    @validator('scheduled_for')
    def validate_scheduled_time(cls, v):
        """Validate scheduled time is in the future."""
        if v and v < datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v


class NotificationBatchCreate(BaseModel):
    """Schema for creating multiple notifications in a batch."""
    notifications: List[NotificationCreate] = Field(..., min_items=1, max_items=100, 
                                                  description="List of notifications to send")
    
    @validator('notifications')
    def validate_notifications(cls, v):
        """Validate notifications list."""
        if not v:
            raise ValueError("At least one notification is required")
        
        # Limit total number of recipients across all notifications
        total_recipients = sum(len(notif.user_ids) for notif in v)
        if total_recipients > 10000:
            raise ValueError("Total number of recipients cannot exceed 10,000")
        
        return v


class NotificationUpdate(BaseModel):
    """Schema for updating a scheduled notification."""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Notification title")
    body: Optional[str] = Field(None, min_length=1, max_length=4000, description="Notification body text")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data payload")
    priority: Optional[str] = Field(None, description="Notification priority (high, normal)")
    scheduled_for: Optional[datetime] = Field(None, description="New scheduled time")
    
    @validator('priority')
    def validate_priority(cls, v):
        """Validate priority value if provided."""
        if v:
            allowed_priorities = ['high', 'normal']
            if v.lower() not in allowed_priorities:
                raise ValueError(f"Priority must be one of: {', '.join(allowed_priorities)}")
            return v.lower()
        return v
    
    @validator('scheduled_for')
    def validate_scheduled_time(cls, v):
        """Validate scheduled time is in the future."""
        if v and v < datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_at_least_one_field(cls, values):
        """Validate that at least one field is being updated."""
        if not any(values.values()):
            raise ValueError("At least one field must be provided for update")
        return values


class NotificationCancel(BaseModel):
    """Schema for canceling a scheduled notification."""
    notification_id: str = Field(..., description="ID of the notification to cancel")
    
    @validator('notification_id')
    def validate_notification_id(cls, v):
        """Validate notification ID format."""
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', v):
            raise ValueError("Invalid notification ID format")
        return v


class NotificationInDB(NotificationBase):
    """Schema for notification information from database."""
    id: str
    template_id: Optional[str] = None
    sender_id: Optional[str] = None
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    """Response schema for notification information."""
    id: str
    title: str
    body: str
    priority: str
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    status: str
    
    class Config:
        from_attributes = True


class NotificationDeliveryResponse(BaseModel):
    """Response schema for notification delivery status."""
    id: str
    notification_id: str
    user_id: str
    device_id: str
    status: str
    provider: str
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class NotificationDetailResponse(NotificationResponse):
    """Detailed response schema for notification information."""
    data: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    sender_id: Optional[str] = None
    collapse_key: Optional[str] = None
    ttl: Optional[int] = None
    deliveries: List[NotificationDeliveryResponse] = []
    
    class Config:
        from_attributes = True


class NotificationStatsResponse(BaseModel):
    """Response schema for notification statistics."""
    total: int
    delivered: int
    failed: int
    pending: int
    opened: int
    success_rate: float


class NotificationQueryParams(BaseModel):
    """Query parameters for filtering notifications."""
    user_id: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    template_id: Optional[str] = None
    limit: Optional[int] = 50
    offset: Optional[int] = 0
    
    @validator('status')
    def validate_status(cls, v):
        """Validate status value."""
        if v:
            allowed_statuses = ['pending', 'sent', 'delivered', 'failed', 'scheduled', 'canceled']
            if v not in allowed_statuses:
                raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v
    
    @validator('limit')
    def validate_limit(cls, v):
        """Validate limit range."""
        if v is not None and (v < 1 or v > 100):
            raise ValueError("Limit must be between 1 and 100")
        return v
    
    @validator('offset')
    def validate_offset(cls, v):
        """Validate offset range."""
        if v is not None and v < 0:
            raise ValueError("Offset must be non-negative")
        return v


class NotificationTemplateUpdate(BaseModel):
    """Schema for updating a notification template."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Template name/identifier")
    title_template: Optional[str] = Field(None, min_length=1, max_length=255, description="Template for notification title")
    body_template: Optional[str] = Field(None, min_length=1, max_length=4000, description="Template for notification body")
    data_template: Optional[Dict[str, Any]] = Field(None, description="Template for notification data payload")
    description: Optional[str] = Field(None, description="Template description")
    category_id: Optional[str] = Field(None, description="ID of the category")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate template name."""
        if v and not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError("Template name must contain only alphanumeric characters, underscores, hyphens, and dots")
        return v
    
    @validator('title_template', 'body_template')
    def validate_template_format(cls, v, values, **kwargs):
        """Validate template format with placeholders."""
        if v and '{{' in v and '}}' not in v:
            raise ValueError("Invalid template format: unclosed placeholder")
        return v
    
    @validator('data_template')
    def validate_data_template(cls, v):
        """Validate data template for security."""
        if v:
            # Check for sensitive patterns in keys
            sensitive_patterns = ['password', 'token', 'secret', 'credit', 'card',
                               'auth', 'private', 'key', 'certificate']
            for key in v.keys():
                if any(pattern in key.lower() for pattern in sensitive_patterns):
                    raise ValueError(f"Data template contains sensitive key: {key}")
        
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_at_least_one_field(cls, values):
        """Validate that at least one field is being updated."""
        if not any(v is not None for v in values.values()):
            raise ValueError("At least one field must be provided for update")
        return values


class NotificationCategoryCreate(BaseModel):
    """Schema for creating a notification category."""
    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate category name."""
        if not re.match(r'^[a-zA-Z0-9_\-\.\s]+$', v):
            raise ValueError("Category name must contain only alphanumeric characters, underscores, hyphens, dots, and spaces")
        return v


class NotificationCategoryUpdate(BaseModel):
    """Schema for updating a notification category."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate category name."""
        if v and not re.match(r'^[a-zA-Z0-9_\-\.\s]+$', v):
            raise ValueError("Category name must contain only alphanumeric characters, underscores, hyphens, dots, and spaces")
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_at_least_one_field(cls, values):
        """Validate that at least one field is being updated."""
        if not any(v is not None for v in values.values()):
            raise ValueError("At least one field must be provided for update")
        return values


class NotificationListResponse(BaseModel):
    """Response schema for listing notifications."""
    notifications: List[NotificationResponse]
    total: int
    
    class Config:
        from_attributes = True


class NotificationHistoryResponse(BaseModel):
    """Response schema for notification history."""
    notifications: List[NotificationResponse]
    total: int
    
    class Config:
        from_attributes = True


class NotificationTemplateResponse(BaseModel):
    """Response schema for notification template information."""
    id: str
    name: str
    title_template: str
    body_template: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    data_template: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    class Config:
        from_attributes = True


class NotificationTemplateListResponse(BaseModel):
    """Response schema for listing notification templates."""
    templates: List[NotificationTemplateResponse]
    total: int
    
    class Config:
        from_attributes = True


class NotificationCategoryResponse(BaseModel):
    """Response schema for notification category information."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    class Config:
        from_attributes = True


class NotificationCategoryListResponse(BaseModel):
    """Response schema for listing notification categories."""
    categories: List[NotificationCategoryResponse]
    total: int
    
    class Config:
        from_attributes = True
