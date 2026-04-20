"""
Feed Routes

API routes for managing social activity feeds, including:
- Retrieving personalized user feeds
- Marking feed items as read
- Hiding unwanted feed items
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user

from ..services.feed_service import FeedService
from ..services.activity_service import ActivityService
from ..schemas.subscription import (
    FeedItemResponse,
    FeedFilter,
    ActivityEventResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Define dependencies to get service instances
def get_feed_service() -> FeedService:
    """Dependency to get the feed service instance."""
    # This will be overridden in the main.py file
    return FeedService()

def get_activity_service() -> ActivityService:
    """Dependency to get the activity service instance."""
    # This will be overridden in the main.py file
    return ActivityService()


@router.get("/feed", response_model=List[FeedItemResponse])
async def get_activity_feed(
    include_read: bool = Query(False, description="Include read items"),
    publisher_ids: Optional[List[str]] = Query(None, description="Filter by publisher IDs"),
    activity_types: Optional[List[str]] = Query(None, description="Filter by activity types"),
    categories: Optional[List[str]] = Query(None, description="Filter by categories"),
    since: Optional[datetime] = Query(None, description="Filter by creation date (since)"),
    until: Optional[datetime] = Query(None, description="Filter by creation date (until)"),
    feed_type: str = Query("chronological", description="Feed type (chronological, algorithmic)"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(20, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    feed_service: FeedService = Depends(get_feed_service)
):
    """
    Get activity feed for the current user.
    
    Args:
        include_read: Whether to include read items
        publisher_ids: Optional list of publisher IDs to filter
        activity_types: Optional list of activity types to filter
        categories: Optional list of categories to filter
        since: Optional since date filter
        until: Optional until date filter
        feed_type: Feed type (chronological, algorithmic)
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user
        feed_service: Feed service
        
    Returns:
        List of feed items with activities
    """
    filter_params = FeedFilter(
        include_read=include_read,
        publisher_ids=publisher_ids,
        activity_types=activity_types,
        categories=categories,
        since=since,
        until=until
    )
    
    try:
        feed_items = await feed_service.get_user_feed(
            db, current_user["id"], filter_params, feed_type, skip, limit
        )
        return feed_items
    except Exception as e:
        logger.error(f"Error getting feed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get feed")


@router.post("/feed/{feed_item_id}/read", response_model=Dict[str, bool])
async def mark_feed_item_as_read(
    feed_item_id: int = Path(..., description="ID of the feed item"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    feed_service: FeedService = Depends(get_feed_service)
):
    """
    Mark a feed item as read.
    
    Args:
        feed_item_id: ID of the feed item
        db: Database session
        current_user: Current authenticated user
        feed_service: Feed service
        
    Returns:
        Success status
    """
    try:
        success = await feed_service.mark_feed_item_as_read(
            db, current_user["id"], feed_item_id
        )
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking feed item as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark feed item as read")


@router.post("/feed/read-all", response_model=Dict[str, int])
async def mark_all_feed_items_as_read(
    publisher_id: Optional[str] = Query(None, description="Optional publisher ID filter"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    feed_service: FeedService = Depends(get_feed_service)
):
    """
    Mark all feed items as read.
    
    Args:
        publisher_id: Optional publisher ID to filter
        db: Database session
        current_user: Current authenticated user
        feed_service: Feed service
        
    Returns:
        Count of marked items
    """
    try:
        count = await feed_service.mark_all_feed_items_as_read(
            db, current_user["id"], publisher_id
        )
        return {"count": count}
    except Exception as e:
        logger.error(f"Error marking all feed items as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark all feed items as read")


@router.post("/feed/{feed_item_id}/hide", response_model=Dict[str, bool])
async def hide_feed_item(
    feed_item_id: int = Path(..., description="ID of the feed item"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    feed_service: FeedService = Depends(get_feed_service)
):
    """
    Hide a feed item.
    
    Args:
        feed_item_id: ID of the feed item
        db: Database session
        current_user: Current authenticated user
        feed_service: Feed service
        
    Returns:
        Success status
    """
    try:
        success = await feed_service.hide_feed_item(
            db, current_user["id"], feed_item_id
        )
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error hiding feed item: {e}")
        raise HTTPException(status_code=500, detail="Failed to hide feed item")


@router.post("/activities", response_model=ActivityEventResponse)
async def create_activity(
    data: Dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    activity_service: ActivityService = Depends(get_activity_service),
    feed_service: FeedService = Depends(get_feed_service)
):
    """
    Create a new activity event and process it for feeds and notifications.
    
    Args:
        data: Activity data
        background_tasks: Background tasks
        db: Database session
        current_user: Current authenticated user
        activity_service: Activity service
        feed_service: Feed service
        
    Returns:
        Created activity event
    """
    try:
        # Ensure publisher is current user
        data["publisher_id"] = current_user["id"]
        
        # Create activity schema from data
        from ..schemas.subscription import ActivityEventCreate
        activity_data = ActivityEventCreate(**data)
        
        # Create activity
        activity = await activity_service.create_activity(db, activity_data)
        
        # Process activity in background
        background_tasks.add_task(
            feed_service.process_activity_for_feeds,
            db,
            activity.id
        )
        
        return activity
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating activity: {e}")
        raise HTTPException(status_code=500, detail="Failed to create activity")
