"""
Subscription routes for the payment plugin.

This module defines the API endpoints for managing subscriptions.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.advanced_auth.models import User
from app.core.security import get_current_user

from ..models.subscription import (
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    SubscriptionCancelRequest, SubscriptionPauseRequest
)
from ..utils.subscription_service import (
    create_subscription_service, activate_subscription_service,
    update_subscription_service, cancel_subscription_service,
    pause_subscription_service, resume_subscription_service,
    verify_subscription_service, get_subscription_service,
    list_subscriptions_service, create_invoice_for_subscription
)

router = APIRouter()

@router.post("/", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new subscription.
    """
    return await create_subscription_service(db, subscription, current_user)

@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get subscription details by ID.
    """
    subscription = await get_subscription_service(db, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription {subscription_id} not found"
        )
    return subscription

@router.get("/", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List subscriptions with optional filtering by customer ID and status.
    """
    return await list_subscriptions_service(db, customer_id, status, skip, limit)

@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    update_data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update subscription details.
    """
    return await update_subscription_service(db, subscription_id, update_data, current_user)

@router.post("/{subscription_id}/activate", response_model=SubscriptionResponse)
async def activate_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Activate a subscription with the payment provider.
    """
    return await activate_subscription_service(db, subscription_id, current_user)

@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: int,
    cancel_request: SubscriptionCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a subscription.
    """
    return await cancel_subscription_service(db, subscription_id, cancel_request, current_user)

@router.post("/{subscription_id}/pause", response_model=SubscriptionResponse)
async def pause_subscription(
    subscription_id: int,
    pause_request: SubscriptionPauseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Pause a subscription.
    """
    return await pause_subscription_service(db, subscription_id, pause_request, current_user)

@router.post("/{subscription_id}/resume", response_model=SubscriptionResponse)
async def resume_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resume a paused subscription.
    """
    return await resume_subscription_service(db, subscription_id, current_user)

@router.post("/{subscription_id}/verify", response_model=SubscriptionResponse)
async def verify_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify subscription status with the provider.
    """
    return await verify_subscription_service(db, subscription_id, current_user)

@router.post("/{subscription_id}/invoice")
async def create_invoice(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new invoice/payment for a subscription.
    """
    return await create_invoice_for_subscription(db, subscription_id, current_user)
