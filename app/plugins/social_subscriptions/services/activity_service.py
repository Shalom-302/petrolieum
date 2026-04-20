"""
Activity Service

Manages activity events within the social subscription system, including:
- Creating and retrieving activity events
- Determining relevant subscribers for activities
- Categorizing activities by type and subscription category
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import IntegrityError

from ..models.database import (
    ActivityEvent, 
    Subscription, 
    SubscriptionStatus, 
    SubscriptionCategory,
    ActivityType
)
from ..schemas.subscription import ActivityEventCreate, ActivityEventResponse
from ..handlers.security_handler import SecurityHandler
from .subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class ActivityService:
    """Service for managing activity events"""
    
    def __init__(
        self, 
        security_handler: SecurityHandler,
        subscription_service: SubscriptionService
    ):
        """
        Initialize the activity service
        
        Args:
            security_handler: Security handler for encryption and logging
            subscription_service: Subscription service for querying subscribers
        """
        self.security_handler = security_handler
        self.subscription_service = subscription_service
        logger.info("Activity service initialized")
    
    async def create_activity(
        self, 
        db: Session, 
        data: ActivityEventCreate
    ) -> ActivityEvent:
        """
        Create a new activity event
        
        Args:
            db: Database session
            data: Activity event creation data
            
        Returns:
            Created activity event object
            
        Raises:
            ValueError: If activity creation fails
        """
        # Sanitize user input
        title = data.title
        description = data.description
        
        if title:
            title = self.security_handler.sanitize_user_input(title)
        
        if description:
            description = self.security_handler.sanitize_user_input(description)
        
        # Generate a unique event ID
        event_id = self.security_handler.generate_event_id()
        
        # Determine the appropriate activity category
        activity_category = data.category
        
        # Create new activity event
        new_activity = ActivityEvent(
            event_id=event_id,
            publisher_id=data.publisher_id,
            activity_type=ActivityType(data.activity_type),
            category=SubscriptionCategory(activity_category),
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            title=title,
            description=description,
            activity_metadata=data.metadata
        )
        
        try:
            db.add(new_activity)
            db.commit()
            db.refresh(new_activity)
            
            # Log activity creation with security handler
            self.security_handler.log_event(
                "activity_created",
                publisher_id=data.publisher_id,
                activity_type=data.activity_type,
                resource_id=data.resource_id
            )
            
            return new_activity
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to create activity event: {e}")
            raise ValueError(f"Failed to create activity event: {e}")
    
    async def get_activity(
        self, 
        db: Session, 
        activity_id: int
    ) -> Optional[ActivityEvent]:
        """
        Get a specific activity by ID
        
        Args:
            db: Database session
            activity_id: ID of the activity
            
        Returns:
            Activity event object if found, None otherwise
        """
        return db.query(ActivityEvent).filter(ActivityEvent.id == activity_id).first()
    
    async def get_activity_by_event_id(
        self, 
        db: Session, 
        event_id: str
    ) -> Optional[ActivityEvent]:
        """
        Get a specific activity by event ID
        
        Args:
            db: Database session
            event_id: Event ID of the activity
            
        Returns:
            Activity event object if found, None otherwise
        """
        return db.query(ActivityEvent).filter(ActivityEvent.event_id == event_id).first()
    
    async def get_publisher_activities(
        self, 
        db: Session, 
        publisher_id: str,
        activity_types: Optional[List[ActivityType]] = None,
        categories: Optional[List[SubscriptionCategory]] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[ActivityEvent]:
        """
        Get activities for a specific publisher
        
        Args:
            db: Database session
            publisher_id: ID of the publisher
            activity_types: Optional list of activity types to filter
            categories: Optional list of categories to filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of activity event objects
        """
        query = db.query(ActivityEvent).filter(ActivityEvent.publisher_id == publisher_id)
        
        if activity_types:
            query = query.filter(ActivityEvent.activity_type.in_([ActivityType(at) for at in activity_types]))
        
        if categories:
            query = query.filter(ActivityEvent.category.in_([SubscriptionCategory(cat) for cat in categories]))
        
        return query.order_by(desc(ActivityEvent.created_at)).offset(skip).limit(limit).all()
    
    async def get_resource_activities(
        self, 
        db: Session, 
        resource_type: str,
        resource_id: str,
        skip: int = 0, 
        limit: int = 100
    ) -> List[ActivityEvent]:
        """
        Get activities for a specific resource
        
        Args:
            db: Database session
            resource_type: Type of resource
            resource_id: ID of the resource
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of activity event objects
        """
        return db.query(ActivityEvent).filter(
            ActivityEvent.resource_type == resource_type,
            ActivityEvent.resource_id == resource_id
        ).order_by(desc(ActivityEvent.created_at)).offset(skip).limit(limit).all()
    
    async def get_subscribers_for_activity(
        self, 
        db: Session, 
        activity: ActivityEvent
    ) -> List[str]:
        """
        Get a list of subscribers who should be notified about an activity
        
        Args:
            db: Database session
            activity: Activity event object
            
        Returns:
            List of subscriber IDs
        """
        # Get subscribers for the publisher with active status 
        # who have subscribed to the activity's category
        category_value = activity.category.value
        
        query = db.query(Subscription.subscriber_id).filter(
            Subscription.publisher_id == activity.publisher_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            # Check if the subscription includes ALL or the specific category
            or_(
                Subscription.categories.contains([SubscriptionCategory.ALL.value]),
                Subscription.categories.contains([category_value])
            )
        )
        
        subscribers = [sub[0] for sub in query.all()]
        return subscribers
    
    async def map_activity_type_to_category(
        self, 
        activity_type: ActivityType
    ) -> SubscriptionCategory:
        """
        Map an activity type to a subscription category
        
        Args:
            activity_type: Activity type enum
            
        Returns:
            Corresponding subscription category
        """
        # Mapping of activity types to subscription categories
        mapping = {
            ActivityType.POST: SubscriptionCategory.CONTENT,
            ActivityType.COMMENT: SubscriptionCategory.INTERACTIONS,
            ActivityType.REACTION: SubscriptionCategory.INTERACTIONS,
            ActivityType.MENTION: SubscriptionCategory.MENTIONS,
            ActivityType.FOLLOW: SubscriptionCategory.INTERACTIONS,
            ActivityType.UPDATE: SubscriptionCategory.UPDATES,
            ActivityType.SYSTEM: SubscriptionCategory.SYSTEM
        }
        
        return mapping.get(activity_type, SubscriptionCategory.CONTENT)
    
    async def create_standard_activity(
        self, 
        db: Session, 
        publisher_id: str,
        activity_type: ActivityType,
        resource_type: str,
        resource_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ActivityEvent:
        """
        Create a standard activity event with appropriate category mapping
        
        Args:
            db: Database session
            publisher_id: ID of the publisher
            activity_type: Type of activity
            resource_type: Type of resource
            resource_id: ID of the resource
            title: Optional title
            description: Optional description
            metadata: Optional metadata
            
        Returns:
            Created activity event object
        """
        # Map activity type to subscription category
        category = await self.map_activity_type_to_category(activity_type)
        
        # Create the activity
        activity_data = ActivityEventCreate(
            publisher_id=publisher_id,
            activity_type=activity_type.value,
            category=category.value,
            resource_type=resource_type,
            resource_id=resource_id,
            title=title,
            description=description,
            metadata=metadata
        )
        
        return await self.create_activity(db, activity_data)
