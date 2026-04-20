"""
Provider models for payment plugin.

This module contains models related to payment providers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .payment import PaymentMethod, Currency, PaymentStatus, RefundStatus

class ProviderResponse(BaseModel):
    """Schema for payment provider response."""
    id: str = Field(..., description="Provider identifier")
    name: str = Field(..., description="Provider name")
    description: str = Field(..., description="Provider description")
    logo_url: Optional[str] = Field(None, description="Provider logo URL")
    supported_methods: List[PaymentMethod] = Field(..., description="Payment methods supported by this provider")
    supported_currencies: List[Currency] = Field(..., description="Currencies supported by this provider")
    countries: List[str] = Field(..., description="Countries where this provider is available")
    is_enabled: bool = Field(..., description="Whether this provider is enabled")
    is_test_mode: bool = Field(..., description="Whether this provider is in test mode")
    provider_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class PaymentProviderConfig(BaseModel):
    """Configuration for a payment provider."""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    merchant_id: Optional[str] = None
    webhook_secret: Optional[str] = None
    environment: str = "production"  # test or production
    timeout: int = 30  # seconds
    extra_config: Optional[Dict[str, Any]] = None

class PaymentRequest(BaseModel):
    """Request to process a payment."""
    amount: float
    currency: Currency
    payment_method: PaymentMethod
    customer: Dict[str, Any]
    request_metadata: Optional[Dict[str, Any]] = None
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None
    webhook_url: Optional[str] = None
    description: Optional[str] = None

class RefundRequest(BaseModel):
    """Refund request to provider."""
    amount: float
    currency: Currency
    payment_reference: str
    reason: Optional[str] = None
    refund_metadata: Dict[str, Any] = {}
    
    @property
    def is_partial(self) -> bool:
        """Check if this is a partial refund."""
        # This is a simplistic check that assumes the original payment
        # information would be looked up by the provider. For a real implementation,
        # we might want to include the original payment amount here.
        return self.refund_metadata.get("is_partial", True)

class PaymentResult(BaseModel):
    """Result of a payment processing operation."""
    success: bool
    provider_reference: Optional[str] = None
    status: PaymentStatus
    message: Optional[str] = None
    payment_url: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

class ProviderInfo(BaseModel):
    """Provider information."""
    id: str
    name: str
    description: str
    logo_url: Optional[str] = None
    is_enabled: bool = True
    supports_refunds: bool = True
    supports_partial_refunds: bool = True
    supported_methods: List[PaymentMethod] = []
    supported_currencies: List[Currency] = []
    supported_countries: List[str] = []
