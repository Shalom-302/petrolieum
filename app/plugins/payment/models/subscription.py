"""
Subscription models for the payment plugin.

This module defines the database and API models for handling subscriptions.
"""
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from pydantic import BaseModel, Field, validator

from app.core.db import Base
from app.plugins.advanced_auth.models import User

class SubscriptionStatus(str, Enum):
    """Subscription status enum."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    PAUSED = "paused"
    ENDED = "ended"

class BillingPeriod(str, Enum):
    """Billing period enum."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    BIANNUAL = "biannual"
    ANNUAL = "annual"
    CUSTOM = "custom"

class SubscriptionDB(Base):
    """Subscription database model."""
    __tablename__ = "payment_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic subscription details
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default=SubscriptionStatus.DRAFT.value)
    
    # Customer information
    customer_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    customer = relationship("User", foreign_keys=[customer_id], backref="subscriptions", primaryjoin="SubscriptionDB.customer_id == User.id")
    customer_email = Column(String, nullable=True)
    
    # Created by information
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_by = relationship("User", foreign_keys=[created_by_id], primaryjoin="SubscriptionDB.created_by_id == User.id")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    next_billing_date = Column(DateTime, nullable=True)
    
    # Billing details
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    billing_period = Column(String, nullable=False, default=BillingPeriod.MONTHLY.value)
    billing_interval = Column(Integer, nullable=False, default=1)  # e.g. 1 for monthly, 2 for bi-monthly
    
    # Trial details
    trial_enabled = Column(Boolean, default=False)
    trial_start_date = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    
    # Payment details
    payment_method_id = Column(String, nullable=True)
    payment_provider = Column(String, nullable=True)
    provider_subscription_id = Column(String, nullable=True)
    auto_renew = Column(Boolean, default=True)
    
    # Metadata
    subscription_metadata = Column(JSON, nullable=True)
    
    # Payments related to this subscription
    payments = relationship("PaymentDB", backref="subscription", 
                           primaryjoin="SubscriptionDB.id == PaymentDB.subscription_id")
    
    # Additional subscription data
    items = relationship("SubscriptionItemDB", backref="subscription", cascade="all, delete-orphan")
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in [
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIALING.value
        ]
    
    @property
    def is_past_due(self) -> bool:
        """Check if subscription is past due."""
        return self.status == SubscriptionStatus.PAST_DUE.value
    
    @property
    def is_canceled(self) -> bool:
        """Check if subscription is canceled."""
        return self.status == SubscriptionStatus.CANCELED.value
    
    @property
    def is_in_trial(self) -> bool:
        """Check if subscription is in trial period."""
        if not self.trial_enabled:
            return False
        now = datetime.utcnow()
        return (self.trial_start_date is not None and 
                self.trial_end_date is not None and
                self.trial_start_date <= now <= self.trial_end_date)
    
    @property
    def days_until_next_billing(self) -> Optional[int]:
        """Get number of days until next billing."""
        if not self.next_billing_date:
            return None
        now = datetime.utcnow()
        delta = self.next_billing_date - now
        return max(0, delta.days)

class SubscriptionItemDB(Base):
    """Subscription item database model."""
    __tablename__ = "payment_subscription_items"
    
    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("payment_subscriptions.id"), nullable=False)
    
    # Item details
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    
    # Product information
    product_id = Column(String, nullable=True)
    provider_item_id = Column(String, nullable=True)
    
    # Metadata
    item_metadata = Column(JSON, nullable=True)
    
    @property
    def total_price(self) -> float:
        """Calculate total price for this item."""
        return self.price * self.quantity

class SubscriptionHistoryDB(Base):
    """Subscription history database model."""
    __tablename__ = "payment_subscription_history"
    
    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("payment_subscriptions.id"), nullable=False)
    
    # Action details
    action = Column(String, nullable=False)  # created, activated, canceled, etc.
    status_before = Column(String, nullable=True)
    status_after = Column(String, nullable=True)
    
    # User information
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    user = relationship("User", foreign_keys=[user_id], primaryjoin="SubscriptionHistoryDB.user_id == User.id")
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Additional data
    data = Column(JSON, nullable=True)

