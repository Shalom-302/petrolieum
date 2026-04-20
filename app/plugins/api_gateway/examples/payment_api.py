"""
Example of integrating the API Gateway with the Payment plugin.

Demonstrates how to securely expose payment functionality through the API Gateway
with proper authentication, rate limiting, and documentation.
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Body

from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.payment.providers.provider_factory import PaymentProviderFactory
from app.plugins.payment.models.payment import PaymentDB
from app.plugins.payment.models.refund import RefundDB
from app.plugins.api_gateway.main import plugin as api_gateway

# Setup logging
logger = logging.getLogger(__name__)

# Create a router for the payments API
payments_router = APIRouter()

# Define API response models
from pydantic import BaseModel, Field


class PaymentMethodInfo(BaseModel):
    """Information about a payment method."""
    id: str
    name: str
    description: str
    provider: str
    is_active: bool
    metadata: Dict[str, Any] = {}


class PaymentRequest(BaseModel):
    """Request model for creating a payment."""
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: str = Field(..., description="Currency code (e.g., USD, EUR)")
    provider: str = Field(..., description="Payment provider name")
    description: Optional[str] = Field(None, description="Payment description")
    metadata: Dict[str, Any] = Field(default={}, description="Additional payment metadata")
    return_url: Optional[str] = Field(None, description="URL to redirect after payment")
    webhook_url: Optional[str] = Field(None, description="URL for payment notifications")


class PaymentResponse(BaseModel):
    """Response model for payment information."""
    id: str
    amount: float
    currency: str
    provider: str
    status: str
    payment_url: Optional[str] = None
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = {}


class RefundRequest(BaseModel):
    """Request model for creating a refund."""
    payment_id: str = Field(..., description="ID of the payment to refund")
    amount: Optional[float] = Field(None, gt=0, description="Amount to refund (defaults to full amount)")
    reason: Optional[str] = Field(None, description="Reason for the refund")
    metadata: Dict[str, Any] = Field(default={}, description="Additional refund metadata")


class RefundResponse(BaseModel):
    """Response model for refund information."""
    id: str
    payment_id: str
    amount: float
    status: str
    created_at: str
    metadata: Dict[str, Any] = {}


# Define API endpoints

@payments_router.get("/methods", response_model=List[PaymentMethodInfo])
async def get_payment_methods(
    db: Session = Depends(get_db),
    api_key = Depends(api_gateway.require_api_key(permissions=["payments:methods:read"]))
):
    """
    Get available payment methods.
    
    Returns a list of all available payment methods from registered payment providers.
    """
    try:
        # Get available provider names
        provider_names = PaymentProviderFactory.get_provider_names()
        
        # Create response with payment method info
        payment_methods = []
        
        for provider_name in provider_names:
            # Create provider instance
            provider = PaymentProviderFactory.get_provider(provider_name, db)
            
            # Get methods from provider
            methods = provider.get_payment_methods()
            
            # Convert to response model
            for method in methods:
                payment_methods.append(
                    PaymentMethodInfo(
                        id=f"{provider_name}:{method['id']}",
                        name=method["name"],
                        description=method.get("description", ""),
                        provider=provider_name,
                        is_active=method.get("is_active", True),
                        metadata=method.get("metadata", {})
                    )
                )
        
        return payment_methods
    
    except Exception as e:
        logger.error(f"Error getting payment methods: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving payment methods")


@payments_router.post("/", response_model=PaymentResponse)
async def create_payment(
    payment_request: PaymentRequest,
    db: Session = Depends(get_db),
    api_key = Depends(api_gateway.require_api_key(permissions=["payments:transactions:write"]))
):
    """
    Create a new payment.
    
    Initiates a payment using the specified provider and returns payment details.
    """
    try:
        # Check if provider exists
        if payment_request.provider not in PaymentProviderFactory.get_provider_names():
            raise HTTPException(status_code=400, detail=f"Payment provider '{payment_request.provider}' not found")
        
        # Get provider instance
        provider = PaymentProviderFactory.get_provider(payment_request.provider, db)
        
        # Create payment
        payment_data = {
            "amount": payment_request.amount,
            "currency": payment_request.currency,
            "description": payment_request.description,
            "metadata": payment_request.metadata,
            "return_url": payment_request.return_url,
            "webhook_url": payment_request.webhook_url
        }
        
        payment = provider.create_payment(**payment_data)
        
        # Convert to response model
        response = PaymentResponse(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            provider=payment.provider,
            status=payment.status,
            payment_url=payment.payment_url,
            created_at=payment.created_at.isoformat(),
            updated_at=payment.updated_at.isoformat(),
            metadata=payment.metadata
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating payment")


@payments_router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str = Path(..., description="Payment ID"),
    db: Session = Depends(get_db),
    api_key = Depends(api_gateway.require_api_key(permissions=["payments:transactions:read"]))
):
    """
    Get payment details.
    
    Retrieves details for a specific payment by ID.
    """
    try:
        # Get payment from database
        payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Convert to response model
        response = PaymentResponse(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            provider=payment.provider,
            status=payment.status,
            payment_url=payment.payment_url,
            created_at=payment.created_at.isoformat(),
            updated_at=payment.updated_at.isoformat(),
            metadata=payment.metadata
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving payment")


@payments_router.post("/refund", response_model=RefundResponse)
async def create_refund(
    refund_request: RefundRequest,
    db: Session = Depends(get_db),
    api_key = Depends(api_gateway.require_api_key(permissions=["payments:refunds:write"]))
):
    """
    Create a refund.
    
    Initiates a refund for a specific payment.
    """
    try:
        # Get payment from database
        payment = db.query(PaymentDB).filter(PaymentDB.id == refund_request.payment_id).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Get provider instance
        provider = PaymentProviderFactory.get_provider(payment.provider, db)
        
        # Create refund
        refund_data = {
            "payment_id": payment.id,
            "amount": refund_request.amount or payment.amount,  # Default to full amount
            "reason": refund_request.reason,
            "metadata": refund_request.metadata
        }
        
        refund = provider.create_refund(**refund_data)
        
        # Convert to response model
        response = RefundResponse(
            id=refund.id,
            payment_id=refund.payment_id,
            amount=refund.amount,
            status=refund.status,
            created_at=refund.created_at.isoformat(),
            metadata=refund.metadata
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating refund: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating refund")


@payments_router.get("/refunds/{refund_id}", response_model=RefundResponse)
async def get_refund(
    refund_id: str = Path(..., description="Refund ID"),
    db: Session = Depends(get_db),
    api_key = Depends(api_gateway.require_api_key(permissions=["payments:refunds:read"]))
):
    """
    Get refund details.
    
    Retrieves details for a specific refund by ID.
    """
    try:
        # Get refund from database
        refund = db.query(RefundDB).filter(RefundDB.id == refund_id).first()
        
        if not refund:
            raise HTTPException(status_code=404, detail="Refund not found")
        
        # Convert to response model
        response = RefundResponse(
            id=refund.id,
            payment_id=refund.payment_id,
            amount=refund.amount,
            status=refund.status,
            created_at=refund.created_at.isoformat(),
            metadata=refund.metadata
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving refund: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving refund")


def register_payment_api():
    """
    Register the payments API with the API Gateway.
    
    This function should be called after both the API Gateway and Payment plugins are initialized.
    """
    api_gateway.register_api(
        router=payments_router,
        namespace="payments",
        version="v1",
        requires_api_key=True,
        permissions=[
            "payments:methods:read",
            "payments:transactions:read",
            "payments:transactions:write",
            "payments:refunds:read",
            "payments:refunds:write"
        ],
        tags=["Payments"]
    )
    
    logger.info("Payment API registered with API Gateway")


# Example usage in your application:
"""
from fastapi import FastAPI
from app.plugins.api_gateway.main import plugin as api_gateway
from app.plugins.payment.main import plugin as payment_plugin
from app.plugins.api_gateway.examples.payment_api import register_payment_api

app = FastAPI()

# Initialize plugins
payment_plugin.initialize(app)
api_gateway.initialize(app)

# Register payment API
register_payment_api()
"""
