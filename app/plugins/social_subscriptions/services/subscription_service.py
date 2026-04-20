"""
Subscription Service

Manages user subscriptions to other users, including:
- Creating, updating, and deleting subscriptions
- Querying subscriptions and subscribers
- Managing subscription status and categories
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import IntegrityError

from ..models.database import Subscription, SubscriptionStatus, SubscriptionCategory
from ..schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionFilter,
    SubscriptionResponse
)
from ..handlers.security_handler import SecurityHandler

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing user subscriptions"""
    
    def __init__(self, security_handler: SecurityHandler, max_subscriptions_per_user: int = 1000):
        """
        Initialize the subscription service
        
        Args:
            security_handler: Security handler for encryption and logging
            max_subscriptions_per_user: Maximum number of subscriptions per user
        """
        self.security_handler = security_handler
        self.max_subscriptions_per_user = max_subscriptions_per_user
        logger.info("Subscription service initialized")
    
    async def create_subscription(
        self, 
        db: Session, 
        subscriber_id: str, 
        data: SubscriptionCreate
    ) -> Subscription:
        """
        Create a new subscription
        
        Args:
            db: Database session
            subscriber_id: ID of the subscribing user
            data: Subscription creation data
            
        Returns:
            Created subscription object
            
        Raises:
            ValueError: If subscription limit is reached or subscription already exists
        """
        # Check if user is trying to subscribe to themselves
        if subscriber_id == data.publisher_id:
            raise ValueError("Cannot subscribe to yourself")
        
        # Check if subscription already exists
        existing = db.query(Subscription).filter(
            Subscription.subscriber_id == subscriber_id,
            Subscription.publisher_id == data.publisher_id
        ).first()
        
        if existing:
            # If subscription exists but is blocked, raise an error
            if existing.status == SubscriptionStatus.BLOCKED:
                raise ValueError("Subscription is blocked and cannot be updated")
                
            # If subscription exists, update its status and categories
            existing.status = SubscriptionStatus.ACTIVE
            existing.categories = [cat.value for cat in data.categories]
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            
            self.security_handler.log_subscription_event(
                "update", 
                subscriber_id, 
                data.publisher_id, 
                {"status": "active", "categories": existing.categories}
            )
            
            return existing
        
        # Check subscription limit
        subscription_count = db.query(Subscription).filter(
            Subscription.subscriber_id == subscriber_id
        ).count()
        
        if subscription_count >= self.max_subscriptions_per_user:
            raise ValueError(f"Maximum subscription limit of {self.max_subscriptions_per_user} reached")
        
        # Create new subscription
        new_subscription = Subscription(
            subscriber_id=subscriber_id,
            publisher_id=data.publisher_id,
            status=SubscriptionStatus.ACTIVE,
            categories=[cat.value for cat in data.categories],
            notification_preferences=data.notification_preferences
        )
        
        try:
            db.add(new_subscription)
            db.commit()
            db.refresh(new_subscription)
            
            self.security_handler.log_subscription_event(
                "create", 
                subscriber_id, 
                data.publisher_id, 
                {"categories": new_subscription.categories}
            )
            
            return new_subscription
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Error creating subscription: {e}")
            raise ValueError("Failed to create subscription")
    
    async def update_subscription(
        self, 
        db: Session, 
        subscriber_id: str, 
        publisher_id: str, 
        data: SubscriptionUpdate
    ) -> Subscription:
        """
        Update an existing subscription
        
        Args:
            db: Database session
            subscriber_id: ID of the subscribing user
            publisher_id: ID of the publisher
            data: Subscription update data
            
        Returns:
            Updated subscription object
            
        Raises:
            ValueError: If subscription does not exist or is blocked
        """
        subscription = db.query(Subscription).filter(
            Subscription.subscriber_id == subscriber_id,
            Subscription.publisher_id == publisher_id
        ).first()
        
        if not subscription:
            raise ValueError("Subscription does not exist")
        
        if subscription.status == SubscriptionStatus.BLOCKED:
            raise ValueError("Subscription is blocked and cannot be updated")
        
        # Update subscription fields
        if data.status is not None:
            subscription.status = SubscriptionStatus(data.status)
        
        if data.categories is not None:
            subscription.categories = [cat.value for cat in data.categories]
        
        if data.notification_preferences is not None:
            subscription.notification_preferences = data.notification_preferences
        
        subscription.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(subscription)
            
            self.security_handler.log_subscription_event(
                "update", 
                subscriber_id, 
                publisher_id, 
                {
                    "status": subscription.status.value if subscription.status else None,
                    "categories": subscription.categories
                }
            )
            
            return subscription
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating subscription: {e}")
            raise ValueError("Failed to update subscription")
    
    async def delete_subscription(
        self, 
        db: Session, 
        subscriber_id: str, 
        publisher_id: str
    ) -> bool:
        """
        Delete a subscription
        
        Args:
            db: Database session
            subscriber_id: ID of the subscribing user
            publisher_id: ID of the publisher
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ValueError: If subscription does not exist
        """
        subscription = db.query(Subscription).filter(
            Subscription.subscriber_id == subscriber_id,
            Subscription.publisher_id == publisher_id
        ).first()
        
        if not subscription:
            raise ValueError("Subscription does not exist")
        
        try:
            db.delete(subscription)
            db.commit()
            
            self.security_handler.log_subscription_event(
                "delete", 
                subscriber_id, 
                publisher_id
            )
            
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting subscription: {e}")
            raise ValueError("Failed to delete subscription")
    
    async def get_subscription(
        self, 
        db: Session, 
        subscriber_id: str, 
        publisher_id: str
    ) -> Optional[Subscription]:
        """
        Get a specific subscription
        
        Args:
            db: Database session
            subscriber_id: ID of the subscribing user
            publisher_id: ID of the publisher
            
        Returns:
            Subscription object if found, None otherwise
        """
        return db.query(Subscription).filter(
            Subscription.subscriber_id == subscriber_id,
            Subscription.publisher_id == publisher_id
        ).first()
    
    async def get_user_subscriptions(
        self, 
        db: Session, 
        subscriber_id: str, 
        filter_params: Optional[SubscriptionFilter] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Subscription]:
        """
        Get all subscriptions for a user
        
        Args:
            db: Database session
            subscriber_id: ID of the subscribing user
            filter_params: Optional filter parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of subscription objects
        """
        query = db.query(Subscription).filter(Subscription.subscriber_id == subscriber_id)
        
        if filter_params:
            if filter_params.status:
                query = query.filter(Subscription.status == SubscriptionStatus(filter_params.status))
            
            if filter_params.category:
                # Filter subscriptions that include the requested category
                category_value = filter_params.category.value
                query = query.filter(
                    # Check ALL category or specific category in the JSON array
                    or_(
                        Subscription.categories.contains([SubscriptionCategory.ALL.value]),
                        Subscription.categories.contains([category_value])
                    )
                )
        
        return query.order_by(desc(Subscription.created_at)).offset(skip).limit(limit).all()
    
    async def get_user_subscribers(
        self, 
        db: Session, 
        publisher_id: str, 
        filter_params: Optional[SubscriptionFilter] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Subscription]:
        """
        Get all subscribers for a user
        
        Args:
            db: Database session
            publisher_id: ID of the publisher
            filter_params: Optional filter parameters
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of subscription objects
        """
        query = db.query(Subscription).filter(Subscription.publisher_id == publisher_id)
        
        if filter_params:
            if filter_params.status:
                query = query.filter(Subscription.status == SubscriptionStatus(filter_params.status))
            
            if filter_params.category:
                # Filter subscriptions that include the requested category
                category_value = filter_params.category.value
                query = query.filter(
                    # Check ALL category or specific category in the JSON array
                    or_(
                        Subscription.categories.contains([SubscriptionCategory.ALL.value]),
                        Subscription.categories.contains([category_value])
                    )
                )
        
        return query.order_by(desc(Subscription.created_at)).offset(skip).limit(limit).all()
    
    async def get_subscription_count(self, db: Session, subscriber_id: str) -> int:
        """
        Get the number of subscriptions for a user
        
        Args:
            db: Database session
            subscriber_id: ID of the subscribing user
            
        Returns:
            Number of subscriptions
        """
        return db.query(Subscription).filter(
            Subscription.subscriber_id == subscriber_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
    
    async def get_subscriber_count(self, db: Session, publisher_id: str) -> int:
        """
        Get the number of subscribers for a user
        
        Args:
            db: Database session
            publisher_id: ID of the publisher
            
        Returns:
            Number of subscribers
        """
        return db.query(Subscription).filter(
            Subscription.publisher_id == publisher_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
    
    async def check_subscription_exists(
        self, 
        db: Session, 
        subscriber_id: str, 
        publisher_id: str,
        category: Optional[SubscriptionCategory] = None
    ) -> bool:
        """
        Check if a subscription exists
        
        Args:
            db: Database session
            subscriber_id: ID of the subscribing user
            publisher_id: ID of the publisher
            category: Optional specific category to check
            
        Returns:
            True if subscription exists, False otherwise
        """
        query = db.query(Subscription).filter(
            Subscription.subscriber_id == subscriber_id,
            Subscription.publisher_id == publisher_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        
        if category:
            # Check if the subscription includes the specific category
            category_value = category.value
            query = query.filter(
                or_(
                    Subscription.categories.contains([SubscriptionCategory.ALL.value]),
                    Subscription.categories.contains([category_value])
                )
            )
        
        return db.query(query.exists()).scalar()
    
    async def process_subscription_request(
        self, 
        db: Session, 
        subscriber_id: str, 
        publisher_id: str, 
        action: str,
        categories: Optional[List[SubscriptionCategory]] = None
    ) -> Tuple[bool, str]:
        """
        Process a subscription request (subscribe or unsubscribe)
        
        Args:
            db: Database session
            subscriber_id: ID of the subscribing user
            publisher_id: ID of the publisher
            action: 'subscribe' or 'unsubscribe'
            categories: Optional list of categories to subscribe to
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if action == "subscribe":
                categories = categories or [SubscriptionCategory.CONTENT, SubscriptionCategory.MENTIONS]
                
                await self.create_subscription(
                    db, 
                    subscriber_id, 
                    SubscriptionCreate(
                        publisher_id=publisher_id,
                        categories=categories
                    )
                )
                return True, "Successfully subscribed"
            
            elif action == "unsubscribe":
                await self.delete_subscription(db, subscriber_id, publisher_id)
                return True, "Successfully unsubscribed"
            
            else:
                return False, "Invalid action"
                
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"Error processing subscription request: {e}")
            return False, "An error occurred while processing the request"
    
    async def get_mutual_subscriptions(
        self, 
        db: Session, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Subscription]:
        """
        Get mutual subscriptions (users who the user follows and who follow the user back)
        
        Args:
            db: Database session
            user_id: ID of the user
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of subscription objects
        """
        # Find all users who the current user follows
        following_subquery = db.query(Subscription.publisher_id).filter(
            Subscription.subscriber_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).subquery()
        
        # Find all users from the above list who also follow the current user
        mutual_subscriptions = db.query(Subscription).filter(
            Subscription.subscriber_id.in_(following_subquery),
            Subscription.publisher_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).order_by(desc(Subscription.created_at)).offset(skip).limit(limit).all()
        
        return mutual_subscriptions
