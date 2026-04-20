"""
Database models for the PWA Support plugin
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.db import Base
from datetime import datetime
import json


# Association table for many-to-many relationship between PushSubscription and NotificationSegment
subscription_segment_association = Table(
    "subscription_segment_association",
    Base.metadata,
    Column("subscription_id", Integer, ForeignKey("push_subscriptions.id")),
    Column("segment_id", Integer, ForeignKey("notification_segments.id"))
)


class PWASettings(Base):
    """
    Main settings model for PWA configuration
    Stores manifest and service worker configuration as JSON strings
    """
    __tablename__ = "pwa_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    manifest = Column(Text, nullable=True)  # JSON string of the PWA manifest
    service_worker_config = Column(Text, nullable=True)  # JSON string of service worker config
    vapid_public_key = Column(String(255), nullable=True)
    vapid_private_key = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_manifest(self):
        """Parse and return the manifest as a Python dictionary"""
        if not self.manifest:
            return {}
        return json.loads(self.manifest)
    
    def get_service_worker_config(self):
        """Parse and return the service worker config as a Python dictionary"""
        if not self.service_worker_config:
            return {}
        return json.loads(self.service_worker_config)


class NotificationSegment(Base):
    """
    Model for grouping subscriptions into segments for targeted notifications
    """
    __tablename__ = "notification_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    criteria = Column(Text, nullable=True)  # JSON string storing criteria for automatic assignment
    is_dynamic = Column(Boolean, default=False)  # If True, segment is dynamically populated based on criteria
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Many-to-many relationship with subscriptions
    subscriptions = relationship(
        "PushSubscription", 
        secondary=subscription_segment_association,
        back_populates="segments"
    )
    
    # One-to-many relationship with notification history
    notifications = relationship("NotificationHistory", back_populates="segment")
    
    def get_criteria(self):
        """Parse and return the criteria as a Python dictionary"""
        if not self.criteria:
            return {}
        return json.loads(self.criteria)


class PushSubscription(Base):
    """
    Model for storing push notification subscriptions
    Each record represents a browser/device subscription
    """
    __tablename__ = "push_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(500), nullable=False, unique=True)
    p256dh = Column(String(255), nullable=False)  # Public key for encryption
    auth = Column(String(255), nullable=False)  # Auth secret
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)  # Optional link to user
    user_agent = Column(String(500), nullable=True)  # Browser/device info
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    # Additional metadata fields for segmentation
    device_type = Column(String(50), nullable=True)  # mobile, tablet, desktop
    language = Column(String(10), nullable=True)  # Language preference
    location = Column(String(100), nullable=True)  # General location (city/country)
    tags = Column(Text, nullable=True)  # JSON array of tags for custom segmentation
    
    # Relationship to user (if authenticated)
    user = relationship("User", back_populates="push_subscriptions")
    
    # Many-to-many relationship with segments
    segments = relationship(
        "NotificationSegment",
        secondary=subscription_segment_association,
        back_populates="subscriptions"
    )
    
    # One-to-many relationship with notification receipts
    receipts = relationship("NotificationReceipt", back_populates="subscription")
    
    def get_tags(self):
        """Parse and return tags as a Python list"""
        if not self.tags:
            return []
        return json.loads(self.tags)


class NotificationHistory(Base):
    """
    Model for tracking notification campaigns
    """
    __tablename__ = "notification_history"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    icon = Column(String(255), nullable=True)
    url = Column(String(255), nullable=True)
    additional_data = Column(Text, nullable=True)  # JSON string of additional notification data
    segment_id = Column(Integer, ForeignKey("notification_segments.id"), nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    sent_count = Column(Integer, default=0)  # Number of notifications sent
    
    # Relationship to segment (if targeted)
    segment = relationship("NotificationSegment", back_populates="notifications")
    
    # One-to-many relationship with receipts
    receipts = relationship("NotificationReceipt", back_populates="notification")
    
    def get_additional_data(self):
        """Parse and return additional data as a Python dictionary"""
        if not self.additional_data:
            return {}
        return json.loads(self.additional_data)


class NotificationReceipt(Base):
    """
    Model for tracking individual notification deliveries and interactions
    """
    __tablename__ = "notification_receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("notification_history.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("push_subscriptions.id"), nullable=False)
    delivered = Column(Boolean, default=False)  # Whether delivery was successful
    clicked = Column(Boolean, default=False)  # Whether notification was clicked
    delivered_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)  # If delivery failed
    
    # Relationships
    notification = relationship("NotificationHistory", back_populates="receipts")
    subscription = relationship("PushSubscription", back_populates="receipts")
