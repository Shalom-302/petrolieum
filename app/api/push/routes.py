"""
API routes for push notifications
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Dict, Any
import json
from pydantic import ValidationError
from datetime import datetime

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.advanced_auth.models.user import User
from app.plugins.pwa_support.models import PushSubscription
from app.schemas.push import (
    PushSubscriptionCreate,
    PushSubscriptionResponse, 
    PushSubscriptionStatus
)

router = APIRouter(prefix="/push", tags=["push"])

# VAPID keys to authenticate server-side push notifications
# These keys must be generated and stored in environment variables
VAPID_PUBLIC_KEY = "BNbKwE-dZP9pbrGrnSRLHgQpCkxnaYWzlvJUBYbMO0FCyNgknmDSQNb__luXyUS8Vtr7HGdQvnD-hFNjN9jd2XU"


@router.get("/vapid-public-key", response_model=Dict[str, str])
async def get_vapid_public_key():
    """Get the VAPID public key for push subscriptions"""
    return {"publicKey": VAPID_PUBLIC_KEY}


@router.post("/subscribe", response_model=PushSubscriptionResponse)
async def subscribe_to_push(
    subscription: PushSubscriptionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Register a new push subscription for the current user"""
    # Check if an existing subscription exists with this endpoint
    sub_data = subscription.subscription.copy()
    if not isinstance(sub_data, dict):
        try:
            sub_data = json.loads(sub_data) if isinstance(sub_data, str) else {}
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid subscription data format"
            )
    
    # Extract necessary subscription data from the payload
    endpoint = sub_data.get("endpoint")
    keys = sub_data.get("keys", {})
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    
    if not endpoint or not p256dh or not auth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required subscription data (endpoint, p256dh, auth)"
        )
    
    # Check if this endpoint already exists for this user
    existing_subscription = db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id,
        PushSubscription.endpoint == endpoint
    ).first()
    
    if existing_subscription:
        # Update existing subscription data
        existing_subscription.p256dh = p256dh
        existing_subscription.auth = auth
        existing_subscription.last_used = datetime.utcnow()
        
        # Update metadata if provided
        if subscription.userAgent:
            existing_subscription.user_agent = subscription.userAgent
        if hasattr(subscription, 'deviceType') and subscription.deviceType:
            existing_subscription.device_type = subscription.deviceType
        if hasattr(subscription, 'language') and subscription.language:
            existing_subscription.language = subscription.language
        if hasattr(subscription, 'tags') and subscription.tags:
            existing_subscription.tags = json.dumps(subscription.tags)
            
        db.commit()
        db.refresh(existing_subscription)
        return PushSubscriptionResponse(
            id=str(existing_subscription.id),
            isSubscribed=True,
            message="Subscription updated successfully"
        )
    
    # Extract optional metadata
    user_agent = subscription.userAgent if hasattr(subscription, 'userAgent') else None
    device_type = subscription.deviceType if hasattr(subscription, 'deviceType') else None
    language = subscription.language if hasattr(subscription, 'language') else None
    tags = json.dumps(subscription.tags) if hasattr(subscription, 'tags') and subscription.tags else None
    
    # Create a new subscription
    new_subscription = PushSubscription(
        user_id=current_user.id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=user_agent,
        device_type=device_type,
        language=language,
        tags=tags,
        created_at=datetime.utcnow(),
        last_used=datetime.utcnow()
    )
    db.add(new_subscription)
    
    try:
        db.commit()
        db.refresh(new_subscription)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription already exists"
        )
    
    return PushSubscriptionResponse(
        id=str(new_subscription.id),
        isSubscribed=True,
        message="Subscription created successfully"
    )


@router.post("/unsubscribe", response_model=PushSubscriptionResponse)
async def unsubscribe_from_push(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Unsubscribe from push notifications for the current user"""
    # Find all subscriptions for this user
    subscriptions = db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id
    ).all()
    
    if not subscriptions:
        return PushSubscriptionResponse(
            id=None,
            isSubscribed=False,
            message="No subscriptions found to remove"
        )
    
    # Delete all subscriptions for this user
    for subscription in subscriptions:
        db.delete(subscription)
    
    db.commit()
    return PushSubscriptionResponse(
        id=None,
        isSubscribed=False,
        message="All subscriptions removed successfully"
    )


@router.get("/status", response_model=PushSubscriptionStatus)
async def get_push_subscription_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Check if the current user is subscribed to push notifications"""
    # Count the number of subscriptions for this user
    subscription_count = db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id
    ).count()
    
    return PushSubscriptionStatus(
        isSubscribed=subscription_count > 0
    )
