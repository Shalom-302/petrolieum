"""
Push Notifications Database Models

This module defines the database models for the push notifications plugin,
including device registrations, notification history, and templates.
"""

import enum
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Table, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

# Association table for many-to-many relationship between devices and segments
device_segment_association = Table(
    "push_notification_device_segment",
    Base.metadata,
    Column("device_id", Integer, ForeignKey("push_notification_devices.id", ondelete="CASCADE"), primary_key=True),
    Column("segment_id", Integer, ForeignKey("push_notification_segments.id", ondelete="CASCADE"), primary_key=True)
)

class NotificationPriority(enum.Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

class DeviceType(enum.Enum):
    """Device types for push notifications"""
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"
    DESKTOP = "desktop"
    UNKNOWN = "unknown"

class DeviceStatus(enum.Enum):
    """Status of a registered device"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REJECTED = "rejected"

class NotificationStatus(enum.Enum):
    """Status of a notification"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"
    INTERACTED = "interacted"

class Device(Base):
    """Device registration for push notifications"""
    __tablename__ = "push_notification_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)
    provider = Column(String(50), nullable=False)
    token = Column(String(1024), nullable=False)
    device_type = Column(Enum(DeviceType), default=DeviceType.UNKNOWN)
    device_name = Column(String(255), nullable=True)
    user_agent = Column(String(1024), nullable=True)
    language = Column(String(20), nullable=True)
    timezone = Column(String(50), nullable=True)
    status = Column(Enum(DeviceStatus), default=DeviceStatus.ACTIVE)
    
    # Encrypted metadata (e.g., device identifiers, app version, etc.)
    encrypted_metadata = Column(Text, nullable=True)
    
    # Metadata for segmentation
    segment_metadata = Column(JSON, nullable=True, default=lambda: {})
    
    # Relationships
    notifications = relationship("NotificationDevice", back_populates="device")
    segments = relationship("NotificationSegment", secondary=device_segment_association, back_populates="devices")
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_active_at = Column(DateTime, default=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "provider": self.provider,
            "device_type": self.device_type.value if self.device_type else None,
            "device_name": self.device_name,
            "status": self.status.value if self.status else None,
            "language": self.language,
            "timezone": self.timezone,
            "segment_metadata": self.segment_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }

class Notification(Base):
    """Notification history"""
    __tablename__ = "push_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)
    priority = Column(Enum(NotificationPriority), default=NotificationPriority.NORMAL)
    segment_id = Column(Integer, ForeignKey("push_notification_segments.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("push_notification_templates.id"), nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    ttl = Column(Integer, default=86400)  # Time to live in seconds
    
    # Relationships
    segment = relationship("NotificationSegment", back_populates="notifications")
    template = relationship("NotificationTemplate", back_populates="notifications")
    device_notifications = relationship("NotificationDevice", back_populates="notification")
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "notification_id": self.notification_id,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "priority": self.priority.value if self.priority else None,
            "segment_id": self.segment_id,
            "template_id": self.template_id,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "ttl": self.ttl,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class NotificationDevice(Base):
    """Mapping between notifications and devices"""
    __tablename__ = "push_notification_device_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("push_notifications.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(Integer, ForeignKey("push_notification_devices.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    status_details = Column(JSON, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    interacted_at = Column(DateTime, nullable=True)
    
    # Relationships
    notification = relationship("Notification", back_populates="device_notifications")
    device = relationship("Device", back_populates="notifications")
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "notification_id": self.notification_id,
            "device_id": self.device_id,
            "status": self.status.value if self.status else None,
            "status_details": self.status_details,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "interacted_at": self.interacted_at.isoformat() if self.interacted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class NotificationTemplate(Base):
    """Templates for notifications"""
    __tablename__ = "push_notification_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    title_template = Column(String(255), nullable=False)
    body_template = Column(Text, nullable=False)
    data_template = Column(JSON, nullable=True)
    category_id = Column(Integer, ForeignKey("push_notification_categories.id"), nullable=True)
    
    # Relationships
    category = relationship("NotificationCategory", back_populates="templates")
    notifications = relationship("Notification", back_populates="template")
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "title_template": self.title_template,
            "body_template": self.body_template,
            "data_template": self.data_template,
            "category_id": self.category_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class NotificationCategory(Base):
    """Categories for notification templates"""
    __tablename__ = "push_notification_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Relationships
    templates = relationship("NotificationTemplate", back_populates="category")
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class NotificationSegment(Base):
    """Segments for targeting notifications"""
    __tablename__ = "push_notification_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    criteria = Column(JSON, nullable=True)
    is_dynamic = Column(Boolean, default=False)
    
    # Relationships
    devices = relationship("Device", secondary=device_segment_association, back_populates="segments")
    notifications = relationship("Notification", back_populates="segment")
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "criteria": self.criteria,
            "is_dynamic": self.is_dynamic,
            "device_count": len(self.devices) if self.devices else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def evaluate_device(self, device: Device) -> bool:
        """
        Evaluate if a device matches this segment's criteria
        
        Args:
            device: Device to evaluate
            
        Returns:
            bool: True if device matches criteria, False otherwise
        """
        if not self.is_dynamic or not self.criteria:
            return False
        
        criteria = self.criteria
        metadata = device.segment_metadata or {}
        
        # Evaluate device metadata against criteria
        for key, value in criteria.items():
            # Handle special criteria fields
            if key == "device_type" and hasattr(device, "device_type"):
                if isinstance(value, list):
                    if device.device_type.value not in value:
                        return False
                elif device.device_type.value != value:
                    return False
            
            elif key == "language" and hasattr(device, "language"):
                if isinstance(value, list):
                    if device.language not in value:
                        return False
                elif device.language != value:
                    return False
            
            elif key == "timezone" and hasattr(device, "timezone"):
                if isinstance(value, list):
                    if device.timezone not in value:
                        return False
                elif device.timezone != value:
                    return False
            
            # Check in metadata
            elif key in metadata:
                if isinstance(value, list):
                    if metadata[key] not in value:
                        return False
                elif metadata[key] != value:
                    return False
            
            # If key not found and required, return False
            else:
                return False
        
        return True
