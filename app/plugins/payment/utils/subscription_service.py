"""
Subscription service for the payment plugin.

This module provides functionality for managing subscriptions, including creating,
updating, canceling, and retrieving subscriptions.
"""
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.plugins.advanced_auth.models import User
from ..models.payment import PaymentDB, PaymentCreate, PaymentStatus, Currency
from ..models.subscription import (
    SubscriptionDB, SubscriptionItemDB, SubscriptionHistoryDB,
    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    SubscriptionStatus, SubscriptionCancelRequest, SubscriptionPauseRequest,
    BillingPeriod
)
from ..providers.provider_factory import PaymentProviderFactory
from .payment_service import create_payment_service

logger = logging.getLogger("kaapi.payment.subscription")

async def create_subscription_service(
    db: Session,
    subscription: SubscriptionCreate,
    current_user: Optional[User] = None
) -> SubscriptionDB:
    """
    Create a new subscription.
    
    Args:
        db: Database session
        subscription: Subscription data
        current_user: Current user creating the subscription
        
    Returns:
        Created subscription record
    """
    # Validate subscription data
    provider_name = subscription.payment_provider
    if not provider_name:
        # Select default provider or use first available
        providers = PaymentProviderFactory.list_providers()
        provider_name = providers[0] if providers else None
        if not provider_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No payment provider available"
            )
    
    # Check if provider supports subscriptions
    provider = PaymentProviderFactory.get_provider(provider_name)
    if not provider.supports_subscriptions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {provider_name} does not support subscriptions"
        )
    
    # Create subscription record
    db_subscription = SubscriptionDB(
        name=subscription.name,
        description=subscription.description,
        status=SubscriptionStatus.DRAFT.value,
        amount=subscription.amount,
        currency=subscription.currency,
        billing_period=subscription.billing_period.value,
        billing_interval=subscription.billing_interval,
        customer_id=subscription.customer_id,
        customer_email=subscription.customer_email,
        created_by_id=current_user.id if current_user else None,
        start_date=subscription.start_date or datetime.utcnow(),
        end_date=subscription.end_date,
        trial_enabled=subscription.trial_enabled,
        trial_start_date=subscription.trial_start_date,
        trial_end_date=subscription.trial_end_date,
        payment_method_id=subscription.payment_method_id,
        payment_provider=provider_name,
        auto_renew=subscription.auto_renew,
        subscription_metadata=subscription.subscription_metadata
    )
    
    # Calculate next billing date
    if db_subscription.start_date:
        db_subscription.next_billing_date = _calculate_next_billing_date(
            db_subscription.start_date,
            db_subscription.billing_period,
            db_subscription.billing_interval
        )
    
    db.add(db_subscription)
    db.flush()  # To get the subscription ID
    
    # Add subscription items if provided
    if subscription.items:
        for item in subscription.items:
            db_item = SubscriptionItemDB(
                subscription_id=db_subscription.id,
                name=item.name,
                description=item.description,
                price=item.price,
                currency=item.currency,
                quantity=item.quantity,
                product_id=item.product_id,
                item_metadata=item.item_metadata
            )
            db.add(db_item)
    
    # Add subscription history record
    history = SubscriptionHistoryDB(
        subscription_id=db_subscription.id,
        action="created",
        status_before=None,
        status_after=db_subscription.status,
        user_id=current_user.id if current_user else None
    )
    db.add(history)
    
    db.commit()
    db.refresh(db_subscription)
    
    logger.info(f"Subscription created: {db_subscription.id}")
    return db_subscription

