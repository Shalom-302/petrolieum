"""
Social Subscriptions Schemas

This module defines the Pydantic schemas for the social subscriptions plugin,
implementing robust request validation as part of the standardized security approach.
"""

from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator


class SubscriptionCategoryEnum(str, Enum):
    """Standard subscription categories following best practices from major platforms"""
    ALL = "all"                      # All notifications (use with caution)
    CONTENT = "content"              # New content published
    INTERACTIONS = "interactions"    # Likes, comments on your content
    MENTIONS = "mentions"            # Direct mentions
    UPDATES = "updates"              # Status/profile updates
    SYSTEM = "system"                # Important system notifications


class SubscriptionStatusEnum(str, Enum):
    """Status of a subscription"""
    ACTIVE = "active"
    PAUSED = "paused"
    MUTED = "muted"
    BLOCKED = "blocked"


class ActivityTypeEnum(str, Enum):
    """Types of activities that can generate notifications"""
    POST = "post"                    # New post/content creation
    COMMENT = "comment"              # Comment on content
    REACTION = "reaction"            # Reaction to content (like, etc.)
    MENTION = "mention"              # Mention in content
    FOLLOW = "follow"                # New follower
    UPDATE = "update"                # Profile/status update
    SYSTEM = "system"                # System-generated activity


class SubscriptionCreate(BaseModel):
    """Schema for creating a new subscription"""
    publisher_id: str = Field(..., description="ID of the user to subscribe to")
    categories: Optional[List[SubscriptionCategoryEnum]] = Field(
        default=["content", "mentions"],
        description="Categories of notifications to receive"
    )
    notification_preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional notification preferences (platform-specific)"
    )
    
    @validator('publisher_id')
    def validate_publisher_id(cls, value):
        """Validate publisher ID"""
        if not value:
            raise ValueError("Publisher ID cannot be empty")
        return value
    
    @validator('categories')
    def validate_categories(cls, value):
        """Validate subscription categories"""
        if not value:
            return ["content", "mentions"]
        return value


class SubscriptionUpdate(BaseModel):
    """Schema for updating an existing subscription"""
    status: Optional[SubscriptionStatusEnum] = Field(
        None,
        description="Status of the subscription"
    )
    categories: Optional[List[SubscriptionCategoryEnum]] = Field(
        None,
        description="Categories of notifications to receive"
    )
    notification_preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional notification preferences (platform-specific)"
    )


class SubscriptionResponse(BaseModel):
    """Schema for subscription response"""
    id: int
    subscriber_id: str
    publisher_id: str
    status: SubscriptionStatusEnum
    categories: List[SubscriptionCategoryEnum]
    notification_preferences: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SubscriptionFilter(BaseModel):
    """Schema for filtering subscriptions"""
    status: Optional[SubscriptionStatusEnum] = None
    category: Optional[SubscriptionCategoryEnum] = None


class ActivityEventCreate(BaseModel):
    """Schema for creating a new activity event"""
    publisher_id: str = Field(..., description="ID of the user creating the activity")
    activity_type: ActivityTypeEnum = Field(..., description="Type of activity")
    category: SubscriptionCategoryEnum = Field(..., description="Category of subscription this belongs to")
    resource_type: str = Field(..., description="Type of resource (article, photo, etc.)")
    resource_id: str = Field(..., description="ID of the affected resource")
    title: Optional[str] = Field(None, description="Title of the activity")
    description: Optional[str] = Field(None, description="Description of the activity")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional activity data")
    
    @validator('resource_type')
    def validate_resource_type(cls, value):
        """Validate resource type"""
        if not value:
            raise ValueError("Resource type cannot be empty")
        return value
    
    @validator('resource_id')
    def validate_resource_id(cls, value):
        """Validate resource ID"""
        if not value:
            raise ValueError("Resource ID cannot be empty")
        return value


class ActivityEventResponse(BaseModel):
    """Schema for activity event response"""
    id: int
    event_id: str
    publisher_id: str
    activity_type: ActivityTypeEnum
    category: SubscriptionCategoryEnum
    resource_type: str
    resource_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class FeedItemCreate(BaseModel):
    """Schema for creating a feed item"""
    user_id: str
    activity_id: int
    publisher_id: str
    relevance_score: Optional[int] = 100
    
    @validator('relevance_score')
    def validate_relevance_score(cls, value):
        """Validate relevance score"""
        if value is not None and (value < 0 or value > 1000):
            raise ValueError("Relevance score must be between 0 and 1000")
        return value


