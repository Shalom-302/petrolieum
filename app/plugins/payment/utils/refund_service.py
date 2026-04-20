"""
Refund service for the payment plugin.

This module handles the business logic for processing refunds.
"""
import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.plugins.advanced_auth.models import User
from ..models.payment import (
    PaymentDB, 
    PaymentStatus, 
    PaymentRefundDB,
    RefundStatus,
    PaymentTransactionDB,
    RefundCreate
)
from ..models.provider import RefundRequest, ProviderResponse
from ..providers.provider_factory import PaymentProviderFactory
from .notification_service import PaymentNotificationService

logger = logging.getLogger("kaapi.payment.refund")

async def create_refund(
    db: Session,
    payment_id: int,
    refund_data: RefundCreate,
    current_user: User
) -> PaymentRefundDB:
    """
    Create a refund request for a payment.
    
    Args:
        db: Database session
        payment_id: Payment ID to refund
        refund_data: Refund data
        current_user: Current user
    
    Returns:
        Created refund
    
    Raises:
        ValueError: If payment does not exist or cannot be refunded
    """
    # Get payment
    payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    if not payment:
        raise ValueError(f"Payment with ID {payment_id} not found")
    
    # Check if payment is refundable
    if payment.status not in [PaymentStatus.COMPLETED.value]:
        raise ValueError(f"Payment with status {payment.status} cannot be refunded")
    
    # Check if refund amount is valid
    if refund_data.amount <= 0:
        raise ValueError("Refund amount must be greater than 0")
    
    # Calculate available refund amount
    available_amount = payment.amount - payment.refunded_amount
    if refund_data.amount > available_amount:
        raise ValueError(f"Refund amount {refund_data.amount} exceeds available amount {available_amount}")
    
    # Create refund record
    refund = PaymentRefundDB(
        payment_id=payment_id,
        reference=f"ref-{str(uuid.uuid4())}",
        amount=refund_data.amount,
        currency=payment.currency,
        reason=refund_data.reason,
        status=RefundStatus.PENDING.value,
        provider=payment.provider,
        refund_metadata=refund_data.refund_metadata,
        refunded_by_id=current_user.id
    )
    
    db.add(refund)
    db.commit()
    db.refresh(refund)
    
    return refund

async def process_refund(
    db: Session,
    refund_id: int,
    current_user: User
) -> PaymentRefundDB:
    """
    Process a refund with the payment provider.
    
    Args:
        db: Database session
        refund_id: Refund ID to process
        current_user: Current user
    
    Returns:
        Processed refund
    
    Raises:
        ValueError: If refund does not exist or cannot be processed
    """
    # Get refund
    refund = db.query(PaymentRefundDB).filter(PaymentRefundDB.id == refund_id).first()
    if not refund:
        raise ValueError(f"Refund with ID {refund_id} not found")
    
    # Check if refund can be processed
    if refund.status != RefundStatus.PENDING.value:
        raise ValueError(f"Refund with status {refund.status} cannot be processed")
    
    # Get payment
    payment = db.query(PaymentDB).filter(PaymentDB.id == refund.payment_id).first()
    if not payment:
        raise ValueError(f"Payment with ID {refund.payment_id} not found")
    
    # Update refund status
    refund.status = RefundStatus.PROCESSING.value
    db.commit()
    db.refresh(refund)
    
    # Get provider
    provider = PaymentProviderFactory.get_provider(payment.provider)
    if not provider:
        logger.error(f"Provider {payment.provider} not found")
        refund.status = RefundStatus.FAILED.value
        db.commit()
        db.refresh(refund)
        raise ValueError(f"Provider {payment.provider} not found")
    
    # Prepare refund request
    refund_request = RefundRequest(
        amount=refund.amount,
        currency=refund.currency,
        payment_reference=payment.provider_reference,
        reason=refund.reason,
        metadata={
            "refund_id": refund.id,
            "payment_id": payment.id,
            "refund_reference": refund.reference
        }
    )
    
    try:
        # Process refund with provider
        response = await provider.process_refund(refund_request)
        
        # Update refund with provider response
        refund.provider_reference = response.provider_reference
        refund.status = response.status.value
        
        # Create transaction record
        transaction = PaymentTransactionDB(
            payment_id=payment.id,
            reference=f"tx-{str(uuid.uuid4())}",
            amount=refund.amount,
            status=response.status.value,
            provider=payment.provider,
            provider_reference=response.provider_reference,
            transaction_type="refund",
            metadata={
                "refund_id": refund.id,
                "reason": refund.reason,
                "response": response.raw_response
            }
        )
        db.add(transaction)
        
        # Update payment stats
        if response.success:
            payment.refunded_amount += refund.amount
            
            # Check if payment is fully refunded
            if payment.refunded_amount >= payment.amount:
                payment.is_fully_refunded = True
                payment.status = PaymentStatus.REFUNDED.value
            else:
                payment.status = PaymentStatus.PARTIALLY_REFUNDED.value
        
        db.commit()
        db.refresh(refund)
        
        # Send notification
        await PaymentNotificationService.send_refund_notification(
            db=db,
            refund=refund, 
            payment=payment,
            success=response.success
        )
        
        return refund
    
    except Exception as e:
        logger.error(f"Error processing refund: {str(e)}")
        refund.status = RefundStatus.FAILED.value
        db.commit()
        db.refresh(refund)
        raise ValueError(f"Error processing refund: {str(e)}")

