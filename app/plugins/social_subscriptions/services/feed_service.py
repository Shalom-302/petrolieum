"""
Feed Service

Manages social activity feeds, including:
- Generating personalized feeds for users
- Sorting and filtering feed items
- Reading status management
- Algorithmic relevance scoring
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func, text
from sqlalchemy.exc import IntegrityError

from ..models.database import (
    FeedItem,
    ActivityEvent,
    Subscription,
    SubscriptionStatus,
    SubscriptionCategory,
    ActivityType
)
from ..schemas.subscription import FeedFilter, FeedItemCreate, FeedItemResponse
from ..handlers.security_handler import SecurityHandler
from .subscription_service import SubscriptionService
from .activity_service import ActivityService

logger = logging.getLogger(__name__)


class FeedService:
    """Service for managing activity feeds"""
    
    def __init__(
        self,
        security_handler: SecurityHandler,
        subscription_service: SubscriptionService,
        activity_service: ActivityService,
        feed_cache_ttl: int = 3600  # 1 hour in seconds
    ):
        """
        Initialize the feed service
        
        Args:
            security_handler: Security handler for encryption and logging
            subscription_service: Subscription service for querying subscriptions
            activity_service: Activity service for querying activities
            feed_cache_ttl: TTL for feed cache in seconds
        """
        self.security_handler = security_handler
        self.subscription_service = subscription_service
        self.activity_service = activity_service
        self.feed_cache_ttl = feed_cache_ttl
        logger.info("Feed service initialized")
    
    async def generate_feed_item(
        self,
        db: Session,
        user_id: str,
        activity_id: int,
        publisher_id: str,
        relevance_score: Optional[int] = None
    ) -> FeedItem:
        """
        Generate a feed item for a user
        
        Args:
            db: Database session
            user_id: ID of the user
            activity_id: ID of the activity
            publisher_id: ID of the publisher
            relevance_score: Optional relevance score
            
        Returns:
            Generated feed item
            
        Raises:
            ValueError: If feed item generation fails
        """
        # Check if feed item already exists
        existing = db.query(FeedItem).filter(
            FeedItem.user_id == user_id,
            FeedItem.activity_id == activity_id
        ).first()
        
        if existing:
            # Update existing feed item if needed
            if relevance_score is not None and existing.relevance_score != relevance_score:
                existing.relevance_score = relevance_score
                db.commit()
                db.refresh(existing)
            return existing
        
        # Create a new feed item
        feed_item = FeedItem(
            user_id=user_id,
            activity_id=activity_id,
            publisher_id=publisher_id,
            relevance_score=relevance_score or 100  # Default relevance score
        )
        
        try:
            db.add(feed_item)
            db.commit()
            db.refresh(feed_item)
            return feed_item
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Error creating feed item: {e}")
            raise ValueError("Failed to create feed item")
    
    async def get_user_feed(
        self,
        db: Session,
        user_id: str,
        filter_params: Optional[FeedFilter] = None,
        feed_type: str = "chronological",
        skip: int = 0,
        limit: int = 20
    ) -> List[FeedItem]:
        """
        Get the activity feed for a user
        
        Args:
            db: Database session
            user_id: ID of the user
            filter_params: Optional filter parameters
            feed_type: Type of feed (chronological, algorithmic)
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of feed items
        """
        # Start with base query
        query = db.query(FeedItem).options(
            joinedload(FeedItem.activity)
        ).filter(
            FeedItem.user_id == user_id,
            FeedItem.is_hidden == False
        )
        
        # Apply filters
        if filter_params:
            if not filter_params.include_read:
                query = query.filter(FeedItem.is_read == False)
                
            if filter_params.publisher_ids:
                query = query.filter(FeedItem.publisher_id.in_(filter_params.publisher_ids))
                
            if filter_params.activity_types:
                query = query.join(ActivityEvent).filter(
                    ActivityEvent.activity_type.in_([
                        ActivityType(at) for at in filter_params.activity_types
                    ])
                )
                
            if filter_params.categories:
                query = query.join(ActivityEvent).filter(
                    ActivityEvent.category.in_([
                        SubscriptionCategory(cat) for cat in filter_params.categories
                    ])
                )
                
            if filter_params.since:
                query = query.filter(FeedItem.created_at >= filter_params.since)
                
            if filter_params.until:
                query = query.filter(FeedItem.created_at <= filter_params.until)
        
        # Apply sorting based on feed type
        if feed_type == "algorithmic":
            # Sort by relevance score (descending) and then by creation time
            query = query.order_by(desc(FeedItem.relevance_score), desc(FeedItem.created_at))
        else:
            # Default to chronological sorting
            query = query.order_by(desc(FeedItem.created_at))
        
        # Apply pagination
        feed_items = query.offset(skip).limit(limit).all()
        
        return feed_items
    
    async def calculate_relevance_score(
        self,
        db: Session,
        user_id: str,
        activity: ActivityEvent
    ) -> int:
        """
        Calculate a relevance score for an activity based on user preferences
        
        Args:
            db: Database session
            user_id: ID of the user
            activity: Activity event
            
        Returns:
            Relevance score (0-1000, higher is more relevant)
        """
        base_score = 100
        publisher_id = activity.publisher_id
        
        # Factor 1: Subscription recency and interaction
        subscription = await self.subscription_service.get_subscription(
            db, user_id, publisher_id
        )
        
        if subscription:
            # More recent subscriptions get higher scores
            days_since_subscription = (datetime.utcnow() - subscription.created_at).days
            recency_score = max(0, 100 - min(days_since_subscription, 100))
            base_score += recency_score
        
        # Factor 2: Activity type importance
        activity_type_scores = {
            ActivityType.MENTION: 300,      # Mentions are high priority
            ActivityType.FOLLOW: 250,       # New followers are important
            ActivityType.COMMENT: 200,      # Comments are fairly important
            ActivityType.REACTION: 150,     # Reactions are somewhat important
            ActivityType.POST: 100,         # Posts are standard importance
            ActivityType.UPDATE: 80,        # Updates are less important
            ActivityType.SYSTEM: 50         # System messages are lowest priority
        }
        
        base_score += activity_type_scores.get(activity.activity_type, 0)
        
        # Factor 3: Recency of activity
        hours_since_activity = (datetime.utcnow() - activity.created_at).total_seconds() / 3600
        recency_bonus = max(0, 200 - min(int(hours_since_activity), 200))
        base_score += recency_bonus
        
        # Cap the score at 1000
        return min(1000, base_score)
    
    async def mark_feed_item_as_read(
        self,
        db: Session,
        user_id: str,
        feed_item_id: int
    ) -> bool:
        """
        Mark a feed item as read
        
        Args:
            db: Database session
            user_id: ID of the user
            feed_item_id: ID of the feed item
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ValueError: If feed item does not exist or doesn't belong to the user
        """
        feed_item = db.query(FeedItem).filter(
            FeedItem.id == feed_item_id,
            FeedItem.user_id == user_id
        ).first()
        
        if not feed_item:
            raise ValueError("Feed item not found or doesn't belong to the user")
        
        feed_item.is_read = True
        
        try:
            db.commit()
            db.refresh(feed_item)
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking feed item as read: {e}")
            return False
    
    async def mark_all_feed_items_as_read(
        self,
        db: Session,
        user_id: str,
        publisher_id: Optional[str] = None
    ) -> int:
        """
        Mark all feed items as read for a user
        
        Args:
            db: Database session
            user_id: ID of the user
            publisher_id: Optional publisher ID to filter
            
        Returns:
            Number of feed items marked as read
        """
        query = db.query(FeedItem).filter(
            FeedItem.user_id == user_id,
            FeedItem.is_read == False
        )
        
        if publisher_id:
            query = query.filter(FeedItem.publisher_id == publisher_id)
        
        try:
            # Update all matching feed items
            count = query.update({FeedItem.is_read: True}, synchronize_session=False)
            db.commit()
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking all feed items as read: {e}")
            return 0
    
    async def hide_feed_item(
        self,
        db: Session,
        user_id: str,
        feed_item_id: int
    ) -> bool:
        """
        Hide a feed item
        
        Args:
            db: Database session
            user_id: ID of the user
            feed_item_id: ID of the feed item
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ValueError: If feed item does not exist or doesn't belong to the user
        """
        feed_item = db.query(FeedItem).filter(
            FeedItem.id == feed_item_id,
            FeedItem.user_id == user_id
        ).first()
        
        if not feed_item:
            raise ValueError("Feed item not found or doesn't belong to the user")
        
        feed_item.is_hidden = True
        
        try:
            db.commit()
            db.refresh(feed_item)
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error hiding feed item: {e}")
            return False
    
    async def process_activity_for_feeds(
        self,
        db: Session,
        activity_id: int
    ) -> int:
        """
        Process an activity and generate feed items for all subscribers
        
        Args:
            db: Database session
            activity_id: ID of the activity
            
        Returns:
            Number of feed items generated
        """
        # Get the activity
        activity = await self.activity_service.get_activity(db, activity_id)
        if not activity:
            logger.error(f"Activity {activity_id} not found")
            return 0
        
        # Get subscribers for this activity
        subscribers = await self.activity_service.get_subscribers_for_activity(db, activity)
        count = 0
        
        # Create feed items for each subscriber
        for subscriber_id in subscribers:
            try:
                # Calculate relevance score
                relevance_score = await self.calculate_relevance_score(db, subscriber_id, activity)
                
                # Generate feed item
                await self.generate_feed_item(
                    db,
                    subscriber_id,
                    activity.id,
                    activity.publisher_id,
                    relevance_score
                )
                count += 1
            except Exception as e:
                logger.error(f"Error creating feed item for subscriber {subscriber_id}: {e}")
        
        return count
    
    async def cleanup_old_feed_items(
        self,
        db: Session,
        days_to_keep: int = 30
    ) -> int:
        """
        Clean up old feed items to prevent database bloat
        
        Args:
            db: Database session
            days_to_keep: Number of days to keep feed items
            
        Returns:
            Number of feed items deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        try:
            # Delete old feed items that have been read
            query = db.query(FeedItem).filter(
                FeedItem.created_at < cutoff_date,
                FeedItem.is_read == True
            )
            
            count = query.delete(synchronize_session=False)
            db.commit()
            
            logger.info(f"Cleaned up {count} old feed items")
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Error cleaning up old feed items: {e}")
            return 0