class FeedItemResponse(BaseModel):
    """Schema for feed item response"""
    id: int
    user_id: str
    activity_id: int
    publisher_id: str
    is_read: bool
    is_hidden: bool
    relevance_score: int
    created_at: datetime
    activity: Optional[ActivityEventResponse] = None
    
    class Config:
        from_attributes = True


class FeedFilter(BaseModel):
    """Schema for filtering feed items"""
    include_read: Optional[bool] = False
    publisher_ids: Optional[List[str]] = None
    activity_types: Optional[List[ActivityTypeEnum]] = None
    categories: Optional[List[SubscriptionCategoryEnum]] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None


class QuietHoursSettings(BaseModel):
    """Schema for quiet hours settings"""
    start: str = Field(..., description="Start time in format HH:MM")
    end: str = Field(..., description="End time in format HH:MM")
    timezone: str = Field("UTC", description="Timezone name")
    enabled: bool = Field(True, description="Whether quiet hours are enabled")
    
    @validator('start', 'end')
    def validate_time_format(cls, value):
        """Validate time format"""
        try:
            hour, minute = value.split(":")
            if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                raise ValueError()
        except (ValueError, AttributeError):
            raise ValueError("Time must be in format HH:MM (00:00 to 23:59)")
        return value


class UserPreferenceCreate(BaseModel):
    """Schema for creating user preferences"""
    feed_type: Optional[str] = Field("chronological", description="Feed type: chronological or algorithmic")
    notification_channels: Optional[List[str]] = Field(["push", "in_app"], description="Notification channels")
    enabled_categories: Optional[List[SubscriptionCategoryEnum]] = Field(
        [cat for cat in SubscriptionCategoryEnum],
        description="Enabled notification categories"
    )
    quiet_hours: Optional[QuietHoursSettings] = None
    
    @validator('feed_type')
    def validate_feed_type(cls, value):
        """Validate feed type"""
        valid_types = ["chronological", "algorithmic"]
        if value not in valid_types:
            raise ValueError(f"Feed type must be one of: {', '.join(valid_types)}")
        return value


class UserPreferenceUpdate(BaseModel):
    """Schema for updating user preferences"""
    feed_type: Optional[str] = None
    notification_channels: Optional[List[str]] = None
    enabled_categories: Optional[List[SubscriptionCategoryEnum]] = None
    quiet_hours: Optional[QuietHoursSettings] = None
    
    @validator('feed_type')
    def validate_feed_type(cls, value):
        """Validate feed type"""
        if value is None:
            return value
        valid_types = ["chronological", "algorithmic"]
        if value not in valid_types:
            raise ValueError(f"Feed type must be one of: {', '.join(valid_types)}")
        return value


class UserPreferenceResponse(BaseModel):
    """Schema for user preference response"""
    id: int
    user_id: str
    feed_type: str
    notification_channels: List[str]
    enabled_categories: List[SubscriptionCategoryEnum]
    quiet_hours: Optional[QuietHoursSettings] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class NotificationRecordCreate(BaseModel):
    """Schema for creating a notification record"""
    activity_id: int
    recipient_id: str
    notification_id: Optional[str] = None
    status: str = "pending"
    
    @validator('status')
    def validate_status(cls, value):
        """Validate status"""
        valid_statuses = ["pending", "sent", "failed", "delivered", "read"]
        if value not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return value


class NotificationRecordUpdate(BaseModel):
    """Schema for updating a notification record"""
    notification_id: Optional[str] = None
    status: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    @validator('status')
    def validate_status(cls, value):
        """Validate status"""
        if value is None:
            return value
        valid_statuses = ["pending", "sent", "failed", "delivered", "read"]
        if value not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return value


class NotificationRecordResponse(BaseModel):
    """Schema for notification record response"""
    id: int
    activity_id: int
    recipient_id: str
    notification_id: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime
    activity: Optional[ActivityEventResponse] = None
    
    class Config:
        from_attributes = True