async def activate_subscription_service(
    db: Session,
    subscription_id: int,
    current_user: Optional[User] = None
) -> SubscriptionDB:
    """
    Activate a subscription with the payment provider.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to activate
        current_user: Current user activating the subscription
        
    Returns:
        Updated subscription record
    """
    db_subscription = await get_subscription_service(db, subscription_id)
    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    if db_subscription.status != SubscriptionStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subscription is already in {db_subscription.status} status"
        )
    
    # Get the provider
    provider = PaymentProviderFactory.get_provider(db_subscription.payment_provider)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {db_subscription.payment_provider} not available"
        )
    
    # Create subscription with provider
    subscription_data = SubscriptionCreate(
        name=db_subscription.name,
        description=db_subscription.description,
        amount=db_subscription.amount,
        currency=db_subscription.currency,
        billing_period=db_subscription.billing_period,
        billing_interval=db_subscription.billing_interval,
        payment_method_id=db_subscription.payment_method_id,
        payment_provider=db_subscription.payment_provider,
        customer_id=db_subscription.customer_id,
        customer_email=db_subscription.customer_email,
        start_date=db_subscription.start_date,
        end_date=db_subscription.end_date,
        trial_enabled=db_subscription.trial_enabled,
        trial_start_date=db_subscription.trial_start_date,
        trial_end_date=db_subscription.trial_end_date,
        auto_renew=db_subscription.auto_renew,
        subscription_metadata=db_subscription.subscription_metadata
    )
    
    try:
        provider_response = await provider.create_subscription(subscription_data)
        
        # Update subscription with provider data
        old_status = db_subscription.status
        db_subscription.status = provider_response.status
        db_subscription.provider_subscription_id = provider_response.provider_subscription_id
        db_subscription.updated_at = datetime.utcnow()
        
        # Update other fields if provided in response
        if provider_response.next_billing_date:
            db_subscription.next_billing_date = provider_response.next_billing_date
        
        # Add history record
        history = SubscriptionHistoryDB(
            subscription_id=db_subscription.id,
            action="activated",
            status_before=old_status,
            status_after=db_subscription.status,
            user_id=current_user.id if current_user else None,
            data={"provider_subscription_id": provider_response.provider_subscription_id}
        )
        db.add(history)
        
        db.commit()
        db.refresh(db_subscription)
        
        logger.info(f"Subscription activated: {db_subscription.id}")
        return db_subscription
        
    except Exception as e:
        logger.error(f"Error activating subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate subscription: {str(e)}"
        )

async def get_subscription_service(
    db: Session,
    subscription_id: int
) -> Optional[SubscriptionDB]:
    """
    Get a subscription by ID.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to retrieve
        
    Returns:
        Subscription record or None if not found
    """
    return db.query(SubscriptionDB).filter(SubscriptionDB.id == subscription_id).first()

async def list_subscriptions_service(
    db: Session,
    customer_id: Optional[int] = None,
    status: Optional[Union[SubscriptionStatus, str]] = None,
    skip: int = 0,
    limit: int = 100
) -> List[SubscriptionDB]:
    """
    List subscriptions with optional filtering.
    
    Args:
        db: Database session
        customer_id: Filter by customer ID
        status: Filter by subscription status
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of subscription records
    """
    query = db.query(SubscriptionDB)
    
    if customer_id:
        query = query.filter(SubscriptionDB.customer_id == customer_id)
    
    if status:
        if isinstance(status, SubscriptionStatus):
            status_value = status.value
        else:
            status_value = status
        query = query.filter(SubscriptionDB.status == status_value)
    
    return query.offset(skip).limit(limit).all()

def _calculate_next_billing_date(
    start_date: datetime,
    billing_period: str,
    billing_interval: int
) -> datetime:
    """
    Calculate the next billing date based on start date and billing period.
    
    Args:
        start_date: Subscription start date
        billing_period: Billing period (daily, weekly, monthly, etc.)
        billing_interval: Billing interval (e.g., 1 for monthly, 2 for bi-monthly)
        
    Returns:
        Next billing date
    """
    if billing_period == "daily":
        return start_date + timedelta(days=billing_interval)
    elif billing_period == "weekly":
        return start_date + timedelta(weeks=billing_interval)
    elif billing_period == "monthly":
        # Add months (approximate)
        months_to_add = billing_interval
        new_month = start_date.month + months_to_add
        new_year = start_date.year + (new_month - 1) // 12
        new_month = ((new_month - 1) % 12) + 1
        
        # Handle cases where the resulting day might not exist in the target month
        try:
            return start_date.replace(year=new_year, month=new_month)
        except ValueError:
            # Day doesn't exist in target month, use last day of the month
            if new_month == 12:
                last_day = 31
            else:
                last_day = (datetime(new_year, new_month + 1, 1) - timedelta(days=1)).day
            return datetime(new_year, new_month, last_day)
    
    elif billing_period == "quarterly":
        # Add 3 months * interval
        return _calculate_next_billing_date(start_date, "monthly", 3 * billing_interval)
    
    elif billing_period == "biannual":
        # Add 6 months * interval
        return _calculate_next_billing_date(start_date, "monthly", 6 * billing_interval)
    
    elif billing_period == "annual":
        # Add years
        return start_date.replace(year=start_date.year + billing_interval)
    
    # Default to monthly
    return _calculate_next_billing_date(start_date, "monthly", billing_interval)