async def cancel_refund(
    db: Session,
    refund_id: int,
    current_user: User
) -> PaymentRefundDB:
    """
    Cancel a pending refund.
    
    Args:
        db: Database session
        refund_id: Refund ID to cancel
        current_user: Current user
    
    Returns:
        Cancelled refund
    
    Raises:
        ValueError: If refund does not exist or cannot be cancelled
    """
    # Get refund
    refund = db.query(PaymentRefundDB).filter(PaymentRefundDB.id == refund_id).first()
    if not refund:
        raise ValueError(f"Refund with ID {refund_id} not found")
    
    # Check if refund can be cancelled
    if refund.status != RefundStatus.PENDING.value:
        raise ValueError(f"Refund with status {refund.status} cannot be cancelled")
    
    # Cancel refund
    refund.status = RefundStatus.FAILED.value
    refund.refund_metadata = {
        **(refund.refund_metadata or {}),
        "cancelled_by": current_user.id,
        "cancelled_at": datetime.utcnow().isoformat(),
        "cancelled_reason": "Cancelled by user"
    }
    
    db.commit()
    db.refresh(refund)
    
    return refund

async def get_refund(
    db: Session, 
    refund_id: int
) -> PaymentRefundDB:
    """
    Get a refund by ID.
    
    Args:
        db: Database session
        refund_id: Refund ID
    
    Returns:
        Refund
        
    Raises:
        ValueError: If refund does not exist
    """
    refund = db.query(PaymentRefundDB).filter(PaymentRefundDB.id == refund_id).first()
    if not refund:
        raise ValueError(f"Refund with ID {refund_id} not found")
    
    return refund

async def get_refunds_for_payment(
    db: Session,
    payment_id: int
) -> List[PaymentRefundDB]:
    """
    Get all refunds for a payment.
    
    Args:
        db: Database session
        payment_id: Payment ID
    
    Returns:
        List of refunds
    """
    return db.query(PaymentRefundDB).filter(PaymentRefundDB.payment_id == payment_id).all()

async def verify_refund_status(
    db: Session,
    refund_id: int
) -> PaymentRefundDB:
    """
    Verify the status of a refund with the payment provider.
    
    Args:
        db: Database session
        refund_id: Refund ID
    
    Returns:
        Updated refund
        
    Raises:
        ValueError: If refund does not exist
    """
    # Get refund
    refund = db.query(PaymentRefundDB).filter(PaymentRefundDB.id == refund_id).first()
    if not refund:
        raise ValueError(f"Refund with ID {refund_id} not found")
    
    # Skip verification for refunds that are already completed or failed
    if refund.status in [RefundStatus.COMPLETED.value, RefundStatus.FAILED.value]:
        return refund
    
    # Get payment
    payment = db.query(PaymentDB).filter(PaymentDB.id == refund.payment_id).first()
    if not payment:
        raise ValueError(f"Payment with ID {refund.payment_id} not found")
    
    # Get provider
    provider = PaymentProviderFactory.get_provider(payment.provider)
    if not provider:
        logger.error(f"Provider {payment.provider} not found")
        return refund
    
    try:
        # Verify refund status with provider
        response = await provider.verify_refund(refund.provider_reference)
        
        # Update refund status
        if response.success and response.status != RefundStatus(refund.status):
            refund.status = response.status.value
            
            # If refund is completed, update payment stats
            if response.status == RefundStatus.COMPLETED and refund.status != RefundStatus.COMPLETED.value:
                # Update payment stats if not already counted
                payment.refunded_amount += refund.amount
                
                # Check if payment is fully refunded
                if payment.refunded_amount >= payment.amount:
                    payment.is_fully_refunded = True
                    payment.status = PaymentStatus.REFUNDED.value
                else:
                    payment.status = PaymentStatus.PARTIALLY_REFUNDED.value
            
            db.commit()
            db.refresh(refund)
        
        return refund
    
    except Exception as e:
        logger.error(f"Error verifying refund status: {str(e)}")
        return refund
