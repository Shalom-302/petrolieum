"""
Social Subscriptions Plugin

Main integration module for the social subscriptions plugin.
This plugin enables users to:
- Subscribe to other users for notifications on specific activities
- Receive personalized activity feeds
- Manage subscription preferences and categories
- Process activity events and generate notifications

Security features include:
- Encryption of sensitive metadata
- Validation of subscription and activity requests
- Comprehensive logging of all subscription and notification events
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.db import get_db, Base, engine

# Import models
from .models.database import (
    Subscription,
    ActivityEvent,
    FeedItem,
    NotificationRecord,
    UserPreference
)

# Import routes and dependencies
from .routes.subscription import router as subscription_router, get_subscription_service
from .routes.feed import router as feed_router, get_feed_service, get_activity_service
from .routes.preferences import router as preferences_router, get_notification_service

# Import handlers and services
from .handlers.security_handler import SecurityHandler
from .services.subscription_service import SubscriptionService
from .services.activity_service import ActivityService
from .services.feed_service import FeedService
from .services.notification_service import NotificationService


# Services instance for the whole module
security_handler = SecurityHandler()
subscription_service = SubscriptionService(security_handler)
activity_service = ActivityService(security_handler, subscription_service)
feed_service = FeedService(security_handler, subscription_service, activity_service)
notification_service = NotificationService(security_handler, activity_service)


def get_router() -> APIRouter:
    """
    Create and configure a router for the social subscriptions plugin.
    
    Returns:
        APIRouter: The configured router
    """
    router = APIRouter(prefix="/social", tags=["social"])
    
    # Include all sub-routers
    router.include_router(subscription_router)
    router.include_router(feed_router)
    router.include_router(preferences_router)
    
    @router.get("/", response_model=Dict[str, Any])
    async def plugin_info():
        """Get social subscriptions plugin information."""
        return {
            "name": "Social Subscriptions System",
            "description": "Complete solution for social subscription management and activity feeds",
            "version": "1.0.0",
            "features": [
                "User subscriptions and follows",
                "Personalized activity feeds",
                "Notification preferences",
                "Activity event processing",
                "Subscription analytics"
            ]
        }
    
    # Register service dependencies for routes
    get_subscription_service_instance = lambda: subscription_service
    get_activity_service_instance = lambda: activity_service
    get_feed_service_instance = lambda: feed_service
    get_notification_service_instance = lambda: notification_service
    
    def init_app(app):
        """Initialize the social subscriptions plugin."""
        # Override dependencies
        app.dependency_overrides[get_subscription_service] = get_subscription_service_instance
        app.dependency_overrides[get_activity_service] = get_activity_service_instance
        app.dependency_overrides[get_feed_service] = get_feed_service_instance
        app.dependency_overrides[get_notification_service] = get_notification_service_instance
        
        # Include router
        app.include_router(router)
        
        return {
            "name": "social_subscriptions",
            "description": "Social Subscriptions System",
            "version": "1.0.0"
        }
    
    return router


# API helper functions for programmatic usage
async def create_standard_subscription(
    db: Session,
    subscriber_id: str,
    publisher_id: str,
    categories: list = None
) -> Subscription:
    """
    Create a standard subscription between users
    
    Args:
        db: Database session
        subscriber_id: ID of the subscriber
        publisher_id: ID of the publisher
        categories: Optional list of categories
        
    Returns:
        Created subscription object
    """
    from .schemas.subscription import SubscriptionCreate
    
    # Create subscription data
    data = SubscriptionCreate(
        publisher_id=publisher_id,
        categories=categories or ["post", "update"]
    )
    
    # Create subscription using service
    return await subscription_service.create_subscription(db, subscriber_id, data)

async def create_standard_activity(
    db: Session,
    publisher_id: str,
    activity_type: str,
    resource_type: str,
    resource_id: str,
    title: str = None,
    description: str = None,
    metadata: dict = None
) -> ActivityEvent:
    """
    Create a standard activity event
    
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
        Created activity event
    """
    return await activity_service.create_standard_activity(
        db,
        publisher_id,
        activity_type,
        resource_type,
        resource_id,
        title,
        description,
        metadata
    )

async def process_activity(
    db: Session,
    activity_id: int
) -> int:
    """
    Process an activity for feeds and notifications
    
    Args:
        db: Database session
        activity_id: ID of the activity
        
    Returns:
        Number of feed items created
    """
    # Process activity for feeds
    feed_count = await feed_service.process_activity_for_feeds(db, activity_id)
    
    # Process activity for notifications
    notification_count = await notification_service.process_activity_notifications(db, activity_id)
    
    logging.getLogger(__name__).info(
        f"Processed activity {activity_id}: created {feed_count} feed items and {notification_count} notifications"
    )
    
    return feed_count + notification_count

async def get_user_feed(
    db: Session,
    user_id: str,
    skip: int = 0,
    limit: int = 20
):
    """
    Get a user's activity feed
    
    Args:
        db: Database session
        user_id: ID of the user
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of feed items
    """
    return await feed_service.get_user_feed(db, user_id, skip, limit)


# Initialize and export router
social_subscriptions_router = get_router()
