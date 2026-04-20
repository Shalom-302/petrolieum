"""
Segmented Notification Service for Push Notifications

This module provides functionality for sending notifications to specific segments
of devices, allowing for targeted notification delivery.
"""

import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.plugins.push_notifications.models.database import (
    Device, 
    NotificationSegment,
    Notification,
    NotificationDevice,
    NotificationStatus,
    NotificationPriority
)
from app.plugins.push_notifications.services.segment_service import get_segment, get_segment_devices
from app.plugins.push_notifications.providers.provider_registry import get_provider_for_device
from app.plugins.push_notifications.security import SecurityHandler

logger = logging.getLogger(__name__)


class SegmentedNotificationRequest(BaseModel):
    """Request model for sending a segmented notification"""
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    segment_id: int
    icon: Optional[str] = None
    badge: Optional[int] = None
    sound: Optional[str] = None
    tag: Optional[str] = None
    url: Optional[str] = None
    ttl: Optional[int] = 86400
    priority: str = "normal"
    collapse_key: Optional[str] = None
    scheduled_at: Optional[datetime] = None


def send_segmented_notification(
    db: Session,
    notification_request: SegmentedNotificationRequest,
    batch_size: int = 100
) -> Tuple[int, int, str]:
    """
    Send a notification to devices in a specific segment
    
    Args:
        db: Database session
        notification_request: Details of the notification to send
        batch_size: Number of devices to process in each batch
        
    Returns:
        Tuple of (total devices, success count, notification_id)
    """
    # Get segment and validate
    segment = get_segment(db, notification_request.segment_id)
    if not segment:
        logger.warning(f"Segment with ID {notification_request.segment_id} not found for notification")
        return 0, 0, ""
    
    # Generate a unique notification ID
    notification_id = str(uuid.uuid4())
    
    # Log operation using secure approach for sensitive data
    secure_data = SecurityHandler.encrypt_metadata({
        "title": notification_request.title,
        "segment": segment.name,
        "segment_id": segment.id
    })
    logger.info(f"Sending segmented notification {notification_id} to segment '{segment.name}', encrypted data: {secure_data[:10]}...")
    
    # Determine the priority enum value
    priority = NotificationPriority.NORMAL
    if notification_request.priority.lower() == "high":
        priority = NotificationPriority.HIGH
    elif notification_request.priority.lower() == "low":
        priority = NotificationPriority.LOW
    
    # Create notification record
    notification = Notification(
        notification_id=notification_id,
        title=notification_request.title,
        body=notification_request.body,
        data=notification_request.data or {},
        priority=priority,
        segment_id=segment.id,
        scheduled_at=notification_request.scheduled_at,
        ttl=notification_request.ttl or 86400
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    # If scheduled for future, just save it
    if notification_request.scheduled_at and notification_request.scheduled_at > datetime.utcnow():
        logger.info(f"Notification {notification_id} scheduled for {notification_request.scheduled_at}")
        return 0, 0, notification_id
    
    # Process in batches to avoid memory issues with large segments
    offset = 0
    total_devices = 0
    success_count = 0
    
    while True:
        # Get a batch of devices
        devices = get_segment_devices(db, segment.id, skip=offset, limit=batch_size)
        if not devices:
            break
        
        total_devices += len(devices)
        
        # Send to each device in the batch
        batch_success = 0
        for device in devices:
            # Get the appropriate provider for this device
            provider = get_provider_for_device(device)
            if not provider:
                logger.warning(f"No provider found for device {device.id} ({device.device_type})")
                # Record failed delivery
                notification_device = NotificationDevice(
                    notification_id=notification.id,
                    device_id=device.id,
                    status=NotificationStatus.FAILED,
                    status_details={"error": "No provider available for device type"}
                )
                db.add(notification_device)
                continue
            
            try:
                # Prepare payload based on provider
                result = provider.send_notification(
                    device.token,
                    notification_request.title,
                    notification_request.body,
                    data=notification_request.data,
                    badge=notification_request.badge,
                    sound=notification_request.sound,
                    tag=notification_request.tag,
                    icon=notification_request.icon,
                    url=notification_request.url,
                    ttl=notification_request.ttl,
                    priority=notification_request.priority,
                    collapse_key=notification_request.collapse_key
                )
                
                # Record delivery status
                status = NotificationStatus.SENT
                status_details = result
                
                if result and "success" in result and result["success"] is True:
                    batch_success += 1
                else:
                    status = NotificationStatus.FAILED
                
                notification_device = NotificationDevice(
                    notification_id=notification.id,
                    device_id=device.id,
                    status=status,
                    status_details=status_details
                )
                db.add(notification_device)
                
            except Exception as e:
                logger.error(f"Error sending notification to device {device.id}: {str(e)}")
                # Record failed delivery
                notification_device = NotificationDevice(
                    notification_id=notification.id,
                    device_id=device.id,
                    status=NotificationStatus.FAILED,
                    status_details={"error": str(e)}
                )
                db.add(notification_device)
        
        success_count += batch_success
        
        # Save batch results
        db.commit()
        
        # Move to next batch
        offset += batch_size
    
    # Log the final results
    SecurityHandler.log_secure_operation(
        "send_segmented_notification", 
        f"Sent notification {notification_id} to {success_count}/{total_devices} devices in segment '{segment.name}'"
    )
    
    return total_devices, success_count, notification_id


def get_notification_status(db: Session, notification_id: str) -> Dict[str, Any]:
    """
    Get the status of a notification
    
    Args:
        db: Database session
        notification_id: ID of notification to check
        
    Returns:
        Dict containing notification status information
    """
    notification = db.query(Notification).filter(
        Notification.notification_id == notification_id
    ).first()
    
    if not notification:
        return {"found": False}
    
    # Get delivery statuses
    deliveries = db.query(NotificationDevice).filter(
        NotificationDevice.notification_id == notification.id
    ).all()
    
    # Count by status
    status_counts = {}
    for status in NotificationStatus:
        status_counts[status.value] = 0
    
    for delivery in deliveries:
        if delivery.status:
            status_counts[delivery.status.value] += 1
    
    return {
        "found": True,
        "notification_id": notification_id,
        "title": notification.title,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "scheduled_at": notification.scheduled_at.isoformat() if notification.scheduled_at else None,
        "segment_id": notification.segment_id,
        "total_devices": len(deliveries),
        "status_counts": status_counts
    }


def mark_notification_delivered(db: Session, notification_id: str, device_token: str) -> bool:
    """
    Mark a notification as delivered to a specific device
    
    Args:
        db: Database session
        notification_id: ID of the notification
        device_token: Token of the device that received the notification
        
    Returns:
        True if marked as delivered, False otherwise
    """
    notification = db.query(Notification).filter(
        Notification.notification_id == notification_id
    ).first()
    
    if not notification:
        return False
    
    device = db.query(Device).filter(Device.token == device_token).first()
    
    if not device:
        return False
    
    delivery = db.query(NotificationDevice).filter(
        NotificationDevice.notification_id == notification.id,
        NotificationDevice.device_id == device.id
    ).first()
    
    if not delivery:
        return False
    
    delivery.status = NotificationStatus.DELIVERED
    delivery.delivered_at = datetime.utcnow()
    
    db.add(delivery)
    db.commit()
    
    return True


def mark_notification_read(db: Session, notification_id: str, device_token: str) -> bool:
    """
    Mark a notification as read by a specific device
    
    Args:
        db: Database session
        notification_id: ID of the notification
        device_token: Token of the device that read the notification
        
    Returns:
        True if marked as read, False otherwise
    """
    notification = db.query(Notification).filter(
        Notification.notification_id == notification_id
    ).first()
    
    if not notification:
        return False
    
    device = db.query(Device).filter(Device.token == device_token).first()
    
    if not device:
        return False
    
    delivery = db.query(NotificationDevice).filter(
        NotificationDevice.notification_id == notification.id,
        NotificationDevice.device_id == device.id
    ).first()
    
    if not delivery:
        return False
    
    delivery.status = NotificationStatus.READ
    delivery.read_at = datetime.utcnow()
    
    db.add(delivery)
    db.commit()
    
    return True


def mark_notification_interacted(db: Session, notification_id: str, device_token: str) -> bool:
    """
    Mark a notification as interacted with by a specific device
    
    Args:
        db: Database session
        notification_id: ID of the notification
        device_token: Token of the device that interacted with the notification
        
    Returns:
        True if marked as interacted, False otherwise
    """
    notification = db.query(Notification).filter(
        Notification.notification_id == notification_id
    ).first()
    
    if not notification:
        return False
    
    device = db.query(Device).filter(Device.token == device_token).first()
    
    if not device:
        return False
    
    delivery = db.query(NotificationDevice).filter(
        NotificationDevice.notification_id == notification.id,
        NotificationDevice.device_id == device.id
    ).first()
    
    if not delivery:
        return False
    
    delivery.status = NotificationStatus.INTERACTED
    delivery.interacted_at = datetime.utcnow()
    
    db.add(delivery)
    db.commit()
    
    return True
