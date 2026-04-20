"""
Refund routes for the payment plugin.

This module defines API routes for refund operations.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query

from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.advanced_auth.models import User

from ..models.payment import RefundCreate, RefundResponse
from ..utils.refund_service import (
    create_refund,
    process_refund,
    cancel_refund,
    get_refund,
    get_refunds_for_payment,
    verify_refund_status
)

logger = logging.getLogger("kaapi.payment.refund_routes")

router = APIRouter()


@router.post("/{payment_id}", response_model=RefundResponse)
async def create_refund_route(
    payment_id: int = Path(..., description="Payment ID to refund"),
    refund: RefundCreate = Body(..., description="Refund details"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new refund request for a payment.
    
    This creates a refund request but does not process it.
    The request will be created in PENDING status and must be
    processed separately.
    
    Regular users can only refund their own payments,
    while superusers can refund any payment.
    """
    return await create_refund(
        db=db,
        payment_id=payment_id,
        refund=refund,
        current_user=current_user
    )


@router.get("/{payment_id}", response_model=List[RefundResponse])
async def get_refunds_for_payment_route(
    payment_id: int = Path(..., description="Payment ID"),
    status: Optional[str] = Query(None, description="Filter by refund status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all refunds for a specific payment.
    
    Regular users can only view refunds for their own payments,
    while superusers can view refunds for any payment.
    """
    return await get_refunds_for_payment(
        db=db,
        payment_id=payment_id,
        status=status,
        current_user=current_user
    )


@router.get("/{payment_id}/{refund_id}", response_model=RefundResponse)
async def get_refund_route(
    payment_id: int = Path(..., description="Payment ID"),
    refund_id: int = Path(..., description="Refund ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get details of a specific refund.
    
    Regular users can only view refunds for their own payments,
    while superusers can view any refund.
    """
    return await get_refund(
        db=db,
        refund_id=refund_id,
        payment_id=payment_id,
        current_user=current_user
    )


@router.post("/{payment_id}/{refund_id}/process", response_model=RefundResponse)
async def process_refund_route(
    payment_id: int = Path(..., description="Payment ID"),
    refund_id: int = Path(..., description="Refund ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Process a refund request.
    
    This will initiate the refund processing through the appropriate
    payment provider. The refund must be in PENDING status.
    
    Regular users can only process refunds for their own payments,
    while superusers can process any refund.
    """
    return await process_refund(
        db=db,
        refund_id=refund_id,
        payment_id=payment_id,
        current_user=current_user
    )


@router.post("/{payment_id}/{refund_id}/cancel", response_model=RefundResponse)
async def cancel_refund_route(
    payment_id: int = Path(..., description="Payment ID"),
    refund_id: int = Path(..., description="Refund ID"),
    reason: str = Body(..., embed=True, description="Reason for cancellation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cancel a refund request.
    
    This will cancel the refund request and notify the payment provider if necessary.
    The refund must be in PENDING status.
    
    Regular users can only cancel refunds for their own payments,
    while superusers can cancel any refund.
    """
    return await cancel_refund(
        db=db,
        refund_id=refund_id,
        payment_id=payment_id,
        reason=reason,
        current_user=current_user
    )


@router.get("/{payment_id}/{refund_id}/verify", response_model=RefundResponse)
async def verify_refund_status_route(
    payment_id: int = Path(..., description="Payment ID"),
    refund_id: int = Path(..., description="Refund ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Verify the status of a refund with the payment provider.
    
    This will check the current status of the refund with the payment provider
    and update the local database if necessary.
    
    Regular users can only verify refunds for their own payments,
    while superusers can verify any refund.
    """
    return await verify_refund_status(
        db=db,
        refund_id=refund_id,
        payment_id=payment_id,
        current_user=current_user
    )
