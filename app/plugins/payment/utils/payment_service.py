"""
Payment service for the payment plugin.

This module contains business logic for payment operations.
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.plugins.advanced_auth.models import User
from ..models.payment import (
    PaymentDB, 
    PaymentCreate, 
    PaymentUpdate, 
    PaymentStatus,
    PaymentMethod,
    PaymentResponse,
    PaymentApproval,
    PaymentTransactionDB
)
from ..models.provider import PaymentRequest, ProviderResponse
from ..providers.provider_factory import PaymentProviderFactory
from ..workflows.approval_workflow import payment_approval_workflow
from ..utils.config import payment_settings

logger = logging.getLogger("kaapi.payment.service")

async def get_payments(
    db: Session, 
    current_user: User,
    skip: int = 0, 
    limit: int = 100,
    status: Optional[str] = None
) -> List[PaymentResponse]:
    """Get a list of payments."""
    query = db.query(PaymentDB)
    
    # Apply status filter if provided
    if status:
        query = query.filter(PaymentDB.status == status)
    
    # Apply user filter based on role
    if not current_user.is_superuser:
        # Regular users only see their own payments
        query = query.filter(
            (PaymentDB.created_by_id == current_user.id) | 
            (PaymentDB.customer_id == current_user.id)
        )
    
    # Fetch payments with pagination
    payments = query.order_by(PaymentDB.created_at.desc()).offset(skip).limit(limit).all()
    
    # Convert to response model
    return [PaymentResponse.from_orm(payment) for payment in payments]

async def get_payment_by_id(
    db: Session, 
    payment_id: int, 
    current_user: User
) -> PaymentResponse:
    """Get a specific payment by ID."""
    payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Check permissions
    if not current_user.is_superuser and payment.created_by_id != current_user.id and payment.customer_id != current_user.id:
        # Check if user is an approver
        is_approver = current_user.id in [approver.id for approver in payment.approvers]
        
        if not is_approver:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this payment"
            )
    
    return PaymentResponse.from_orm(payment)

async def create_payment_service(
    db: Session,
    payment: PaymentCreate,
    current_user: User
) -> PaymentResponse:
    """Create a new payment."""
    # Generate a unique reference
    reference = str(uuid.uuid4())
    
    # Create payment record
    db_payment = PaymentDB(
        reference=reference,
        amount=payment.amount,
        currency=payment.currency.value,
        description=payment.description,
        status=PaymentStatus.DRAFT.value,
        payment_method=payment.payment_method.value,
        provider=payment.provider,
        payment_metadata=payment.payment_metadata,
        created_by_id=current_user.id,
        customer_id=payment.customer_id or current_user.id
    )
    
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    
    # If approval is required, start approval workflow
    if payment.require_approval and payment.approvers:
        try:
            workflow_name = payment.approval_workflow or "standard_payment_approval"
            await payment_approval_workflow["start"](
                db=db,
                payment_id=db_payment.id,
                workflow_name=workflow_name,
                approvers=payment.approvers,
                initiated_by=current_user.id
            )
        except Exception as e:
            logger.error(f"Error starting payment approval workflow: {e}")
            # Don't fail the payment creation if workflow fails
            # Just log the error and continue
    
    return PaymentResponse.from_orm(db_payment)

async def update_payment_service(
    db: Session,
    payment_id: int,
    payment: PaymentUpdate,
    current_user: User
) -> PaymentResponse:
    """Update a payment."""
    db_payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    
    if not db_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Check permissions
    if not current_user.is_superuser and db_payment.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this payment"
        )
    
    # Check if payment is in a state that allows updates
    if db_payment.status not in [PaymentStatus.DRAFT.value, PaymentStatus.FAILED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update payment in {db_payment.status} status"
        )
    
    # Update fields
    if payment.amount is not None:
        db_payment.amount = payment.amount
    
    if payment.currency is not None:
        db_payment.currency = payment.currency.value
    
    if payment.payment_method is not None:
        db_payment.payment_method = payment.payment_method.value
    
    if payment.description is not None:
        db_payment.description = payment.description
    
    if payment.payment_metadata is not None:
        db_payment.payment_metadata = payment.payment_metadata
    
    if payment.provider is not None:
        db_payment.provider = payment.provider
    
    db_payment.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_payment)
    
    return PaymentResponse.from_orm(db_payment)

async def process_payment_service(
    db: Session,
    payment_id: int,
    current_user: User
) -> PaymentResponse:
    """Process a payment through the appropriate payment provider."""
    db_payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    
    if not db_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Check permissions
    if not current_user.is_superuser and db_payment.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process this payment"
        )
    
    # Check if payment status allows processing
    allowed_statuses = [
        PaymentStatus.DRAFT.value, 
        PaymentStatus.APPROVED.value,
        PaymentStatus.FAILED.value
    ]
    
    if db_payment.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot process payment in {db_payment.status} status"
        )
    
    # If payment needs approval and hasn't been approved yet
    if db_payment.approval_steps and db_payment.status != PaymentStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment requires approval before processing"
        )
    
    # Get the payment provider
    provider_id = db_payment.provider
    if not provider_id:
        # Auto-select provider based on payment method and currency
        provider_id = await _select_provider(db_payment.payment_method, db_payment.currency)
    
    provider = PaymentProviderFactory.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment provider '{provider_id}' not found or not enabled"
        )
    
    # Get customer information
    customer = await _get_customer_info(db, db_payment.customer_id)
    
    # Create payment request
    payment_request = PaymentRequest(
        amount=db_payment.amount,
        currency=db_payment.currency,
        payment_method=db_payment.payment_method,
        customer=customer,
        metadata={
            "payment_id": db_payment.id,
            "reference": db_payment.reference,
            "description": db_payment.description,
            **(db_payment.payment_metadata if db_payment.payment_metadata else {})
        },
        description=db_payment.description or f"Payment {db_payment.reference}",
        return_url=payment_settings.get_return_url(db_payment.id),
        cancel_url=payment_settings.get_cancel_url(db_payment.id),
        webhook_url=payment_settings.get_webhook_url(provider_id)
    )
    
    # Process payment through provider
    try:
        # Update payment status to processing
        db_payment.status = PaymentStatus.PROCESSING.value
        db_payment.updated_at = datetime.utcnow()
        db.commit()
        
        # Process payment
        result = await provider.process_payment(payment_request)
        
        # Update payment based on result
        db_payment.status = result.status.value
        db_payment.provider_reference = result.provider_reference
        db_payment.updated_at = datetime.utcnow()
        
        # Create transaction record
        transaction = PaymentTransactionDB(
            payment_id=db_payment.id,
            reference=str(uuid.uuid4()),
            amount=db_payment.amount,
            status=result.status.value,
            provider=provider_id,
            provider_reference=result.provider_reference,
            transaction_type="payment",
            metadata=result.raw_response
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(db_payment)
        
        # Create response with payment URL if available
        response = PaymentResponse.from_orm(db_payment)
        if result.payment_url:
            response.payment_url = result.payment_url
        
        return response
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing payment {db_payment.id}: {e}")
        
        # Update payment status to failed
        db_payment.status = PaymentStatus.FAILED.value
        db_payment.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_payment)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {str(e)}"
        )

async def cancel_payment_service(
    db: Session,
    payment_id: int,
    current_user: User
) -> PaymentResponse:
    """Cancel a payment."""
    db_payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    
    if not db_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Check permissions
    if not current_user.is_superuser and db_payment.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this payment"
        )
    
    # Check if payment status allows cancellation
    if db_payment.status in [PaymentStatus.COMPLETED.value, PaymentStatus.CANCELLED.value, PaymentStatus.REFUNDED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel payment in {db_payment.status} status"
        )
    
    # If payment has a provider reference, try to cancel with provider
    if db_payment.provider_reference and db_payment.provider:
        provider = PaymentProviderFactory.get_provider(db_payment.provider)
        if provider:
            try:
                result = await provider.cancel_payment(db_payment.provider_reference)
                if result.success:
                    # Provider successfully cancelled the payment
                    pass
                else:
                    # Provider couldn't cancel, but we'll still cancel in our system
                    logger.warning(f"Provider couldn't cancel payment {db_payment.id}: {result.message}")
            except Exception as e:
                logger.error(f"Error cancelling payment with provider: {e}")
                # Continue with cancellation in our system
    
    # Cancel the payment in our system
    db_payment.status = PaymentStatus.CANCELLED.value
    db_payment.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_payment)
    
    return PaymentResponse.from_orm(db_payment)

async def approve_payment_service(
    db: Session,
    payment_id: int,
    approval: PaymentApproval,
    current_user: User
) -> PaymentResponse:
    """Approve a payment in a multi-user approval workflow."""
    db_payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    
    if not db_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Check if payment requires approval
    if db_payment.status != PaymentStatus.PENDING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment is not pending approval (status: {db_payment.status})"
        )
    
    # Use the approval workflow to approve
    try:
        result = await payment_approval_workflow["approve"](
            db=db,
            payment_id=payment_id,
            user_id=current_user.id,
            comments=approval.comments
        )
        
        # Refresh payment after approval
        db.refresh(db_payment)
        
        return PaymentResponse.from_orm(db_payment)
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error approving payment {payment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving payment: {str(e)}"
        )

async def reject_payment_service(
    db: Session,
    payment_id: int,
    reason: str,
    current_user: User
) -> PaymentResponse:
    """Reject a payment in a multi-user approval workflow."""
    db_payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    
    if not db_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Check if payment requires approval
    if db_payment.status != PaymentStatus.PENDING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment is not pending approval (status: {db_payment.status})"
        )
    
    # Use the approval workflow to reject
    try:
        result = await payment_approval_workflow["reject"](
            db=db,
            payment_id=payment_id,
            user_id=current_user.id,
            reason=reason
        )
        
        # Refresh payment after rejection
        db.refresh(db_payment)
        
        return PaymentResponse.from_orm(db_payment)
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error rejecting payment {payment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting payment: {str(e)}"
        )

async def get_available_providers() -> List[ProviderResponse]:
    """Get available payment providers."""
    return PaymentProviderFactory.get_all_providers()

async def get_available_payment_methods() -> List[Dict[str, Any]]:
    """Get available payment methods."""
    methods = []
    
    for method in PaymentMethod:
        method_info = {
            "id": method.value,
            "name": method.name.replace('_', ' ').title(),
            "description": _get_payment_method_description(method),
            "icon": _get_payment_method_icon(method),
            "is_african": method.value in [
                "mobile_money", "m_pesa", "orange_money", "mtn_mobile_money", 
                "airtel_money", "wave", "senegal_wave", "moov_money", 
                "ecocash", "chipper_cash", "africa_paydo", "flw_bank_transfer", "ussd"
            ]
        }
        methods.append(method_info)
    
    return methods

async def _select_provider(payment_method: str, currency: str) -> str:
    """Select an appropriate provider based on payment method and currency."""
    providers = PaymentProviderFactory.get_all_providers()
    
    for provider in providers:
        if payment_method in [m.value for m in provider.supported_methods] and \
           currency in [c.value for c in provider.supported_currencies] and \
           provider.is_enabled:
            return provider.id
    
    # Default to a globally available provider if no specific match
    # Or raise an exception if none available
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"No provider available for payment method '{payment_method}' and currency '{currency}'"
    )

async def _get_customer_info(db: Session, customer_id: int) -> Dict[str, Any]:
    """Get customer information for payment processing."""
    user = db.query(User).filter(User.id == customer_id).first()
    
    if not user:
        return {
            "email": "unknown@example.com",
            "name": "Unknown Customer",
            "phone": ""
        }
    
    return {
        "email": user.email,
        "name": f"{user.first_name} {user.last_name}" if hasattr(user, "first_name") else user.email,
        "phone": user.phone if hasattr(user, "phone") else "",
        "user_id": user.id
    }

def _get_payment_method_description(method: PaymentMethod) -> str:
    """Get a description for a payment method."""
    descriptions = {
        PaymentMethod.CREDIT_CARD: "Pay using your credit card",
        PaymentMethod.DEBIT_CARD: "Pay using your debit card",
        PaymentMethod.BANK_TRANSFER: "Pay via bank transfer",
        PaymentMethod.PAYPAL: "Pay via PayPal",
        PaymentMethod.APPLE_PAY: "Pay with Apple Pay",
        PaymentMethod.GOOGLE_PAY: "Pay with Google Pay",
        PaymentMethod.CRYPTOCURRENCY: "Pay with cryptocurrency",
        
        PaymentMethod.MOBILE_MONEY: "Pay using mobile money services",
        PaymentMethod.M_PESA: "Pay using M-Pesa mobile money service",
        PaymentMethod.ORANGE_MONEY: "Pay using Orange Money",
        PaymentMethod.MTN_MOBILE_MONEY: "Pay using MTN Mobile Money",
        PaymentMethod.AIRTEL_MONEY: "Pay using Airtel Money",
        PaymentMethod.WAVE: "Pay using Wave",
        PaymentMethod.SENEGAL_WAVE: "Pay using Wave in Senegal",
        PaymentMethod.MOOV_MONEY: "Pay using Moov Money",
        PaymentMethod.ECOCASH: "Pay using EcoCash",
        PaymentMethod.CHIPPER_CASH: "Pay using Chipper Cash",
        PaymentMethod.AFRICA_PAYDO: "Pay using Africa PayDo",
        PaymentMethod.FLW_BANK_TRANSFER: "Pay using Flutterwave bank transfer",
        PaymentMethod.USSD: "Pay using USSD",
        
        PaymentMethod.CASH_ON_DELIVERY: "Pay cash on delivery",
        PaymentMethod.STORE_CREDIT: "Pay using store credit",
        PaymentMethod.VOUCHER: "Pay using a voucher",
        PaymentMethod.OTHER: "Other payment method"
    }
    
    return descriptions.get(method, "Pay using " + method.value.replace('_', ' ').title())

def _get_payment_method_icon(method: PaymentMethod) -> str:
    """Get an icon for a payment method."""
    # These would be replaced with actual icon URLs in a real implementation
    icons = {
        PaymentMethod.CREDIT_CARD: "fa-credit-card",
        PaymentMethod.DEBIT_CARD: "fa-credit-card",
        PaymentMethod.BANK_TRANSFER: "fa-university",
        PaymentMethod.PAYPAL: "fa-paypal",
        PaymentMethod.APPLE_PAY: "fa-apple",
        PaymentMethod.GOOGLE_PAY: "fa-google",
        PaymentMethod.CRYPTOCURRENCY: "fa-bitcoin",
        
        PaymentMethod.MOBILE_MONEY: "fa-mobile-alt",
        PaymentMethod.M_PESA: "fa-money-bill-wave",
        PaymentMethod.ORANGE_MONEY: "fa-money-bill",
        PaymentMethod.MTN_MOBILE_MONEY: "fa-money-bill",
        PaymentMethod.AIRTEL_MONEY: "fa-money-bill",
        PaymentMethod.WAVE: "fa-water",
        PaymentMethod.SENEGAL_WAVE: "fa-water",
        PaymentMethod.MOOV_MONEY: "fa-money-bill",
        PaymentMethod.ECOCASH: "fa-money-bill",
        PaymentMethod.CHIPPER_CASH: "fa-money-bill-wave",
        PaymentMethod.AFRICA_PAYDO: "fa-money-bill",
        PaymentMethod.FLW_BANK_TRANSFER: "fa-exchange-alt",
        PaymentMethod.USSD: "fa-phone",
        
        PaymentMethod.CASH_ON_DELIVERY: "fa-truck",
        PaymentMethod.STORE_CREDIT: "fa-store",
        PaymentMethod.VOUCHER: "fa-ticket-alt",
        PaymentMethod.OTHER: "fa-question-circle"
    }
    
    return icons.get(method, "fa-money-bill")
