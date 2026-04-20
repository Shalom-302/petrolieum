"""
Test suite for payment providers.

This module provides functionality to test payment providers without making actual payments.
"""
import logging
import json
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.advanced_auth.models import User
from ..models.payment import (
    PaymentDB, 
    PaymentCreate, 
    PaymentStatus,
    PaymentApprovalStepDB,
    PaymentTransactionDB
)
from ..models.provider import PaymentRequest, ProviderResponse, PaymentProviderConfig
from ..providers.base_provider import BasePaymentProvider
from ..providers.provider_factory import PaymentProviderFactory
from ..utils.config import payment_settings
from app.core.security import get_current_active_user

logger = logging.getLogger("kaapi.payment.test")

class MockPaymentProvider(BasePaymentProvider):
    """
    Mock payment provider for testing purposes.
    
    This provider simulates successful and failed payments based on configuration.
    """
    
    provider_name = "mock_provider"
    
    def __init__(self, config: PaymentProviderConfig):
        """Initialize the mock provider."""
        super().__init__(config)
        
        # Mock provider specific settings
        self.fail_probability = config.extra_config.get("fail_probability", 0.0)
        self.delay_seconds = config.extra_config.get("delay_seconds", 1.0)
        self.webhook_delay_seconds = config.extra_config.get("webhook_delay_seconds", 2.0)
        self.auto_webhook = config.extra_config.get("auto_webhook", True)
        
        # Payment details to store for testing
        self.test_payments: Dict[str, Dict[str, Any]] = {}
    
    @property
    def id(self) -> str:
        """Get the provider ID."""
        return "mock_provider"
    
    @property
    def name(self) -> str:
        """Get the provider name."""
        return "Mock Payment Provider"
    
    @property
    def description(self) -> str:
        """Get the provider description."""
        return "A mock payment provider for testing purposes"
    
    @property
    def is_enabled(self) -> bool:
        """Check if the provider is enabled."""
        return True
    
    @property
    def supported_methods(self) -> List[str]:
        """Get the supported payment methods."""
        return ["credit_card", "bank_transfer", "mobile_money", "cryptocurrency", "other"]
    
    @property
    def supported_currencies(self) -> List[str]:
        """Get the supported currencies."""
        return ["USD", "EUR", "GBP", "KES", "NGN", "ZAR", "GHS", "UGX", "TZS"]
    
    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """Process a payment through the mock provider."""
        # Simulate processing delay
        await asyncio.sleep(self.delay_seconds)
        
        # Generate a reference
        reference = f"mock-{uuid.uuid4()}"
        payment_id = payment_request.metadata.get("payment_id")
        
        # Store payment for later
        self.test_payments[reference] = {
            "request": payment_request.dict(),
            "timestamp": datetime.utcnow().isoformat(),
            "reference": reference,
            "payment_id": payment_id
        }
        
        # Determine if payment should fail
        import random
        should_fail = random.random() < self.fail_probability
        
        if should_fail:
            response = ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference=reference,
                message="Payment failed (mock provider)",
                raw_response={
                    "error": "payment_failed",
                    "error_description": "This is a simulated payment failure",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        else:
            response = ProviderResponse(
                success=True,
                status=PaymentStatus.PROCESSING,
                provider_reference=reference,
                message="Payment initiated (mock provider)",
                payment_url=f"http://localhost:8000/apipayments/test/mock/{reference}",
                raw_response={
                    "status": "processing",
                    "reference": reference,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            
            # Schedule automatic webhook if enabled
            if self.auto_webhook and payment_id:
                asyncio.create_task(self._send_webhook(payment_id, reference))
        
        return response
    
    async def verify_payment(self, reference: str) -> ProviderResponse:
        """Verify a payment with the provider."""
        await asyncio.sleep(0.5)
        
        # Check if payment exists
        if reference not in self.test_payments:
            return ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference=reference,
                message="Payment not found",
                raw_response={
                    "error": "payment_not_found",
                    "error_description": "No payment found with this reference",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        
        # Get payment
        payment = self.test_payments[reference]
        
        # Check payment status
        if payment.get("status") == "completed":
            return ProviderResponse(
                success=True,
                status=PaymentStatus.COMPLETED,
                provider_reference=reference,
                message="Payment completed",
                raw_response={
                    "status": "completed",
                    "reference": reference,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        elif payment.get("status") == "failed":
            return ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference=reference,
                message="Payment failed",
                raw_response={
                    "status": "failed",
                    "reference": reference,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        else:
            return ProviderResponse(
                success=True,
                status=PaymentStatus.PROCESSING,
                provider_reference=reference,
                message="Payment is still processing",
                raw_response={
                    "status": "processing",
                    "reference": reference,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
    
    async def cancel_payment(self, reference: str) -> ProviderResponse:
        """Cancel a payment with the provider."""
        await asyncio.sleep(0.5)
        
        # Check if payment exists
        if reference not in self.test_payments:
            return ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference=reference,
                message="Payment not found",
                raw_response={
                    "error": "payment_not_found",
                    "error_description": "No payment found with this reference",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        
        # Get payment
        payment = self.test_payments[reference]
        
        # Check if payment can be cancelled
        if payment.get("status") in ["completed", "cancelled", "refunded"]:
            return ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference=reference,
                message=f"Payment cannot be cancelled in status {payment.get('status')}",
                raw_response={
                    "error": "invalid_status",
                    "error_description": f"Payment cannot be cancelled in status {payment.get('status')}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        
        # Update payment status
        payment["status"] = "cancelled"
        
        return ProviderResponse(
            success=True,
            status=PaymentStatus.CANCELLED,
            provider_reference=reference,
            message="Payment cancelled",
            raw_response={
                "status": "cancelled",
                "reference": reference,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle webhook data from the mock provider."""
        reference = payload.get("reference")
        if not reference:
            return None
        
        # Check if payment exists
        if reference not in self.test_payments:
            return None
        
        # Get payment
        payment = self.test_payments[reference]
        payment_id = payment.get("payment_id")
        
        # Process webhook
        return {
            "provider_reference": reference,
            "status": payload.get("status", "completed"),
            "amount": payload.get("amount"),
            "transaction_id": f"mock-tx-{uuid.uuid4()}",
            "metadata": {
                "payment_id": payment_id,
                "webhook_source": "mock_provider"
            },
            "event_type": payload.get("event_type", "payment_completed")
        }
    
    async def _send_webhook(self, payment_id: int, reference: str) -> None:
        """Send a simulated webhook for a payment."""
        # Wait for the specified delay
        await asyncio.sleep(self.webhook_delay_seconds)
        
        # Get payment
        payment = self.test_payments.get(reference)
        if not payment:
            logger.error(f"Payment {reference} not found for webhook")
            return
        
        # Update payment status to completed
        payment["status"] = "completed"
        
        # Get webhook URL from settings
        webhook_url = payment_settings.get_webhook_url("mock_provider")
        
        # Prepare webhook payload
        payload = {
            "event": "payment.completed",
            "event_type": "payment_completed",
            "reference": reference,
            "status": "completed",
            "amount": payment.get("request", {}).get("amount"),
            "currency": payment.get("request", {}).get("currency"),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "payment_id": payment_id,
                "webhook_source": "mock_provider"
            }
        }
        
        # Log webhook
        logger.info(f"Simulating webhook for payment {payment_id} to {webhook_url}")
        logger.info(f"Webhook payload: {payload}")

# Register the mock provider
PaymentProviderFactory.register(MockPaymentProvider)

async def create_test_payment(
    db: Session,
    user: User,
    amount: float = 100.0,
    currency: str = "USD",
    provider: str = "mock_provider",
    payment_method: str = "credit_card",
    description: str = "Test payment",
    should_fail: bool = False,
    require_approval: bool = False,
    approvers: Optional[List[int]] = None
) -> PaymentDB:
    """
    Create a test payment.
    
    Args:
        db: Database session
        user: User creating the payment
        amount: Payment amount
        currency: Payment currency
        provider: Payment provider to use
        payment_method: Payment method
        description: Payment description
        should_fail: Whether the payment should fail
        require_approval: Whether the payment requires approval
        approvers: List of user IDs that should approve the payment
    
    Returns:
        Created payment
    """
    # Set up mock provider with fail probability if needed
    mock_config = PaymentProviderConfig(
        environment="test",
        extra_config={
            "fail_probability": 1.0 if should_fail else 0.0,
            "delay_seconds": 0.5,
            "webhook_delay_seconds": 1.0,
            "auto_webhook": True
        }
    )
    
    mock_provider = MockPaymentProvider(mock_config)
    PaymentProviderFactory.initialize_provider("mock_provider", mock_provider)
    
    # Create payment
    payment = PaymentDB(
        reference=f"test-{uuid.uuid4()}",
        amount=amount,
        currency=currency,
        status=PaymentStatus.DRAFT.value,
        payment_method=payment_method,
        provider=provider,
        description=description,
        metadata={"test": True, "created_by_test": True},
        created_by_id=user.id,
        customer_id=user.id
    )
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    # Set up approval if needed
    if require_approval and approvers:
        # Create approval steps
        for i, approver_id in enumerate(approvers):
            approval_step = PaymentApprovalStepDB(
                payment_id=payment.id,
                step_order=i + 1,
                approver_id=approver_id,
                status="pending",
                created_at=datetime.utcnow()
            )
            db.add(approval_step)
        
        # Update payment status
        payment.status = PaymentStatus.PENDING_APPROVAL.value
        db.commit()
        db.refresh(payment)
    
    return payment

async def create_test_transaction(
    db: Session,
    payment: PaymentDB,
    status: str = "completed",
    amount: Optional[float] = None,
    provider: Optional[str] = None,
    transaction_type: str = "payment"
) -> PaymentTransactionDB:
    """
    Create a test transaction for a payment.
    
    Args:
        db: Database session
        payment: Payment to create transaction for
        status: Transaction status
        amount: Transaction amount (defaults to payment amount)
        provider: Provider name (defaults to payment provider)
        transaction_type: Transaction type
    
    Returns:
        Created transaction
    """
    transaction = PaymentTransactionDB(
        payment_id=payment.id,
        reference=f"test-tx-{uuid.uuid4()}",
        amount=amount or payment.amount,
        status=status,
        provider=provider or payment.provider,
        provider_reference=f"test-ref-{uuid.uuid4()}",
        transaction_type=transaction_type,
        metadata={"test": True, "created_by_test": True}
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    return transaction

async def complete_test_payment(
    db: Session,
    payment: PaymentDB,
    status: str = PaymentStatus.COMPLETED.value
) -> PaymentDB:
    """
    Complete a test payment.
    
    Args:
        db: Database session
        payment: Payment to complete
        status: Status to set payment to
    
    Returns:
        Updated payment
    """
    # Update payment status
    payment.status = status
    payment.updated_at = datetime.utcnow()
    
    # Create transaction if not exists
    existing_transaction = db.query(PaymentTransactionDB).filter(
        PaymentTransactionDB.payment_id == payment.id,
        PaymentTransactionDB.transaction_type == "payment"
    ).first()
    
    if not existing_transaction:
        transaction = PaymentTransactionDB(
            payment_id=payment.id,
            reference=f"test-tx-{uuid.uuid4()}",
            amount=payment.amount,
            status=status,
            provider=payment.provider,
            provider_reference=f"test-ref-{uuid.uuid4()}",
            transaction_type="payment",
            metadata={"test": True, "created_by_test": True}
        )
        db.add(transaction)
    
    db.commit()
    db.refresh(payment)
    
    return payment

def register_test_routes(app: FastAPI) -> None:
    """
    Register test routes in the FastAPI application.
    
    Args:
        app: FastAPI application
    """
    from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
    
    # Create test router
    router = APIRouter()
    
    @router.post("/test/create")
    async def create_test_payment_route(
        amount: float = Body(100.0),
        currency: str = Body("USD"),
        provider: str = Body("mock_provider"),
        payment_method: str = Body("credit_card"),
        description: str = Body("Test payment"),
        should_fail: bool = Body(False),
        require_approval: bool = Body(False),
        approvers: List[int] = Body([]),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """Create a test payment."""
        return await create_test_payment(
            db=db,
            user=current_user,
            amount=amount,
            currency=currency,
            provider=provider,
            payment_method=payment_method,
            description=description,
            should_fail=should_fail,
            require_approval=require_approval,
            approvers=approvers
        )
    
    @router.post("/test/{payment_id}/complete")
    async def complete_test_payment_route(
        payment_id: int = Path(...),
        status: str = Body(PaymentStatus.COMPLETED.value),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """Complete a test payment."""
        payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        return await complete_test_payment(
            db=db,
            payment=payment,
            status=status
        )
    
    @router.get("/test/mock/{reference}")
    async def view_mock_payment(
        reference: str = Path(...),
        current_user: User = Depends(get_current_active_user)
    ):
        """View a mock payment page."""
        # Get mock provider
        provider = PaymentProviderFactory.get_provider("mock_provider")
        if not isinstance(provider, MockPaymentProvider):
            raise HTTPException(status_code=400, detail="Mock provider not initialized")
        
        # Check if payment exists
        if reference not in provider.test_payments:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Get payment
        payment = provider.test_payments[reference]
        
        # Return HTML page
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Mock Payment Gateway</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
                .header {{ background-color: #f5f5f5; padding: 10px; margin-bottom: 20px; text-align: center; }}
                .payment-details {{ margin-bottom: 20px; }}
                .payment-details div {{ margin-bottom: 10px; }}
                .payment-actions {{ display: flex; justify-content: space-between; }}
                .button {{ padding: 10px 20px; border: none; border-radius: 3px; cursor: pointer; }}
                .success {{ background-color: #4CAF50; color: white; }}
                .failure {{ background-color: #f44336; color: white; }}
                .cancel {{ background-color: #9e9e9e; color: white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Mock Payment Gateway</h1>
                    <p>This is a simulated payment page for testing purposes</p>
                </div>
                
                <div class="payment-details">
                    <div><strong>Reference:</strong> {payment.get('reference')}</div>
                    <div><strong>Amount:</strong> {payment.get('request', {}).get('amount')} {payment.get('request', {}).get('currency')}</div>
                    <div><strong>Description:</strong> {payment.get('request', {}).get('description')}</div>
                    <div><strong>Payment Method:</strong> {payment.get('request', {}).get('payment_method')}</div>
                    <div><strong>Status:</strong> {payment.get('status', 'pending')}</div>
                </div>
                
                <div class="payment-actions">
                    <button class="button success" onclick="completePayment()">Complete Payment</button>
                    <button class="button failure" onclick="failPayment()">Fail Payment</button>
                    <button class="button cancel" onclick="cancelPayment()">Cancel</button>
                </div>
            </div>
            
            <script>
                async function completePayment() {{
                    await sendWebhook('completed');
                    document.querySelector('.payment-details div:last-child').innerHTML = '<strong>Status:</strong> completed';
                    alert('Payment completed successfully!');
                }}
                
                async function failPayment() {{
                    await sendWebhook('failed');
                    document.querySelector('.payment-details div:last-child').innerHTML = '<strong>Status:</strong> failed';
                    alert('Payment failed!');
                }}
                
                async function cancelPayment() {{
                    await sendWebhook('cancelled');
                    document.querySelector('.payment-details div:last-child').innerHTML = '<strong>Status:</strong> cancelled';
                    alert('Payment cancelled!');
                }}
                
                async function sendWebhook(status) {{
                    try {{
                        const response = await fetch('/apipayments/webhook/mock_provider', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }},
                            body: JSON.stringify({{
                                event: `payment.${{status}}`,
                                event_type: `payment_${{status}}`,
                                reference: '{reference}',
                                status: status,
                                amount: {payment.get('request', {}).get('amount')},
                                currency: '{payment.get('request', {}).get('currency')}',
                                timestamp: new Date().toISOString(),
                                metadata: {{
                                    payment_id: {payment.get('payment_id')},
                                    webhook_source: 'mock_provider'
                                }}
                            }})
                        }});
                        
                        if (response.ok) {{
                            console.log('Webhook sent successfully');
                        }} else {{
                            console.error('Error sending webhook');
                        }}
                    }} catch (error) {{
                        console.error('Error sending webhook', error);
                    }}
                }}
            </script>
        </body>
        </html>
        """
        
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)
    
    # Add routes to the application
    app.include_router(router)
