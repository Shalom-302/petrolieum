"""
Segmentation Service for Push Notifications

This module provides functionality for creating and managing notification segments,
which allow for targeted delivery of push notifications to specific groups of users.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.plugins.push_notifications.models.database import (
    Device, 
    NotificationSegment,
    device_segment_association
)
from app.plugins.push_notifications.security import SecurityHandler

logger = logging.getLogger(__name__)


def create_segment(
    db: Session, 
    name: str, 
    description: Optional[str] = None, 
    criteria: Optional[Dict[str, Any]] = None, 
    is_dynamic: bool = False
) -> NotificationSegment:
    """
    Create a new notification segment
    
    Args:
        db: Database session
        name: Name of the segment
        description: Optional description
        criteria: Optional criteria for device inclusion (for dynamic segments)
        is_dynamic: Whether the segment is dynamic (auto-populated based on criteria)
        
    Returns:
        Created NotificationSegment instance
    """
    # Log the operation with sensitive data protection
    criteria_log = "<criteria>" if criteria else "None"
    logger.info(f"Creating notification segment '{name}', dynamic: {is_dynamic}, criteria: {criteria_log}")
    
    # Create new segment
    segment = NotificationSegment(
        name=name,
        description=description,
        criteria=criteria,
        is_dynamic=is_dynamic
    )
    
    db.add(segment)
    db.commit()
    db.refresh(segment)
    
    # If it's dynamic, populate it now
    if is_dynamic and criteria:
        populate_dynamic_segment(db, segment)
    
    return segment


def update_segment(
    db: Session, 
    segment_id: int, 
    name: Optional[str] = None,
    description: Optional[str] = None,
    criteria: Optional[Dict[str, Any]] = None,
    is_dynamic: Optional[bool] = None
) -> Optional[NotificationSegment]:
    """
    Update an existing notification segment
    
    Args:
        db: Database session
        segment_id: ID of segment to update
        name: Updated name (if provided)
        description: Updated description (if provided)
        criteria: Updated criteria (if provided)
        is_dynamic: Updated dynamic status (if provided)
    
    Returns:
        Updated NotificationSegment instance or None if not found
    """
    # Retrieve the segment
    segment = db.query(NotificationSegment).filter(NotificationSegment.id == segment_id).first()
    
    if not segment:
        logger.warning(f"Segment with ID {segment_id} not found for update")
        return None
    
    # Log the operation with sensitive data protection
    criteria_log = "<criteria>" if criteria else "None"
    logger.info(f"Updating notification segment '{segment.name}' (ID: {segment_id}), new criteria: {criteria_log}")
    
    # Update provided fields
    if name is not None:
        segment.name = name
    
    if description is not None:
        segment.description = description
    
    criteria_changed = False
    if criteria is not None:
        segment.criteria = criteria
        criteria_changed = True
    
    dynamic_changed = False
    if is_dynamic is not None:
        segment.is_dynamic = is_dynamic
        dynamic_changed = True
    
    db.add(segment)
    db.commit()
    db.refresh(segment)
    
    # If dynamic status or criteria changed and segment is dynamic, repopulate
    if segment.is_dynamic and (criteria_changed or dynamic_changed):
        # Clear existing devices first
        segment.devices = []
        db.add(segment)
        db.commit()
        
        # Repopulate
        populate_dynamic_segment(db, segment)
    
    return segment


def delete_segment(db: Session, segment_id: int) -> bool:
    """
    Delete a notification segment
    
    Args:
        db: Database session
        segment_id: ID of segment to delete
    
    Returns:
        True if deleted, False if not found
    """
    segment = db.query(NotificationSegment).filter(NotificationSegment.id == segment_id).first()
    
    if not segment:
        logger.warning(f"Segment with ID {segment_id} not found for deletion")
        return False
    
    logger.info(f"Deleting notification segment '{segment.name}' (ID: {segment_id})")
    
    # Remove all associations first
    segment.devices = []
    db.add(segment)
    db.commit()
    
    # Delete segment
    db.delete(segment)
    db.commit()
    
    return True


def get_segment(db: Session, segment_id: int) -> Optional[NotificationSegment]:
    """
    Get a notification segment by ID
    
    Args:
        db: Database session
        segment_id: ID of segment to retrieve
    
    Returns:
        NotificationSegment if found, None otherwise
    """
    return db.query(NotificationSegment).filter(NotificationSegment.id == segment_id).first()


def get_segments(db: Session, skip: int = 0, limit: int = 100) -> List[NotificationSegment]:
    """
    Get all notification segments with pagination
    
    Args:
        db: Database session
        skip: Number of segments to skip
        limit: Maximum number of segments to return
    
    Returns:
        List of NotificationSegment instances
    """
    return db.query(NotificationSegment).offset(skip).limit(limit).all()


def get_segment_by_name(db: Session, name: str) -> Optional[NotificationSegment]:
    """
    Get a notification segment by name
    
    Args:
        db: Database session
        name: Name of segment to retrieve
    
    Returns:
        NotificationSegment if found, None otherwise
    """
    return db.query(NotificationSegment).filter(NotificationSegment.name == name).first()


def assign_devices_to_segment(
    db: Session, 
    segment_id: int, 
    device_ids: List[int]
) -> Tuple[int, int]:
    """
    Assign multiple devices to a segment
    
    Args:
        db: Database session
        segment_id: ID of segment to assign to
        device_ids: List of device IDs to assign
    
    Returns:
        Tuple of (number of successful assignments, number of failed assignments)
    """
    segment = db.query(NotificationSegment).filter(NotificationSegment.id == segment_id).first()
    
    if not segment:
        logger.warning(f"Segment with ID {segment_id} not found for device assignment")
        return 0, len(device_ids)
    
    # Get all valid devices
    devices = db.query(Device).filter(Device.id.in_(device_ids)).all()
    
    # Add each device to segment
    success_count = 0
    for device in devices:
        if device not in segment.devices:
            segment.devices.append(device)
            success_count += 1
    
    db.add(segment)
    db.commit()
    
    logger.info(f"Assigned {success_count} devices to segment '{segment.name}' (ID: {segment_id})")
    
    return success_count, len(device_ids) - success_count


def remove_devices_from_segment(
    db: Session, 
    segment_id: int, 
    device_ids: List[int]
) -> Tuple[int, int]:
    """
    Remove multiple devices from a segment
    
    Args:
        db: Database session
        segment_id: ID of segment to remove from
        device_ids: List of device IDs to remove
    
    Returns:
        Tuple of (number of successful removals, number of failed removals)
    """
    segment = db.query(NotificationSegment).filter(NotificationSegment.id == segment_id).first()
    
    if not segment:
        logger.warning(f"Segment with ID {segment_id} not found for device removal")
        return 0, len(device_ids)
    
    # Get all valid devices that are in this segment
    devices = db.query(Device).join(
        Device.segments
    ).filter(
        Device.id.in_(device_ids),
        NotificationSegment.id == segment_id
    ).all()
    
    # Remove each device from segment
    success_count = 0
    for device in devices:
        segment.devices.remove(device)
        success_count += 1
    
    db.add(segment)
    db.commit()
    
    logger.info(f"Removed {success_count} devices from segment '{segment.name}' (ID: {segment_id})")
    
    return success_count, len(device_ids) - success_count


def populate_dynamic_segment(db: Session, segment: NotificationSegment) -> int:
    """
    Populate a dynamic segment based on its criteria
    
    Args:
        db: Database session
        segment: NotificationSegment instance
    
    Returns:
        Number of devices added to segment
    """
    if not segment.is_dynamic or not segment.criteria:
        logger.warning(f"Cannot populate non-dynamic segment or segment without criteria: {segment.name}")
        return 0
    
    # Log operation using secure approach for sensitive data
    logger.info(f"Populating dynamic segment '{segment.name}' (ID: {segment.id})")
    
    criteria = segment.criteria
    query = db.query(Device)
    
    # Build query based on criteria
    for key, value in criteria.items():
        if key == "device_type":
            if isinstance(value, list):
                query = query.filter(Device.device_type.in_(value))
            else:
                query = query.filter(Device.device_type == value)
        
        elif key == "language":
            if isinstance(value, list):
                query = query.filter(Device.language.in_(value))
            else:
                query = query.filter(Device.language == value)
        
        elif key == "timezone":
            if isinstance(value, list):
                query = query.filter(Device.timezone.in_(value))
            else:
                query = query.filter(Device.timezone == value)
        
        # For other criteria, we need to check in metadata JSON field
        # This varies by database type, using a more generic approach
        elif key == "metadata":
            # Handle nested metadata criteria (varies by database)
            for meta_key, meta_value in value.items():
                if isinstance(meta_value, list):
                    # This JSON path query is database-specific and may need adjustment
                    # Here using a generic approach that works for PostgreSQL
                    query = query.filter(Device.metadata[meta_key].astext.in_(meta_value))
                else:
                    query = query.filter(Device.metadata[meta_key].astext == str(meta_value))
    
    # Get matching devices
    matching_devices = query.all()
    
    # Clear existing devices and add matching ones
    segment.devices = matching_devices
    
    db.add(segment)
    db.commit()
    
    logger.info(f"Added {len(matching_devices)} devices to dynamic segment '{segment.name}'")
    
    return len(matching_devices)


def update_dynamic_segments_for_device(db: Session, device: Device) -> int:
    """
    Update all dynamic segments for a specific device
    Called when a device is updated to ensure it's in all matching segments
    
    Args:
        db: Database session
        device: Device instance
    
    Returns:
        Number of segments updated
    """
    # Get all dynamic segments
    dynamic_segments = db.query(NotificationSegment).filter(NotificationSegment.is_dynamic == True).all()
    
    if not dynamic_segments:
        return 0
    
    # Create a secure log entry
    logger.info(f"Updating dynamic segments for device ID: {device.id}")
    
    segments_added = 0
    segments_removed = 0
    
    for segment in dynamic_segments:
        # Check if device matches segment criteria
        if segment.evaluate_device(device):
            # If not already in segment, add it
            if device not in segment.devices:
                segment.devices.append(device)
                segments_added += 1
                db.add(segment)
        else:
            # If in segment but doesn't match criteria, remove it
            if device in segment.devices:
                segment.devices.remove(device)
                segments_removed += 1
                db.add(segment)
    
    if segments_added > 0 or segments_removed > 0:
        db.commit()
    
    logger.info(f"Device ID {device.id} added to {segments_added} segments and removed from {segments_removed} segments")
    
    return segments_added + segments_removed


def get_segment_devices(db: Session, segment_id: int, skip: int = 0, limit: int = 100) -> List[Device]:
    """
    Get all devices in a segment with pagination
    
    Args:
        db: Database session
        segment_id: ID of segment to get devices for
        skip: Number of devices to skip
        limit: Maximum number of devices to return
    
    Returns:
        List of Device instances
    """
    segment = db.query(NotificationSegment).filter(NotificationSegment.id == segment_id).first()
    
    if not segment:
        return []
    
    return db.query(Device).join(
        Device.segments
    ).filter(
        NotificationSegment.id == segment_id
    ).offset(skip).limit(limit).all()


def get_device_segments(db: Session, device_id: int) -> List[NotificationSegment]:
    """
    Get all segments a device belongs to
    
    Args:
        db: Database session
        device_id: ID of device to get segments for
    
    Returns:
        List of NotificationSegment instances
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    
    if not device:
        return []
    
    return device.segments