async def update_subscription_service(
    db: Session,
    subscription_id: int,
    update_data: SubscriptionUpdate,
    current_user: Optional[User] = None
) -> SubscriptionDB:
    """
    Update a subscription.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to update
        update_data: Data to update
        current_user: Current user updating the subscription
        
    Returns:
        Updated subscription record
    """
    db_subscription = await get_subscription_service(db, subscription_id)
    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Store old status for history
    old_status = db_subscription.status
    
    # Update subscription fields if provided
    if update_data.name is not None:
        db_subscription.name = update_data.name
    
    if update_data.description is not None:
        db_subscription.description = update_data.description
    
    if update_data.status is not None:
        db_subscription.status = update_data.status.value
    
    if update_data.amount is not None:
        db_subscription.amount = update_data.amount
    
    if update_data.currency is not None:
        db_subscription.currency = update_data.currency
    
    if update_data.billing_period is not None:
        db_subscription.billing_period = update_data.billing_period.value
    
    if update_data.billing_interval is not None:
        db_subscription.billing_interval = update_data.billing_interval
    
    if update_data.payment_method_id is not None:
        db_subscription.payment_method_id = update_data.payment_method_id
    
    if update_data.customer_id is not None:
        db_subscription.customer_id = update_data.customer_id
    
    if update_data.customer_email is not None:
        db_subscription.customer_email = update_data.customer_email
    
    if update_data.start_date is not None:
        db_subscription.start_date = update_data.start_date
    
    if update_data.end_date is not None:
        db_subscription.end_date = update_data.end_date
    
    if update_data.next_billing_date is not None:
        db_subscription.next_billing_date = update_data.next_billing_date
    
    if update_data.trial_enabled is not None:
        db_subscription.trial_enabled = update_data.trial_enabled
    
    if update_data.trial_start_date is not None:
        db_subscription.trial_start_date = update_data.trial_start_date
    
    if update_data.trial_end_date is not None:
        db_subscription.trial_end_date = update_data.trial_end_date
    
    if update_data.auto_renew is not None:
        db_subscription.auto_renew = update_data.auto_renew
    
    if update_data.subscription_metadata is not None:
        # Merge metadata rather than replace
        if db_subscription.subscription_metadata:
            db_subscription.subscription_metadata.update(update_data.subscription_metadata)
        else:
            db_subscription.subscription_metadata = update_data.subscription_metadata
    
    # Update with provider if necessary (if subscription is already active with provider)
    provider_updated = False
    if db_subscription.provider_subscription_id and db_subscription.status != SubscriptionStatus.DRAFT.value:
        try:
            provider = PaymentProviderFactory.get_provider(db_subscription.payment_provider)
            await provider.update_subscription(
                db_subscription.provider_subscription_id,
                update_data
            )
            provider_updated = True
        except Exception as e:
            logger.error(f"Error updating subscription with provider: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update subscription with provider: {str(e)}"
            )
    
    # Recalculate next billing date if necessary
    if (update_data.start_date is not None or 
        update_data.billing_period is not None or 
        update_data.billing_interval is not None):
        db_subscription.next_billing_date = _calculate_next_billing_date(
            db_subscription.start_date or datetime.utcnow(),
            db_subscription.billing_period,
            db_subscription.billing_interval
        )
    
    # Record update time
    db_subscription.updated_at = datetime.utcnow()
    
    # Add history record
    history = SubscriptionHistoryDB(
        subscription_id=db_subscription.id,
        action="updated",
        status_before=old_status,
        status_after=db_subscription.status,
        user_id=current_user.id if current_user else None,
        data={"provider_updated": provider_updated}
    )
    db.add(history)
    
    db.commit()
    db.refresh(db_subscription)
    logger.info(f"Subscription updated: {db_subscription.id}")
    return db_subscription

