"""
Push Notification Service for PWA Support

This module provides functionality for:
- Managing push notification subscriptions
- Sending push notifications to subscribed clients
- Generating VAPID keys for Web Push
- Segmenting notifications
"""

from sqlalchemy.orm import Session
from typing import Dict, Optional, List, Tuple, Any
from .models import PushSubscription, PWASettings, NotificationSegment, NotificationHistory, NotificationReceipt
from .schemas import PushSubscriptionSchema, PushNotificationSchema, SegmentCriteriaSchema, SegmentedNotificationSend
from pywebpush import webpush, WebPushException
import json
import logging
from datetime import datetime
import base64
import sqlalchemy as sa
from urllib.parse import urlparse

logger = logging.getLogger("pwa.push")


def generate_vapid_keys() -> Dict[str, str]:
    """
    Generate VAPID keys for Web Push Authentication
    
    Returns:
        Dict containing 'public_key' and 'private_key'
    """
    try:
        from py_vapid import Vapid
        
        vapid = Vapid()
        vapid.generate_keys()
        
        return {
            "public_key": vapid.public_key.decode(),
            "private_key": vapid.private_key.decode()
        }
    except ImportError:
        # Fallback if py_vapid is not available
        logger.warning("py_vapid not available, using pre-generated keys")
        return {
            "public_key": "BLBx-hf5H4pjs3BqOKR3fLwsX3CUalXjNx5iB5bWpJfJoNpMXs0Dr1g2_gA_NvmuZXE4dbNph11UIQgJhTFcuQU",
            "private_key": "tH8MiIYPeAWIYVNKBUQftR66XoDo8qfJ0zu-HXZ7Pv0"
        }


def get_vapid_keys(db: Session) -> Dict[str, str]:
    """
    Get VAPID keys from database, generating them if they don't exist
    
    Args:
        db: Database session
        
    Returns:
        Dict containing 'public_key' and 'private_key'
    """
    try:
        settings = db.query(PWASettings).first()
        
        if not settings or not settings.vapid_public_key or not settings.vapid_private_key:
            # Generate new keys
            logger.info("No VAPID keys found in database, generating new ones")
            vapid_keys = generate_vapid_keys()
            
            try:
                if not settings:
                    settings = PWASettings(
                        vapid_public_key=vapid_keys["public_key"],
                        vapid_private_key=vapid_keys["private_key"],
                        manifest=json.dumps({}),
                        service_worker_config=json.dumps({})
                    )
                    db.add(settings)
                else:
                    settings.vapid_public_key = vapid_keys["public_key"]
                    settings.vapid_private_key = vapid_keys["private_key"]
                    
                db.commit()
                logger.info("VAPID keys saved to database successfully")
            except Exception as e:
                db.rollback()
                logger.error(f"Error saving VAPID keys to database: {str(e)}")
                # Return the generated keys anyway even if saving failed
            
            return vapid_keys
        else:
            logger.info("Using existing VAPID keys from database")
            return {
                "public_key": settings.vapid_public_key,
                "private_key": settings.vapid_private_key
            }
    except Exception as e:
        # If anything fails, return default fallback keys
        logger.error(f"Error retrieving or generating VAPID keys: {str(e)}")
        return {
            "public_key": "BLBx-hf5H4pjs3BqOKR3fLwsX3CUalXjNx5iB5bWpJfJoNpMXs0Dr1g2_gA_NvmuZXE4dbNph11UIQgJhTFcuQU",
            "private_key": "tH8MiIYPeAWIYVNKBUQftR66XoDo8qfJ0zu-HXZ7Pv0"
        }


