"""
Preferences Routes

API routes for managing user notification and subscription preferences, including:
- Setting notification preferences
- Managing quiet hours
- Customizing feed display options
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user

from ..models.database import UserPreference
from ..schemas.subscription import (
    UserPreferenceCreate,
    UserPreferenceUpdate,
    UserPreferenceResponse
)
from ..services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter()

# Define a dependency to get the notification service instance
def get_notification_service() -> NotificationService:
    """Dependency to get the notification service instance."""
    # This will be overridden in the main.py file
    return NotificationService()


@router.get("/preferences", response_model=UserPreferenceResponse)
async def get_user_preferences(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Get current user's notification and subscription preferences.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        notification_service: Notification service for preference management
        
    Returns:
        User preferences
    """
    try:
        user_prefs = await notification_service.get_user_preferences(db, current_user["id"])
        return user_prefs
    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user preferences")


@router.post("/preferences", response_model=UserPreferenceResponse)
async def create_user_preferences(
    data: UserPreferenceCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Create or update user notification and subscription preferences.
    
    Args:
        data: User preference data
        db: Database session
        current_user: Current authenticated user
        notification_service: Notification service for preference management
        
    Returns:
        Created or updated user preferences
    """
    try:
        user_prefs = await notification_service.create_user_preferences(db, current_user["id"], data)
        return user_prefs
    except Exception as e:
        logger.error(f"Error creating user preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user preferences")


@router.put("/preferences", response_model=UserPreferenceResponse)
async def update_user_preferences(
    data: UserPreferenceUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Update user notification and subscription preferences.
    
    Args:
        data: User preference update data
        db: Database session
        current_user: Current authenticated user
        notification_service: Notification service for preference management
        
    Returns:
        Updated user preferences
    """
    try:
        user_prefs = await notification_service.update_user_preferences(db, current_user["id"], data)
        return user_prefs
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user preferences")


@router.post("/preferences/quiet-hours", response_model=UserPreferenceResponse)
async def set_quiet_hours(
    quiet_hours: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Set quiet hours for notifications.
    
    Args:
        quiet_hours: Quiet hours configuration
        db: Database session
        current_user: Current authenticated user
        notification_service: Notification service for preference management
        
    Returns:
        Updated user preferences
    """
    try:
        user_prefs = await notification_service.set_quiet_hours(db, current_user["id"], quiet_hours)
        return user_prefs
    except Exception as e:
        logger.error(f"Error setting quiet hours: {e}")
        raise HTTPException(status_code=500, detail="Failed to set quiet hours")


@router.post("/preferences/categories", response_model=UserPreferenceResponse)
async def set_enabled_categories(
    categories: List[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Set enabled notification categories.
    
    Args:
        categories: List of enabled categories
        db: Database session
        current_user: Current authenticated user
        notification_service: Notification service for preference management
        
    Returns:
        Updated user preferences
    """
    try:
        user_prefs = await notification_service.set_enabled_categories(db, current_user["id"], categories)
        return user_prefs
    except Exception as e:
        logger.error(f"Error setting enabled categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to set enabled categories")


@router.post("/preferences/feed", response_model=UserPreferenceResponse)
async def set_feed_preferences(
    feed_preferences: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    notification_service: NotificationService = Depends(get_notification_service)
):
    """
    Set feed display preferences.
    
    Args:
        feed_preferences: Feed preferences configuration
        db: Database session
        current_user: Current authenticated user
        notification_service: Notification service for preference management
        
    Returns:
        Updated user preferences
    """
    try:
        user_prefs = await notification_service.set_feed_preferences(db, current_user["id"], feed_preferences)
        return user_prefs
    except Exception as e:
        logger.error(f"Error setting feed preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to set feed preferences")