async def cancel_subscription_service(
    db: Session,
    subscription_id: int,
    cancel_request: SubscriptionCancelRequest,
    current_user: Optional[User] = None
) -> SubscriptionDB:
    """
    Cancel a subscription.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to cancel
        cancel_request: Cancellation details
        current_user: Current user canceling the subscription
        
    Returns:
        Updated subscription record
    """
    db_subscription = await get_subscription_service(db, subscription_id)
    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Can't cancel if already canceled
    if db_subscription.status == SubscriptionStatus.CANCELED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is already canceled"
        )
    
    old_status = db_subscription.status
    
    # Cancel with provider if applicable
    if db_subscription.provider_subscription_id:
        try:
            provider = PaymentProviderFactory.get_provider(db_subscription.payment_provider)
            await provider.cancel_subscription(
                db_subscription.provider_subscription_id,
                cancel_request
            )
        except Exception as e:
            logger.error(f"Error canceling subscription with provider: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel subscription with provider: {str(e)}"
            )
    
    # Update subscription in database
    db_subscription.status = SubscriptionStatus.CANCELED.value
    
    # If cancel at period end, set end date to next billing date
    if cancel_request.cancel_at_period_end and db_subscription.next_billing_date:
        db_subscription.end_date = db_subscription.next_billing_date
    else:
        db_subscription.end_date = datetime.utcnow()
    
    db_subscription.updated_at = datetime.utcnow()
    
    # Store cancellation details in metadata
    if not db_subscription.subscription_metadata:
        db_subscription.subscription_metadata = {}
    
    db_subscription.subscription_metadata = {
        **db_subscription.subscription_metadata,
        "cancellation": {
            "reason": cancel_request.reason,
            "requested_at": datetime.utcnow().isoformat(),
            "requested_by": current_user.id if current_user else None,
            "cancel_at_period_end": cancel_request.cancel_at_period_end
        }
    }
    
    # Add history record
    history = SubscriptionHistoryDB(
        subscription_id=db_subscription.id,
        action="canceled",
        status_before=old_status,
        status_after=db_subscription.status,
        user_id=current_user.id if current_user else None,
        data={
            "reason": cancel_request.reason,
            "cancel_at_period_end": cancel_request.cancel_at_period_end
        }
    )
    db.add(history)
    
    db.commit()
    db.refresh(db_subscription)
    logger.info(f"Subscription canceled: {db_subscription.id}")
    return db_subscription

async def pause_subscription_service(
    db: Session,
    subscription_id: int,
    pause_request: SubscriptionPauseRequest,
    current_user: Optional[User] = None
) -> SubscriptionDB:
    """
    Pause a subscription.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to pause
        pause_request: Pause details
        current_user: Current user pausing the subscription
        
    Returns:
        Updated subscription record
    """
    db_subscription = await get_subscription_service(db, subscription_id)
    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Can only pause active subscriptions
    if db_subscription.status not in [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot pause subscription in {db_subscription.status} status"
        )
    
    old_status = db_subscription.status
    
    # Pause with provider if applicable
    if db_subscription.provider_subscription_id:
        try:
            provider = PaymentProviderFactory.get_provider(db_subscription.payment_provider)
            await provider.pause_subscription(db_subscription.provider_subscription_id)
        except Exception as e:
            logger.error(f"Error pausing subscription with provider: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to pause subscription with provider: {str(e)}"
            )
    
    # Update subscription in database
    db_subscription.status = SubscriptionStatus.PAUSED.value
    db_subscription.updated_at = datetime.utcnow()
    
    # Store pause details in metadata
    if not db_subscription.subscription_metadata:
        db_subscription.subscription_metadata = {}
    
    db_subscription.subscription_metadata = {
        **db_subscription.subscription_metadata,
        "pause": {
            "reason": pause_request.reason,
            "paused_at": datetime.utcnow().isoformat(),
            "paused_by": current_user.id if current_user else None,
            "resume_at": pause_request.resume_at.isoformat() if pause_request.resume_at else None
        }
    }
    
    # Add history record
    history = SubscriptionHistoryDB(
        subscription_id=db_subscription.id,
        action="paused",
        status_before=old_status,
        status_after=db_subscription.status,
        user_id=current_user.id if current_user else None,
        data={
            "reason": pause_request.reason,
            "resume_at": pause_request.resume_at.isoformat() if pause_request.resume_at else None
        }
    )
    db.add(history)
    
    db.commit()
    db.refresh(db_subscription)
    logger.info(f"Subscription paused: {db_subscription.id}")
    return db_subscription

