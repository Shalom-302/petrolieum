"""
Notification Service

Integrates with the push_notifications plugin to deliver notifications to users.
This service handles:
- Converting activity events to notifications
- Sending notifications through the push_notifications service
- Tracking notification delivery and read status
- Respecting user notification preferences
"""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, time
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import IntegrityError

from ..models.database import (
    ActivityEvent,
    NotificationRecord,
    UserPreference,
    SubscriptionCategory,
    ActivityType
)
from ..schemas.subscription import (
    NotificationRecordCreate,
    NotificationRecordUpdate,
    UserPreferenceCreate,
    UserPreferenceUpdate,
    UserPreferenceResponse
)
from ..handlers.security_handler import SecurityHandler
from .activity_service import ActivityService

# Import the needed components from the push_notifications plugin
try:
    from app.plugins.push_notifications.main import push_notifications_service
    from app.plugins.push_notifications.models.database import NotificationDevice
    from app.plugins.push_notifications.schemas.notification import NotificationCreate
    PUSH_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    PUSH_NOTIFICATIONS_AVAILABLE = False
    logging.warning("Push notifications plugin not available. Some functionality will be limited.")

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling notifications related to social activities"""
    
    def __init__(
        self,
        security_handler: SecurityHandler,
        activity_service: ActivityService
    ):
        """
        Initialize the notification service
        
        Args:
            security_handler: Security handler for encryption and logging
            activity_service: Activity service for querying activities
        """
        self.security_handler = security_handler
        self.activity_service = activity_service
        logger.info("Notification service initialized")
    
    async def create_notification_record(
        self,
        db: Session,
        activity_id: int,
        recipient_id: str,
        notification_id: Optional[str] = None,
        status: str = "pending"
    ) -> NotificationRecord:
        """
        Create a record of a notification
        
        Args:
            db: Database session
            activity_id: ID of the activity
            recipient_id: ID of the recipient
            notification_id: Optional ID from push notification service
            status: Status of the notification
            
        Returns:
            Created notification record
            
        Raises:
            ValueError: If notification record creation fails
        """
        # Check if record already exists
        existing = db.query(NotificationRecord).filter(
            NotificationRecord.activity_id == activity_id,
            NotificationRecord.recipient_id == recipient_id
        ).first()
        
        if existing:
            # Update existing record
            existing.notification_id = notification_id or existing.notification_id
            existing.status = status
            
            if status == "sent" and not existing.sent_at:
                existing.sent_at = datetime.utcnow()
                
            if status == "delivered" and not existing.delivered_at:
                existing.delivered_at = datetime.utcnow()
                
            if status == "read" and not existing.read_at:
                existing.read_at = datetime.utcnow()
                
            db.commit()
            db.refresh(existing)
            
            self.security_handler.log_notification_event(
                "update", 
                activity_id, 
                recipient_id,
                status
            )
            
            return existing
        
        # Create new record
        new_record = NotificationRecord(
            activity_id=activity_id,
            recipient_id=recipient_id,
            notification_id=notification_id,
            status=status
        )
        
        if status == "sent":
            new_record.sent_at = datetime.utcnow()
            
        if status == "delivered":
            new_record.delivered_at = datetime.utcnow()
            
        if status == "read":
            new_record.read_at = datetime.utcnow()
        
        try:
            db.add(new_record)
            db.commit()
            db.refresh(new_record)
            
            self.security_handler.log_notification_event(
                "create", 
                activity_id, 
                recipient_id,
                status
            )
            
            return new_record
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Error creating notification record: {e}")
            raise ValueError("Failed to create notification record")
    
    async def update_notification_record(
        self,
        db: Session,
        record_id: int,
        data: NotificationRecordUpdate
    ) -> NotificationRecord:
        """
        Update a notification record
        
        Args:
            db: Database session
            record_id: ID of the record
            data: Update data
            
        Returns:
            Updated notification record
            
        Raises:
            ValueError: If notification record does not exist
        """
        record = db.query(NotificationRecord).filter(
            NotificationRecord.id == record_id
        ).first()
        
        if not record:
            raise ValueError("Notification record not found")
        
        # Update fields
        if data.notification_id is not None:
            record.notification_id = data.notification_id
            
        if data.status is not None:
            record.status = data.status
            
            if data.status == "sent" and not record.sent_at:
                record.sent_at = data.sent_at or datetime.utcnow()
                
            if data.status == "delivered" and not record.delivered_at:
                record.delivered_at = data.delivered_at or datetime.utcnow()
                
            if data.status == "read" and not record.read_at:
                record.read_at = data.read_at or datetime.utcnow()
        else:
            # Update timestamps if provided
            if data.sent_at is not None:
                record.sent_at = data.sent_at
                
            if data.delivered_at is not None:
                record.delivered_at = data.delivered_at
                
            if data.read_at is not None:
                record.read_at = data.read_at
        
        try:
            db.commit()
            db.refresh(record)
            
            self.security_handler.log_notification_event(
                "update", 
                record.activity_id, 
                record.recipient_id,
                record.status
            )
            
            return record
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating notification record: {e}")
            raise ValueError("Failed to update notification record")
    
    async def get_notification_records(
        self,
        db: Session,
        recipient_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[NotificationRecord]:
        """
        Get notification records for a recipient
        
        Args:
            db: Database session
            recipient_id: ID of the recipient
            status: Optional status filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of notification records
        """
        query = db.query(NotificationRecord).filter(
            NotificationRecord.recipient_id == recipient_id
        )
        
        if status:
            query = query.filter(NotificationRecord.status == status)
        
        return query.order_by(desc(NotificationRecord.created_at)).offset(skip).limit(limit).all()
    
    async def mark_notification_as_read(
        self,
        db: Session,
        record_id: int,
        recipient_id: str
    ) -> bool:
        """
        Mark a notification as read
        
        Args:
            db: Database session
            record_id: ID of the notification record
            recipient_id: ID of the recipient (for validation)
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ValueError: If notification doesn't exist or doesn't belong to the recipient
        """
        record = db.query(NotificationRecord).filter(
            NotificationRecord.id == record_id,
            NotificationRecord.recipient_id == recipient_id
        ).first()
        
        if not record:
            raise ValueError("Notification not found or doesn't belong to the recipient")
        
        record.status = "read"
        record.read_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(record)
            
            self.security_handler.log_notification_event(
                "read", 
                record.activity_id, 
                recipient_id,
                "read"
            )
            
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking notification as read: {e}")
            return False
    
    async def get_user_preferences(
        self,
        db: Session,
        user_id: str
    ) -> UserPreferenceResponse:
        """
        Get user notification preferences
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            User preferences
        """
        user_pref = db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if not user_pref:
            # Return default preferences
            return UserPreferenceResponse(
                user_id=user_id,
                enabled_categories=["mention", "follow", "post", "comment", "reaction", "update"],
                quiet_hours={"enabled": False, "start": "22:00", "end": "07:00", "timezone": "UTC"},
                feed_preferences={"sort": "chronological", "show_read": False}
            )
        
        # Log access to user preferences for security auditing
        self.security_handler.log_access_event("read_preferences", user_id)
        
        return UserPreferenceResponse.from_orm(user_pref)
    
    async def create_user_preferences(
        self,
        db: Session,
        user_id: str,
        data: UserPreferenceCreate
    ) -> UserPreferenceResponse:
        """
        Create or update user notification preferences
        
        Args:
            db: Database session
            user_id: User ID
            data: User preference data
            
        Returns:
            Created or updated user preferences
            
        Raises:
            ValueError: If preference creation fails
        """
        # Check if preferences already exist
        existing = db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if existing:
            # Update existing preferences
            if data.enabled_categories is not None:
                existing.enabled_categories = data.enabled_categories
            
            if data.quiet_hours is not None:
                existing.quiet_hours = data.quiet_hours
            
            if data.feed_preferences is not None:
                existing.feed_preferences = data.feed_preferences
            
            try:
                db.commit()
                db.refresh(existing)
                
                # Log update event
                self.security_handler.log_modification_event(
                    "update_preferences", 
                    user_id,
                    {"categories": len(data.enabled_categories) if data.enabled_categories else 0}
                )
                
                logger.info(f"Updated user preferences for user {user_id}")
                return UserPreferenceResponse.from_orm(existing)
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating user preferences: {e}")
                raise ValueError("Failed to update user preferences")
        
        # Create new preferences
        new_pref = UserPreference(
            user_id=user_id,
            enabled_categories=data.enabled_categories,
            quiet_hours=data.quiet_hours,
            feed_preferences=data.feed_preferences
        )
        
        try:
            db.add(new_pref)
            db.commit()
            db.refresh(new_pref)
            
            # Log creation event
            self.security_handler.log_modification_event(
                "create_preferences", 
                user_id,
                {"categories": len(data.enabled_categories) if data.enabled_categories else 0}
            )
            
            logger.info(f"Created user preferences for user {user_id}")
            return UserPreferenceResponse.from_orm(new_pref)
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Error creating user preferences: {e}")
            raise ValueError("Failed to create user preferences")
    
    async def update_user_preferences(
        self,
        db: Session,
        user_id: str,
        data: UserPreferenceUpdate
    ) -> UserPreferenceResponse:
        """
        Update user notification preferences
        
        Args:
            db: Database session
            user_id: User ID
            data: User preference update data
            
        Returns:
            Updated user preferences
            
        Raises:
            ValueError: If preference update fails
        """
        # Get existing preferences
        user_pref = db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if not user_pref:
            # Create new preferences if they don't exist
            user_pref = UserPreference(
                user_id=user_id,
                enabled_categories=data.enabled_categories or ["mention", "follow", "post", "comment", "reaction", "update"],
                quiet_hours=data.quiet_hours or {"enabled": False, "start": "22:00", "end": "07:00", "timezone": "UTC"},
                feed_preferences=data.feed_preferences or {"sort": "chronological", "show_read": False}
            )
            db.add(user_pref)
        else:
            # Update existing preferences
            if data.enabled_categories is not None:
                user_pref.enabled_categories = data.enabled_categories
            
            if data.quiet_hours is not None:
                user_pref.quiet_hours = data.quiet_hours
            
            if data.feed_preferences is not None:
                user_pref.feed_preferences = data.feed_preferences
        
        try:
            db.commit()
            db.refresh(user_pref)
            
            # Log update event
            self.security_handler.log_modification_event(
                "update_preferences", 
                user_id,
                {"categories": len(data.enabled_categories) if data.enabled_categories else 0}
            )
            
            logger.info(f"Updated user preferences for user {user_id}")
            return UserPreferenceResponse.from_orm(user_pref)
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user preferences: {e}")
            raise ValueError("Failed to update user preferences")
    
    async def set_quiet_hours(
        self,
        db: Session,
        user_id: str,
        quiet_hours: Dict[str, Any]
    ) -> UserPreferenceResponse:
        """
        Set quiet hours for notifications
        
        Args:
            db: Database session
            user_id: User ID
            quiet_hours: Quiet hours configuration
            
        Returns:
            Updated user preferences
            
        Raises:
            ValueError: If setting quiet hours fails
        """
        # Get existing preferences
        user_pref = db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if not user_pref:
            # Create new preferences if they don't exist
            user_pref = UserPreference(
                user_id=user_id,
                enabled_categories=["mention", "follow", "post", "comment", "reaction", "update"],
                quiet_hours=quiet_hours,
                feed_preferences={"sort": "chronological", "show_read": False}
            )
            db.add(user_pref)
        else:
            # Update quiet hours
            user_pref.quiet_hours = quiet_hours
        
        try:
            db.commit()
            db.refresh(user_pref)
            
            # Log quiet hours settings
            self.security_handler.log_modification_event(
                "set_quiet_hours", 
                user_id,
                {"enabled": quiet_hours.get("enabled", False)}
            )
            
            logger.info(f"Updated quiet hours for user {user_id}")
            return UserPreferenceResponse.from_orm(user_pref)
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating quiet hours: {e}")
            raise ValueError("Failed to update quiet hours")
    
    async def set_enabled_categories(
        self,
        db: Session,
        user_id: str,
        categories: List[str]
    ) -> UserPreferenceResponse:
        """
        Set enabled notification categories
        
        Args:
            db: Database session
            user_id: User ID
            categories: List of enabled categories
            
        Returns:
            Updated user preferences
            
        Raises:
            ValueError: If setting categories fails
        """
        # Get existing preferences
        user_pref = db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if not user_pref:
            # Create new preferences if they don't exist
            user_pref = UserPreference(
                user_id=user_id,
                enabled_categories=categories,
                quiet_hours={"enabled": False, "start": "22:00", "end": "07:00", "timezone": "UTC"},
                feed_preferences={"sort": "chronological", "show_read": False}
            )
            db.add(user_pref)
        else:
            # Update enabled categories
            user_pref.enabled_categories = categories
        
        try:
            db.commit()
            db.refresh(user_pref)
            
            # Log category settings with encryption for sensitive data
            self.security_handler.log_modification_event(
                "set_categories", 
                user_id,
                {"count": len(categories)}
            )
            
            logger.info(f"Updated enabled categories for user {user_id}")
            return UserPreferenceResponse.from_orm(user_pref)
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating enabled categories: {e}")
            raise ValueError("Failed to update enabled categories")
    
    async def set_feed_preferences(
        self,
        db: Session,
        user_id: str,
        feed_preferences: Dict[str, Any]
    ) -> UserPreferenceResponse:
        """
        Set feed display preferences
        
        Args:
            db: Database session
            user_id: User ID
            feed_preferences: Feed preferences configuration
            
        Returns:
            Updated user preferences
            
        Raises:
            ValueError: If setting feed preferences fails
        """
        # Get existing preferences
        user_pref = db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if not user_pref:
            # Create new preferences if they don't exist
            user_pref = UserPreference(
                user_id=user_id,
                enabled_categories=["mention", "follow", "post", "comment", "reaction", "update"],
                quiet_hours={"enabled": False, "start": "22:00", "end": "07:00", "timezone": "UTC"},
                feed_preferences=feed_preferences
            )
            db.add(user_pref)
        else:
            # Update feed preferences
            user_pref.feed_preferences = feed_preferences
        
        try:
            db.commit()
            db.refresh(user_pref)
            
            # Log feed preference settings
            self.security_handler.log_modification_event(
                "set_feed_preferences", 
                user_id,
                {"sort": feed_preferences.get("sort", "chronological")}
            )
            
            logger.info(f"Updated feed preferences for user {user_id}")
            return UserPreferenceResponse.from_orm(user_pref)
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating feed preferences: {e}")
            raise ValueError("Failed to update feed preferences")
    
    async def get_user_preference(
        self,
        db: Session,
        user_id: str
    ) -> Optional[UserPreference]:
        """
        Get user notification preferences
        
        Args:
            db: Database session
            user_id: ID of the user
            
        Returns:
            User preference object if found, None otherwise
        """
        return db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
    
    async def is_in_quiet_hours(
        self,
        user_preference: UserPreference
    ) -> bool:
        """
        Check if current time is within quiet hours for the user
        
        Args:
            user_preference: User preference object
            
        Returns:
            True if in quiet hours, False otherwise
        """
        if not user_preference or not user_preference.quiet_hours:
            return False
        
        quiet_hours = user_preference.quiet_hours
        if not quiet_hours.get("enabled", True):
            return False
        
        try:
            start_time_str = quiet_hours.get("start", "22:00")
            end_time_str = quiet_hours.get("end", "07:00")
            timezone_str = quiet_hours.get("timezone", "UTC")
            
            # This is a simplified check - a real implementation would use pytz
            # to handle timezone conversion properly
            now = datetime.utcnow()
            
            # Parse quiet hours
            start_hour, start_minute = map(int, start_time_str.split(":"))
            end_hour, end_minute = map(int, end_time_str.split(":"))
            
            start_time = time(start_hour, start_minute)
            end_time = time(end_hour, end_minute)
            current_time = now.time()
            
            # Check if current time is within quiet hours
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                # Handle case where quiet hours span midnight
                return current_time >= start_time or current_time <= end_time
                
        except Exception as e:
            logger.error(f"Error checking quiet hours: {e}")
            return False
    
    async def should_send_notification(
        self,
        db: Session,
        user_id: str,
        activity: ActivityEvent
    ) -> bool:
        """
        Check if a notification should be sent based on user preferences
        
        Args:
            db: Database session
            user_id: ID of the user
            activity: Activity event
            
        Returns:
            True if notification should be sent, False otherwise
        """
        # Get user preferences
        user_preference = await self.get_user_preference(db, user_id)
        
        # If no preferences are set, use default settings (allow all notifications)
        if not user_preference:
            return True
        
        # Check if the activity category is enabled for this user
        if user_preference.enabled_categories and activity.category.value not in user_preference.enabled_categories:
            return False
        
        # Check if in quiet hours
        if await self.is_in_quiet_hours(user_preference):
            # During quiet hours, only send high-priority notifications
            high_priority_types = [
                ActivityType.MENTION.value,
                ActivityType.FOLLOW.value
            ]
            
            if activity.activity_type.value not in high_priority_types:
                return False
        
        return True
    
    async def format_notification_content(
        self,
        activity: ActivityEvent
    ) -> Dict[str, Any]:
        """
        Format activity data into notification content
        
        Args:
            activity: Activity event
            
        Returns:
            Formatted notification content
        """
        # Default values
        title = "New notification"
        body = "You have a new notification"
        
        # Format based on activity type
        activity_type = activity.activity_type.value
        
        if activity_type == ActivityType.MENTION.value:
            title = "You were mentioned"
            body = f"{activity.title or 'Someone mentioned you'}"
            
        elif activity_type == ActivityType.FOLLOW.value:
            title = "New follower"
            body = f"{activity.title or 'Someone started following you'}"
            
        elif activity_type == ActivityType.POST.value:
            title = "New post"
            body = f"{activity.title or 'New content from someone you follow'}"
            
        elif activity_type == ActivityType.COMMENT.value:
            title = "New comment"
            body = f"{activity.title or 'Someone commented on your content'}"
            
        elif activity_type == ActivityType.REACTION.value:
            title = "New reaction"
            body = f"{activity.title or 'Someone reacted to your content'}"
            
        elif activity_type == ActivityType.UPDATE.value:
            title = "Profile update"
            body = f"{activity.title or 'Someone updated their profile'}"
            
        elif activity_type == ActivityType.SYSTEM.value:
            title = "System notification"
            body = f"{activity.title or 'Important system notification'}"
        
        # Use activity description if available
        if activity.description:
            body = activity.description
        
        return {
            "title": title,
            "body": body,
            "data": {
                "activity_id": activity.id,
                "event_id": activity.event_id,
                "activity_type": activity_type,
                "publisher_id": activity.publisher_id,
                "resource_type": activity.resource_type,
                "resource_id": activity.resource_id
            }
        }
    
    async def send_push_notification(
        self,
        db: Session,
        activity_id: int,
        recipient_id: str
    ) -> Optional[str]:
        """
        Send a push notification for an activity
        
        Args:
            db: Database session
            activity_id: ID of the activity
            recipient_id: ID of the recipient
            
        Returns:
            Notification ID if sent successfully, None otherwise
        """
        if not PUSH_NOTIFICATIONS_AVAILABLE:
            logger.warning("Push notifications plugin not available. Skipping notification.")
            return None
        
        # Get the activity
        activity = await self.activity_service.get_activity(db, activity_id)
        if not activity:
            logger.error(f"Activity {activity_id} not found")
            return None
        
        # Check if notification should be sent based on user preferences
        should_send = await self.should_send_notification(db, recipient_id, activity)
        if not should_send:
            logger.info(f"Skipping notification for user {recipient_id} based on preferences")
            return None
        
        try:
            # Format notification content
            notification_content = await self.format_notification_content(activity)
            
            # Create push notification using the push_notifications plugin
            notification_data = NotificationCreate(
                user_id=recipient_id,
                title=notification_content["title"],
                body=notification_content["body"],
                data=notification_content["data"],
                priority="high" if activity.activity_type in [ActivityType.MENTION, ActivityType.FOLLOW] else "normal",
                category=activity.category.value
            )
            
            # Send the notification
            result = await push_notifications_service.notification_service.send_notification(
                db, notification_data
            )
            
            if result and hasattr(result, 'id'):
                notification_id = str(result.id)
                
                # Create a notification record
                await self.create_notification_record(
                    db,
                    activity_id,
                    recipient_id,
                    notification_id,
                    "sent"
                )
                
                return notification_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            
            # Create a failed notification record
            await self.create_notification_record(
                db,
                activity_id,
                recipient_id,
                None,
                "failed"
            )
            
            return None
    
    async def process_activity_notifications(
        self,
        db: Session,
        activity_id: int
    ) -> int:
        """
        Process notifications for an activity
        
        Args:
            db: Database session
            activity_id: ID of the activity
            
        Returns:
            Number of notifications sent
        """
        # Get the activity
        activity = await self.activity_service.get_activity(db, activity_id)
        if not activity:
            logger.error(f"Activity {activity_id} not found")
            return 0
        
        # Get subscribers who should be notified
        subscribers = await self.activity_service.get_subscribers_for_activity(db, activity)
        count = 0
        
        # Send notifications to each subscriber
        for subscriber_id in subscribers:
            try:
                # Skip if subscriber is the same as publisher
                if subscriber_id == activity.publisher_id:
                    continue
                    
                # Send push notification
                notification_id = await self.send_push_notification(db, activity_id, subscriber_id)
                
                if notification_id:
                    count += 1
                    
            except Exception as e:
                logger.error(f"Error processing notification for subscriber {subscriber_id}: {e}")
        
        return count