# Pydantic models for API
class SubscriptionItemCreate(BaseModel):
    """Subscription item create model."""
    name: str
    description: Optional[str] = None
    price: float
    currency: str
    quantity: int = 1
    product_id: Optional[str] = None
    item_metadata: Optional[Dict[str, Any]] = None

class SubscriptionCreate(BaseModel):
    """Subscription create model."""
    name: str
    description: Optional[str] = None
    amount: float
    currency: str
    billing_period: BillingPeriod = BillingPeriod.MONTHLY
    billing_interval: int = 1
    payment_method_id: Optional[str] = None
    payment_provider: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    trial_enabled: bool = False
    trial_start_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    auto_renew: bool = True
    subscription_metadata: Optional[Dict[str, Any]] = None
    items: Optional[List[SubscriptionItemCreate]] = None
    
    @validator('customer_id', 'customer_email')
    def validate_customer_info(cls, v, values, **kwargs):
        """Validate that either customer_id or customer_email is provided."""
        field = kwargs['field'].name
        
        if field == 'customer_email' and not v:
            # If customer_email is not provided, customer_id must be
            if not values.get('customer_id'):
                raise ValueError('Either customer_id or customer_email must be provided')
        
        return v
    
    @validator('trial_end_date')
    def validate_trial_dates(cls, v, values, **kwargs):
        """Validate trial dates."""
        if values.get('trial_enabled') and values.get('trial_start_date') and v:
            if values['trial_start_date'] >= v:
                raise ValueError('Trial end date must be after trial start date')
        return v

class SubscriptionUpdate(BaseModel):
    """Subscription update model."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[SubscriptionStatus] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    billing_period: Optional[BillingPeriod] = None
    billing_interval: Optional[int] = None
    payment_method_id: Optional[str] = None
    payment_provider: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    trial_enabled: Optional[bool] = None
    trial_start_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    auto_renew: Optional[bool] = None
    subscription_metadata: Optional[Dict[str, Any]] = None

class SubscriptionItemResponse(BaseModel):
    """Subscription item response model."""
    id: int
    subscription_id: int
    name: str
    description: Optional[str] = None
    price: float
    currency: str
    quantity: int
    product_id: Optional[str] = None
    provider_item_id: Optional[str] = None
    item_metadata: Optional[Dict[str, Any]] = None
    total_price: float
    
    class Config:
        from_attributes = True

class SubscriptionResponse(BaseModel):
    """Subscription response model."""
    id: int
    name: str
    description: Optional[str] = None
    status: str
    amount: float
    currency: str
    billing_period: str
    billing_interval: int
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    trial_enabled: bool
    trial_start_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    payment_method_id: Optional[str] = None
    payment_provider: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    auto_renew: bool
    subscription_metadata: Optional[Dict[str, Any]] = None
    items: List[SubscriptionItemResponse] = []
    is_active: bool
    is_past_due: bool
    is_canceled: bool
    is_in_trial: bool
    days_until_next_billing: Optional[int] = None
    
    class Config:
        from_attributes = True

class SubscriptionCancelRequest(BaseModel):
    """Subscription cancellation request model."""
    reason: Optional[str] = None
    cancel_at_period_end: bool = True
    prorate: bool = False
    
class SubscriptionPauseRequest(BaseModel):
    """Subscription pause request model."""
    resume_at: Optional[datetime] = None
    reason: Optional[str] = None

class SubscriptionRequest(BaseModel):
    """Subscription request model for payment providers.
    
    This model is used when sending subscription requests to payment providers.
    """
    subscription_id: str
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    amount: float
    currency: str
    billing_period: str
    billing_interval: int = 1
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    trial_enabled: bool = False
    trial_end_date: Optional[datetime] = None
    subscription_metadata: Optional[Dict[str, Any]] = None
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None
    webhook_url: Optional[str] = None
    
    @property
    def customer(self) -> Dict[str, Any]:
        """Get customer information as a dictionary."""
        return {
            "email": self.customer_email,
            "name": self.customer_name,
            "phone": self.customer_phone
        }
