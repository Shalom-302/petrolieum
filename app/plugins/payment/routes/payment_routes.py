"""
API routes for the payment plugin.

This module contains API routes for the payment plugin.
"""
import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.plugins.advanced_auth.models import User
from app.core.db import get_db
from ..models.payment import (
    PaymentCreate, 
    PaymentUpdate,
    PaymentResponse,
    PaymentApproval
)
from ..utils.payment_service import (
    get_payments,
    get_payment_by_id,
    create_payment_service,
    update_payment_service,
    process_payment_service,
    cancel_payment_service,
    approve_payment_service,
    reject_payment_service,
    get_available_providers,
    get_available_payment_methods
)

logger = logging.getLogger("kaapi.payment.routes")

router = APIRouter()

@router.get("/", response_model=List[PaymentResponse])
async def list_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = Query(None)
):
    """
    List payments with optional filters.
    
    Regular users can only see their own payments,
    while superusers can see all payments.
    """
    return await get_payments(
        db=db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        status=status
    )

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific payment by ID.
    
    Regular users can only access their own payments,
    while superusers can access any payment.
    """
    return await get_payment_by_id(
        db=db,
        payment_id=payment_id,
        current_user=current_user
    )

@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new payment.
    
    The payment will be created with the specified details and
    will be linked to the current user.
    """
    return await create_payment_service(
        db=db,
        payment=payment,
        current_user=current_user
    )

@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: int,
    payment: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update an existing payment.
    
    Regular users can only update their own payments,
    while superusers can update any payment.
    """
    return await update_payment_service(
        db=db,
        payment_id=payment_id,
        payment=payment,
        current_user=current_user
    )

@router.post("/{payment_id}/process", response_model=PaymentResponse)
async def process_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Process a payment.
    
    This will initiate the payment processing through the appropriate
    payment provider. The payment must be in DRAFT or APPROVED status.
    
    Regular users can only process their own payments,
    while superusers can process any payment.
    """
    return await process_payment_service(
        db=db,
        payment_id=payment_id,
        current_user=current_user
    )

@router.post("/{payment_id}/cancel", response_model=PaymentResponse)
async def cancel_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cancel a payment.
    
    This will cancel the payment and notify the payment provider if necessary.
    
    Regular users can only cancel their own payments,
    while superusers can cancel any payment.
    """
    return await cancel_payment_service(
        db=db,
        payment_id=payment_id,
        current_user=current_user
    )

@router.post("/{payment_id}/approve", response_model=PaymentResponse)
async def approve_payment(
    payment_id: int,
    approval: PaymentApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Approve a payment.
    
    This is used in multi-user approval workflows where multiple
    approvers are required for a payment to be processed.
    
    Only users who are in the list of approvers for the payment can approve it.
    """
    return await approve_payment_service(
        db=db,
        payment_id=payment_id,
        approval=approval,
        current_user=current_user
    )

@router.post("/{payment_id}/reject", response_model=PaymentResponse)
async def reject_payment(
    payment_id: int,
    reason: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Reject a payment.
    
    This is used in multi-user approval workflows where multiple
    approvers are required for a payment to be processed.
    
    Only users who are in the list of approvers for the payment can reject it.
    A reason for rejection must be provided.
    """
    return await reject_payment_service(
        db=db,
        payment_id=payment_id,
        reason=reason,
        current_user=current_user
    )

@router.get("/providers", response_model=List[Dict[str, Any]])
async def list_providers(
    current_user: User = Depends(get_current_active_user)
):
    """
    List all available payment providers.
    
    This endpoint returns information about all the payment providers
    that are currently configured and enabled in the system.
    """
    return await get_available_providers()

@router.get("/methods", response_model=List[Dict[str, Any]])
async def list_payment_methods(
    current_user: User = Depends(get_current_active_user)
):
    """
    List all available payment methods.
    
    This endpoint returns information about all the payment methods
    that are supported by the enabled payment providers.
    """
    return await get_available_payment_methods()