async def resume_subscription_service(
    db: Session,
    subscription_id: int,
    current_user: Optional[User] = None
) -> SubscriptionDB:
    """
    Resume a paused subscription.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to resume
        current_user: Current user resuming the subscription
        
    Returns:
        Updated subscription record
    """
    db_subscription = await get_subscription_service(db, subscription_id)
    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Can only resume paused subscriptions
    if db_subscription.status != SubscriptionStatus.PAUSED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume subscription in {db_subscription.status} status"
        )
    
    old_status = db_subscription.status
    
    # Resume with provider if applicable
    if db_subscription.provider_subscription_id:
        try:
            provider = PaymentProviderFactory.get_provider(db_subscription.payment_provider)
            await provider.resume_subscription(db_subscription.provider_subscription_id)
        except Exception as e:
            logger.error(f"Error resuming subscription with provider: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to resume subscription with provider: {str(e)}"
            )
    
    # Update subscription in database
    db_subscription.status = SubscriptionStatus.ACTIVE.value
    db_subscription.updated_at = datetime.utcnow()
    
    # Store resume details in metadata
    if not db_subscription.subscription_metadata:
        db_subscription.subscription_metadata = {}
    
    db_subscription.subscription_metadata = {
        **db_subscription.subscription_metadata,
        "resume": {
            "resumed_at": datetime.utcnow().isoformat(),
            "resumed_by": current_user.id if current_user else None
        }
    }
    
    # Add history record
    history = SubscriptionHistoryDB(
        subscription_id=db_subscription.id,
        action="resumed",
        status_before=old_status,
        status_after=db_subscription.status,
        user_id=current_user.id if current_user else None
    )
    db.add(history)
    
    db.commit()
    db.refresh(db_subscription)
    logger.info(f"Subscription resumed: {db_subscription.id}")
    return db_subscription

async def verify_subscription_service(
    db: Session,
    subscription_id: int,
    current_user: Optional[User] = None
) -> SubscriptionDB:
    """
    Verify subscription status with the provider and update the local record.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to verify
        current_user: Current user verifying the subscription
        
    Returns:
        Updated subscription record
    """
    db_subscription = await get_subscription_service(db, subscription_id)
    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # If no provider subscription ID, nothing to verify
    if not db_subscription.provider_subscription_id:
        return db_subscription
    
    # Get status from provider
    try:
        provider = PaymentProviderFactory.get_provider(db_subscription.payment_provider)
        provider_data = await provider.get_subscription(db_subscription.provider_subscription_id)
        
        old_status = db_subscription.status
        
        # Update subscription with data from provider
        if "status" in provider_data:
            db_subscription.status = provider_data["status"]
        
        if "next_billing_date" in provider_data:
            db_subscription.next_billing_date = provider_data["next_billing_date"]
        
        db_subscription.updated_at = datetime.utcnow()
        
        # Add history record if status changed
        if old_status != db_subscription.status:
            history = SubscriptionHistoryDB(
                subscription_id=db_subscription.id,
                action="verified",
                status_before=old_status,
                status_after=db_subscription.status,
                user_id=current_user.id if current_user else None,
                data={"provider_data": provider_data}
            )
            db.add(history)
        
        db.commit()
        db.refresh(db_subscription)
        logger.info(f"Subscription verified: {db_subscription.id}")
        return db_subscription
    
    except Exception as e:
        logger.error(f"Error verifying subscription with provider: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify subscription with provider: {str(e)}"
        )

async def create_invoice_for_subscription(
    db: Session,
    subscription_id: int,
    current_user: Optional[User] = None
) -> PaymentDB:
    """
    Create a new invoice/payment for a subscription.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to invoice
        current_user: Current user creating the invoice
        
    Returns:
        Created payment record
    """
    db_subscription = await get_subscription_service(db, subscription_id)
    if not db_subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Can only invoice active subscriptions
    if db_subscription.status not in [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot create invoice for subscription in {db_subscription.status} status"
        )
    
    # Create payment record
    payment_data = PaymentCreate(
        amount=db_subscription.amount,
        currency=Currency(db_subscription.currency),
        description=f"Invoice for subscription {db_subscription.name} - {datetime.utcnow().strftime('%Y-%m-%d')}",
        payment_method="subscription",
        provider=db_subscription.payment_provider,
        customer_id=db_subscription.customer_id,
        payment_metadata={
            "subscription_id": db_subscription.id,
            "billing_period": db_subscription.billing_period,
            "invoice_date": datetime.utcnow().isoformat()
        }
    )
    
    # Create the payment
    payment = await create_payment_service(db, payment_data, current_user)
    
    # Update subscription with payment
    db_subscription.updated_at = datetime.utcnow()
    
    # Add history record
    history = SubscriptionHistoryDB(
        subscription_id=db_subscription.id,
        action="invoice_created",
        status_before=db_subscription.status,
        status_after=db_subscription.status,
        user_id=current_user.id if current_user else None,
        data={"payment_id": payment.id}
    )
    db.add(history)
    
    db.commit()
    logger.info(f"Invoice created for subscription: {db_subscription.id}, payment: {payment.id}")
    return payment
