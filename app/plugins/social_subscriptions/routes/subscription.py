"""
Subscription Routes

API routes for managing social subscriptions, including:
- Subscribe/unsubscribe to users
- Get subscriptions and subscribers
- Update subscription preferences
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user

from ..services.subscription_service import SubscriptionService
from ..schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionFilter
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Define a dependency to get the subscription service instance
def get_subscription_service() -> SubscriptionService:
    """Dependency to get the subscription service instance."""
    # This will be overridden in the main.py file
    return SubscriptionService()


@router.post("/subscriptions/{publisher_id}", response_model=SubscriptionResponse)
async def subscribe_to_user(
    publisher_id: str = Path(..., description="ID of the user to subscribe to"),
    data: Optional[SubscriptionCreate] = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Subscribe to a user to receive their activity notifications.
    
    Args:
        publisher_id: ID of the user to subscribe to
        data: Optional subscription creation data with categories and preferences
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        Created subscription object
    """
    if data is None:
        data = SubscriptionCreate(publisher_id=publisher_id)
    else:
        # Ensure publisher_id in path and body match
        data.publisher_id = publisher_id
    
    try:
        subscription = await subscription_service.create_subscription(
            db, current_user["id"], data
        )
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.put("/subscriptions/{publisher_id}", response_model=SubscriptionResponse)
async def update_subscription(
    publisher_id: str = Path(..., description="ID of the publisher"),
    data: SubscriptionUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Update an existing subscription.
    
    Args:
        publisher_id: ID of the publisher
        data: Subscription update data
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        Updated subscription object
    """
    try:
        subscription = await subscription_service.update_subscription(
            db, current_user["id"], publisher_id, data
        )
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to update subscription")


@router.delete("/subscriptions/{publisher_id}", response_model=Dict[str, bool])
async def unsubscribe_from_user(
    publisher_id: str = Path(..., description="ID of the publisher"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Unsubscribe from a user.
    
    Args:
        publisher_id: ID of the publisher
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        Success status
    """
    try:
        success = await subscription_service.delete_subscription(
            db, current_user["id"], publisher_id
        )
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete subscription")


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def get_my_subscriptions(
    status: Optional[str] = Query(None, description="Filter by subscription status"),
    category: Optional[str] = Query(None, description="Filter by subscription category"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Get all subscriptions for the current user.
    
    Args:
        status: Optional status filter
        category: Optional category filter
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        List of subscription objects
    """
    filter_params = None
    if status or category:
        filter_params = SubscriptionFilter(status=status, category=category)
    
    try:
        subscriptions = await subscription_service.get_user_subscriptions(
            db, current_user["id"], filter_params, skip, limit
        )
        return subscriptions
    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscriptions")


@router.get("/subscribers", response_model=List[SubscriptionResponse])
async def get_my_subscribers(
    status: Optional[str] = Query(None, description="Filter by subscription status"),
    category: Optional[str] = Query(None, description="Filter by subscription category"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Get all subscribers for the current user.
    
    Args:
        status: Optional status filter
        category: Optional category filter
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        List of subscription objects
    """
    filter_params = None
    if status or category:
        filter_params = SubscriptionFilter(status=status, category=category)
    
    try:
        subscribers = await subscription_service.get_user_subscribers(
            db, current_user["id"], filter_params, skip, limit
        )
        return subscribers
    except Exception as e:
        logger.error(f"Error getting subscribers: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscribers")


@router.get("/subscriptions/{publisher_id}", response_model=SubscriptionResponse)
async def get_subscription(
    publisher_id: str = Path(..., description="ID of the publisher"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Get a specific subscription.
    
    Args:
        publisher_id: ID of the publisher
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        Subscription object if found
    """
    try:
        subscription = await subscription_service.get_subscription(
            db, current_user["id"], publisher_id
        )
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return subscription
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscription")


@router.get("/subscriptions/count", response_model=Dict[str, int])
async def get_subscription_count(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Get the number of subscriptions for the current user.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        Count of subscriptions
    """
    try:
        count = await subscription_service.get_subscription_count(db, current_user["id"])
        return {"count": count}
    except Exception as e:
        logger.error(f"Error getting subscription count: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscription count")


@router.get("/subscribers/count", response_model=Dict[str, int])
async def get_subscriber_count(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Get the number of subscribers for the current user.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        Count of subscribers
    """
    try:
        count = await subscription_service.get_subscriber_count(db, current_user["id"])
        return {"count": count}
    except Exception as e:
        logger.error(f"Error getting subscriber count: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscriber count")


@router.get("/subscriptions/mutual", response_model=List[SubscriptionResponse])
async def get_mutual_subscriptions(
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    subscription_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Get mutual subscriptions (users who the current user follows and who follow the current user back).
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user
        subscription_service: Subscription service
        
    Returns:
        List of subscription objects
    """
    try:
        subscriptions = await subscription_service.get_mutual_subscriptions(
            db, current_user["id"], skip, limit
        )
        return subscriptions
    except Exception as e:
        logger.error(f"Error getting mutual subscriptions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get mutual subscriptions")
