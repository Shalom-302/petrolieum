"""
Social Subscriptions Database Models

This module defines the database models for the social subscriptions plugin,
including subscriptions, activity events, and feeds.
"""

import enum
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Table, Enum, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class SubscriptionCategory(enum.Enum):
    """Standard subscription categories following best practices from major platforms"""
    ALL = "all"                      # All notifications (use with caution)
    CONTENT = "content"              # New content published
    INTERACTIONS = "interactions"    # Likes, comments on your content
    MENTIONS = "mentions"            # Direct mentions
    UPDATES = "updates"              # Status/profile updates
    SYSTEM = "system"                # Important system notifications


class SubscriptionStatus(enum.Enum):
    """Status of a subscription"""
    ACTIVE = "active"
    PAUSED = "paused"
    MUTED = "muted"
    BLOCKED = "blocked"


class ActivityType(enum.Enum):
    """Types of activities that can generate notifications"""
    POST = "post"                    # New post/content creation
    COMMENT = "comment"              # Comment on content
    REACTION = "reaction"            # Reaction to content (like, etc.)
    MENTION = "mention"              # Mention in content
    FOLLOW = "follow"                # New follower
    UPDATE = "update"                # Profile/status update
    SYSTEM = "system"                # System-generated activity


class Subscription(Base):
    """User subscription to another user"""
    __tablename__ = "social_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    subscriber_id = Column(String(255), index=True, nullable=False)  # User who subscribes
    publisher_id = Column(String(255), index=True, nullable=False)   # User being followed
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    categories = Column(JSON, default=lambda: ["content", "mentions"])  # Enabled categories
    notification_preferences = Column(JSON, nullable=True)  # Additional preferences
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Create a composite index for efficient lookups
    __table_args__ = (
        Index('idx_subscriber_publisher', subscriber_id, publisher_id, unique=True),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "subscriber_id": self.subscriber_id,
            "publisher_id": self.publisher_id, 
            "status": self.status.value if self.status else None,
            "categories": self.categories,
            "notification_preferences": self.notification_preferences,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ActivityEvent(Base):
    """Activity event that can generate notifications"""
    __tablename__ = "social_activity_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, index=True, nullable=False)
    publisher_id = Column(String(255), index=True, nullable=False)  # Creator of the activity
    activity_type = Column(Enum(ActivityType), nullable=False)
    category = Column(Enum(SubscriptionCategory), nullable=False)
    resource_type = Column(String(50), nullable=False)  # Type of resource (article, photo, etc.)
    resource_id = Column(String(255), nullable=False)   # ID of the affected resource
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    activity_metadata = Column(JSON, nullable=True)  # Additional data
    created_at = Column(DateTime, default=func.now())
    
    # Create indexes for efficient queries
    __table_args__ = (
        Index('idx_publisher_activity', publisher_id, activity_type),
        Index('idx_resource', resource_type, resource_id),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "event_id": self.event_id,
            "publisher_id": self.publisher_id,
            "activity_type": self.activity_type.value if self.activity_type else None,
            "category": self.category.value if self.category else None,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "title": self.title,
            "description": self.description,
            "metadata": self.activity_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class FeedItem(Base):
    """Pre-generated feed item for efficient feed delivery"""
    __tablename__ = "social_feed_items"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)  # Feed owner
    activity_id = Column(Integer, ForeignKey("social_activity_events.id", ondelete="CASCADE"), nullable=False)
    publisher_id = Column(String(255), index=True, nullable=False)  # Creator of the activity
    is_read = Column(Boolean, default=False)
    is_hidden = Column(Boolean, default=False)
    relevance_score = Column(Integer, default=100)  # For algorithmic feeds (higher is more relevant)
    created_at = Column(DateTime, default=func.now())
    
    # Relationship to the activity event
    activity = relationship("ActivityEvent")
    
    # Create indexes for efficient feed queries
    __table_args__ = (
        Index('idx_user_feed', user_id, is_hidden, created_at),
        Index('idx_user_publisher', user_id, publisher_id),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "activity_id": self.activity_id,
            "publisher_id": self.publisher_id,
            "is_read": self.is_read,
            "is_hidden": self.is_hidden,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "activity": self.activity.to_dict() if self.activity else None
        }


class NotificationRecord(Base):
    """Record of notifications sent for activities"""
    __tablename__ = "social_notification_records"
    
    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("social_activity_events.id", ondelete="CASCADE"), nullable=False)
    recipient_id = Column(String(255), index=True, nullable=False)
    notification_id = Column(String(255), nullable=True)  # ID from push notification service
    status = Column(String(50), default="pending")  # pending, sent, failed, delivered, read
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationship to the activity event
    activity = relationship("ActivityEvent")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "activity_id": self.activity_id,
            "recipient_id": self.recipient_id,
            "notification_id": self.notification_id,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class UserPreference(Base):
    """User preferences for social subscriptions and notifications"""
    __tablename__ = "social_user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), unique=True, index=True, nullable=False)
    feed_type = Column(String(50), default="chronological")  # chronological, algorithmic
    notification_channels = Column(JSON, default=lambda: ["push", "in_app"])
    enabled_categories = Column(JSON, default=lambda: [cat.value for cat in SubscriptionCategory])
    quiet_hours = Column(JSON, nullable=True)  # e.g. {"start": "22:00", "end": "07:00", "timezone": "UTC"}
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "feed_type": self.feed_type,
            "notification_channels": self.notification_channels,
            "enabled_categories": self.enabled_categories,
            "quiet_hours": self.quiet_hours,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