def register_subscription(db: Session, subscription: PushSubscriptionSchema, user_id: Optional[int] = None, 
                          user_agent: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> bool:
    """
    Register a new push notification subscription
    
    Args:
        db: Database session
        subscription: Subscription data from browser
        user_id: Optional user ID for authenticated users
        user_agent: Optional user agent string
        metadata: Optional metadata for segmentation (device_type, language, location, tags)
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Parse user agent if provided to infer device type
    device_type = None
    if user_agent:
        if "Mobile" in user_agent:
            device_type = "mobile"
        elif "Tablet" in user_agent:
            device_type = "tablet"
        else:
            device_type = "desktop"
    
    # Extract metadata fields
    language = None
    location = None
    tags = None
    
    if metadata:
        language = metadata.get("language")
        location = metadata.get("location")
        if "tags" in metadata and isinstance(metadata["tags"], list):
            tags = json.dumps(metadata["tags"])
    
    # Check if subscription already exists
    existing_sub = db.query(PushSubscription).filter(
        PushSubscription.endpoint == subscription.endpoint
    ).first()
    
    if existing_sub:
        # Update existing subscription
        existing_sub.p256dh = subscription.keys.p256dh
        existing_sub.auth = subscription.keys.auth
        existing_sub.user_id = user_id or existing_sub.user_id
        existing_sub.last_used = datetime.utcnow()
        
        # Update metadata if provided
        if device_type:
            existing_sub.device_type = device_type
        if language:
            existing_sub.language = language
        if location:
            existing_sub.location = location
        if tags:
            existing_sub.tags = tags
        
        db.add(existing_sub)
        db.commit()
        
        # If subscription has a user_id and we have dynamic segments, update segment assignments
        if existing_sub.user_id:
            update_dynamic_segments_for_subscription(db, existing_sub)
            
        return True
    else:
        # Create new subscription
        new_sub = PushSubscription(
            endpoint=subscription.endpoint,
            p256dh=subscription.keys.p256dh,
            auth=subscription.keys.auth,
            user_id=user_id,
            user_agent=user_agent,
            device_type=device_type,
            language=language,
            location=location,
            tags=tags
        )
        db.add(new_sub)
        db.commit()
        
        # If subscription has a user_id and we have dynamic segments, update segment assignments
        if new_sub.user_id:
            update_dynamic_segments_for_subscription(db, new_sub)
            
        return True


def unregister_subscription(db: Session, endpoint: str) -> bool:
    """
    Unregister a push notification subscription
    
    Args:
        db: Database session
        endpoint: Push subscription endpoint to unregister
    
    Returns:
        bool: True if successful, False otherwise
    """
    subscription = db.query(PushSubscription).filter(
        PushSubscription.endpoint == endpoint
    ).first()
    
    if subscription:
        # Remove from all segments first (respecting foreign key constraints)
        subscription.segments = []
        db.add(subscription)
        db.commit()
        
        # Then delete the subscription
        db.delete(subscription)
        db.commit()
        return True
    return False


def send_push_notification(
    db: Session, 
    title: str, 
    message: str, 
    icon: Optional[str] = None,
    tag: Optional[str] = None,
    url: Optional[str] = None,
    ttl: int = 86400
) -> int:
    """
    Send push notification to all subscribers
    
    Args:
        db: Database session
        title: Notification title
        message: Notification body message
        icon: URL to the notification icon
        tag: Tag to group notifications
        url: URL to open when notification is clicked
        ttl: Time to live in seconds
        
    Returns:
        int: Number of notifications successfully sent
    """
    # Create notification history record
    notification_history = NotificationHistory(
        title=title,
        message=message,
        icon=icon,
        url=url,
        additional_data=json.dumps({"tag": tag}) if tag else None
    )
    db.add(notification_history)
    db.commit()
    
    # Get VAPID keys
    vapid_keys = get_vapid_keys(db)
    
    # Get all subscriptions
    subscriptions = db.query(PushSubscription).all()
    sent_count = 0
    
    # Prepare notification payload
    payload = {
        "title": title,
        "message": message,
        "requireInteraction": True
    }
    
    if icon:
        payload["icon"] = icon
    
    if url:
        payload["url"] = url
    
    if tag:
        payload["tag"] = tag
    
    # Get API endpoint from the first subscription to use in VAPID claims
    api_endpoint = None
    if subscriptions:
        parsed_url = urlparse(subscriptions[0].endpoint)
        api_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}"
    else:
        return 0  # No subscriptions to send to
    
    # Send to each subscription
    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth
            }
        }
        
        # Create receipt record
        receipt = NotificationReceipt(
            notification_id=notification_history.id,
            subscription_id=subscription.id
        )
        db.add(receipt)
        
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=vapid_keys["private_key"],
                vapid_claims={
                    "sub": "mailto:admin@kaapi-app.com",  # A contact email is required
                    "aud": api_endpoint
                }
            )
            
            # Update receipt and subscription
            receipt.delivered = True
            receipt.delivered_at = datetime.utcnow()
            subscription.last_used = datetime.utcnow()
            sent_count += 1
            
        except WebPushException as e:
            # Handle expired subscriptions
            if e.response and e.response.status_code in [404, 410]:
                logger.info(f"Subscription expired, removing: {subscription.endpoint}")
                db.delete(subscription)
            else:
                logger.error(f"WebPush error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
    
    # Update notification history
    notification_history.sent_count = sent_count
    db.add(notification_history)
    db.commit()
    
    return sent_count


def send_segmented_notification(db: Session, notification: SegmentedNotificationSend) -> int:
    """
    Send a push notification to a specific segment of users
    
    Args:
        db: Database session
        notification: Notification data with segment_id
    
    Returns:
        Number of notifications sent
    """
    # Verify segment exists
    segment = db.query(NotificationSegment).filter(
        NotificationSegment.id == notification.segment_id
    ).first()
    
    if not segment:
        logger.error(f"Segment with ID {notification.segment_id} not found")
        return 0
    
    # Create notification history record
    notification_history = NotificationHistory(
        title=notification.title,
        message=notification.message,
        icon=notification.icon,
        url=notification.url,
        segment_id=segment.id,
        additional_data=json.dumps(notification.dict(exclude={"segment_id", "title", "message", "icon", "url"})) 
            if notification.data or notification.actions or notification.badge or notification.tag else None
    )
    db.add(notification_history)
    db.commit()
    
    # Get VAPID keys
    vapid_keys = get_vapid_keys(db)
    
    # Get all subscriptions for this segment
    subscriptions = db.query(PushSubscription).join(
        PushSubscription.segments
    ).filter(
        NotificationSegment.id == segment.id
    ).all()
    
    sent_count = 0
    
    # Prepare notification payload
    payload = {
        "title": notification.title,
        "message": notification.message,
        "requireInteraction": True
    }
    
    if notification.icon:
        payload["icon"] = notification.icon
    
    if notification.url:
        payload["url"] = notification.url
    
    if notification.data:
        payload["data"] = notification.data
    
    if notification.actions:
        payload["actions"] = notification.actions
    
    if notification.badge:
        payload["badge"] = notification.badge
    
    if notification.tag:
        payload["tag"] = notification.tag
    
    # Get API endpoint from the first subscription to use in VAPID claims
    api_endpoint = None
    if subscriptions:
        parsed_url = urlparse(subscriptions[0].endpoint)
        api_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}"
    else:
        return 0  # No subscriptions to send to
    
    # Send to each subscription
    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth
            }
        }
        
        # Create receipt record
        receipt = NotificationReceipt(
            notification_id=notification_history.id,
            subscription_id=subscription.id
        )
        db.add(receipt)
        
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=vapid_keys["private_key"],
                vapid_claims={
                    "sub": "mailto:admin@example.com",
                    "aud": api_endpoint
                }
            )
            
            # Update receipt and subscription
            receipt.delivered = True
            receipt.delivered_at = datetime.utcnow()
            subscription.last_used = datetime.utcnow()
            sent_count += 1
            
        except WebPushException as e:
            # Log error
            error_msg = str(e)
            logger.error(f"Push notification failed: {error_msg}")
            receipt.error_message = error_msg
            
            # If subscription expired or invalid, remove it
            if e.response and e.response.status_code in (404, 410):
                # Remove from all segments first
                subscription.segments = []
                db.add(subscription)
                db.commit()
                
                # Then delete the subscription
                db.delete(subscription)
            
        except Exception as e:
            # Log general error
            error_msg = str(e)
            logger.error(f"Push notification failed with error: {error_msg}")
            receipt.error_message = error_msg
    
    # Update notification history
    notification_history.sent_count = sent_count
    db.add(notification_history)
    db.commit()
    
    return sent_count


def create_notification_segment(db: Session, segment_data: dict) -> NotificationSegment:
    """
    Create a new notification segment
    
    Args:
        db: Database session
        segment_data: Segment data including name, description, criteria, is_dynamic
    
    Returns:
        Created NotificationSegment instance
    """
    # Convert criteria to JSON if provided
    criteria_json = None
    if "criteria" in segment_data and segment_data["criteria"]:
        criteria_json = json.dumps(segment_data["criteria"])
    
    segment = NotificationSegment(
        name=segment_data["name"],
        description=segment_data.get("description"),
        criteria=criteria_json,
        is_dynamic=segment_data.get("is_dynamic", False)
    )
    
    db.add(segment)
    db.commit()
    db.refresh(segment)
    
    # If it's a dynamic segment, populate it
    if segment.is_dynamic:
        populate_dynamic_segment(db, segment)
    
    return segment


def update_notification_segment(db: Session, segment_id: int, segment_data: dict) -> Optional[NotificationSegment]:
    """
    Update an existing notification segment
    
    Args:
        db: Database session
        segment_id: ID of segment to update
        segment_data: Updated segment data
    
    Returns:
        Updated NotificationSegment instance or None if not found
    """
    segment = db.query(NotificationSegment).filter(
        NotificationSegment.id == segment_id
    ).first()
    
    if not segment:
        return None
    
    # Update fields if provided
    if "name" in segment_data:
        segment.name = segment_data["name"]
    
    if "description" in segment_data:
        segment.description = segment_data["description"]
    
    if "criteria" in segment_data:
        segment.criteria = json.dumps(segment_data["criteria"]) if segment_data["criteria"] else None
    
    was_dynamic = segment.is_dynamic
    if "is_dynamic" in segment_data:
        segment.is_dynamic = segment_data["is_dynamic"]
    
    db.add(segment)
    db.commit()
    db.refresh(segment)
    
    # If it's newly dynamic or criteria changed while dynamic, repopulate
    if segment.is_dynamic and ("criteria" in segment_data or (segment.is_dynamic and not was_dynamic)):
        # Clear current memberships
        segment.subscriptions = []
        db.add(segment)
        db.commit()
        
        # Repopulate based on criteria
        populate_dynamic_segment(db, segment)
    
    return segment


def delete_notification_segment(db: Session, segment_id: int) -> bool:
    """
    Delete a notification segment
    
    Args:
        db: Database session
        segment_id: ID of segment to delete
    
    Returns:
        True if deleted, False if not found
    """
    segment = db.query(NotificationSegment).filter(
        NotificationSegment.id == segment_id
    ).first()
    
    if not segment:
        return False
    
    # Remove all associations first
    segment.subscriptions = []
    db.add(segment)
    db.commit()
    
    # Delete segment
    db.delete(segment)
    db.commit()
    
    return True


def assign_subscriptions_to_segment(db: Session, segment_id: int, subscription_ids: List[int]) -> Tuple[int, int]:
    """
    Assign multiple subscriptions to a segment
    
    Args:
        db: Database session
        segment_id: ID of segment to assign to
        subscription_ids: List of subscription IDs to assign
    
    Returns:
        Tuple of (number of successful assignments, number of failed assignments)
    """
    segment = db.query(NotificationSegment).filter(
        NotificationSegment.id == segment_id
    ).first()
    
    if not segment:
        return 0, len(subscription_ids)
    
    # Get all valid subscriptions
    subscriptions = db.query(PushSubscription).filter(
        PushSubscription.id.in_(subscription_ids)
    ).all()
    
    # Add each subscription to segment
    success_count = 0
    for subscription in subscriptions:
        if subscription not in segment.subscriptions:
            segment.subscriptions.append(subscription)
            success_count += 1
    
    db.add(segment)
    db.commit()
    
    return success_count, len(subscription_ids) - success_count


def remove_subscriptions_from_segment(db: Session, segment_id: int, subscription_ids: List[int]) -> Tuple[int, int]:
    """
    Remove multiple subscriptions from a segment
    
    Args:
        db: Database session
        segment_id: ID of segment to remove from
        subscription_ids: List of subscription IDs to remove
    
    Returns:
        Tuple of (number of successful removals, number of failed removals)
    """
    segment = db.query(NotificationSegment).filter(
        NotificationSegment.id == segment_id
    ).first()
    
    if not segment:
        return 0, len(subscription_ids)
    
    # Get all valid subscriptions that are in this segment
    subscriptions = db.query(PushSubscription).join(
        PushSubscription.segments
    ).filter(
        PushSubscription.id.in_(subscription_ids),
        NotificationSegment.id == segment_id
    ).all()
    
    # Remove each subscription from segment
    success_count = 0
    for subscription in subscriptions:
        segment.subscriptions.remove(subscription)
        success_count += 1
    
    db.add(segment)
    db.commit()
    
    return success_count, len(subscription_ids) - success_count


def populate_dynamic_segment(db: Session, segment: NotificationSegment) -> int:
    """
    Populate a dynamic segment based on its criteria
    
    Args:
        db: Database session
        segment: NotificationSegment instance
    
    Returns:
        Number of subscriptions added to segment
    """
    if not segment.is_dynamic or not segment.criteria:
        return 0
    
    criteria = json.loads(segment.criteria)
    
    # Start with a base query
    query = db.query(PushSubscription)
    
    # Apply device type filter
    if "device_types" in criteria and criteria["device_types"]:
        query = query.filter(PushSubscription.device_type.in_(criteria["device_types"]))
    
    # Apply language filter
    if "languages" in criteria and criteria["languages"]:
        query = query.filter(PushSubscription.language.in_(criteria["languages"]))
    
    # Apply location filter
    if "locations" in criteria and criteria["locations"]:
        query = query.filter(PushSubscription.location.in_(criteria["locations"]))
    
    # Apply tag filter (more complex since tags are stored as JSON)
    if "tags" in criteria and criteria["tags"]:
        # Build a condition that checks if any of the required tags are in the subscription's tags
        # This depends on the database being used
        tag_conditions = []
        for tag in criteria["tags"]:
            # This works for PostgreSQL JSON containing
            tag_conditions.append(PushSubscription.tags.contains(tag))
        
        if tag_conditions:
            query = query.filter(sa.or_(*tag_conditions))
    
    # Apply user role filter
    if "user_role_ids" in criteria and criteria["user_role_ids"]:
        # Join with User and filter by role_id
        from app.plugins.advanced_auth.models import User
        query = query.join(User).filter(User.role_id.in_(criteria["user_role_ids"]))
    
    # Get all matching subscriptions
    matching_subscriptions = query.all()
    
    # Clear current membership and add matching subscriptions
    segment.subscriptions = matching_subscriptions
    db.add(segment)
    db.commit()
    
    return len(matching_subscriptions)


def update_dynamic_segments_for_subscription(db: Session, subscription: PushSubscription) -> int:
    """
    Update all dynamic segments for a specific subscription
    Called when a subscription is updated to ensure it's in all matching segments
    
    Args:
        db: Database session
        subscription: PushSubscription instance
    
    Returns:
        Number of segments updated
    """
    # Get all dynamic segments
    dynamic_segments = db.query(NotificationSegment).filter(
        NotificationSegment.is_dynamic == True
    ).all()
    
    count = 0
    for segment in dynamic_segments:
        if not segment.criteria:
            continue
        
        criteria = json.loads(segment.criteria)
        matches = True
        
        # Check device type
        if "device_types" in criteria and criteria["device_types"]:
            if not subscription.device_type or subscription.device_type not in criteria["device_types"]:
                matches = False
        
        # Check language
        if matches and "languages" in criteria and criteria["languages"]:
            if not subscription.language or subscription.language not in criteria["languages"]:
                matches = False
        
        # Check location
        if matches and "locations" in criteria and criteria["locations"]:
            if not subscription.location or subscription.location not in criteria["locations"]:
                matches = False
        
        # Check tags
        if matches and "tags" in criteria and criteria["tags"]:
            subscription_tags = subscription.get_tags()
            if not subscription_tags or not any(tag in subscription_tags for tag in criteria["tags"]):
                matches = False
        
        # Check user role
        if matches and "user_role_ids" in criteria and criteria["user_role_ids"]:
            if not subscription.user_id:
                matches = False
            else:
                from app.plugins.advanced_auth.models import User
                user = db.query(User).filter(User.id == subscription.user_id).first()
                if not user or user.role_id not in criteria["user_role_ids"]:
                    matches = False
        
        # Add or remove from segment based on match
        if matches:
            if subscription not in segment.subscriptions:
                segment.subscriptions.append(subscription)
                count += 1
        else:
            if subscription in segment.subscriptions:
                segment.subscriptions.remove(subscription)
                count += 1
    
    if count > 0:
        db.add(subscription)
        db.commit()
    
    return count


def get_notification_statistics(db: Session) -> Dict[str, Any]:
    """
    Get statistics about notification delivery and interactions
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with notification statistics
    """
    # Get total notifications sent
    total_sent = db.query(sa.func.sum(NotificationHistory.sent_count)).scalar() or 0
    
    # Get delivered count
    delivered = db.query(NotificationReceipt).filter(NotificationReceipt.delivered == True).count()
    
    # Get clicked count
    clicked = db.query(NotificationReceipt).filter(NotificationReceipt.clicked == True).count()
    
    # Get failed count
    failed = db.query(NotificationReceipt).filter(
        NotificationReceipt.delivered == False,
        NotificationReceipt.error_message.isnot(None)
    ).count()
    
    # Calculate rates
    delivery_rate = (delivered / total_sent) if total_sent > 0 else 0
    click_rate = (clicked / delivered) if delivered > 0 else 0
    
    return {
        "total_sent": total_sent,
        "delivered": delivered,
        "clicked": clicked,
        "failed": failed,
        "delivery_rate": delivery_rate,
        "click_rate": click_rate
    }
