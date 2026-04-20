"""
Stripe payment provider implementation.

This module implements the Stripe payment provider interface.
"""
import logging
import hmac
import hashlib
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
import secrets

import aiohttp

from ..models.payment import PaymentStatus, RefundStatus, RefundResponse
from ..models.provider import ProviderResponse, PaymentRequest, RefundRequest
from ..models.subscription import SubscriptionRequest, SubscriptionStatus, SubscriptionResponse
from .base_provider import BasePaymentProvider
from .provider_factory import PaymentProviderFactory

logger = logging.getLogger("kaapi.payment.stripe")


@PaymentProviderFactory.register
class StripeProvider(BasePaymentProvider):
    """Stripe payment provider implementation."""

    provider_id = "stripe"
    provider_name = "Stripe"
    logo_url = "https://stripe.com/img/v3/home/twitter.png"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize a Stripe payment provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        
        # Initialize provider with needed credentials
        self.api_key = config.get("api_key", "")
        self.publishable_key = config.get("publishable_key", "")
        self.webhook_secret = config.get("webhook_secret", "")
        
        # API configuration
        self.mode = config.get("mode", "test").lower()
        self.api_base_url = "https://api.stripe.com/v1"
        
        # Callbacks
        self.success_url = config.get("success_url", "")
        self.cancel_url = config.get("cancel_url", "")
        
        # Default currency if not specified
        self.default_currency = config.get("default_currency", "USD")
        
        logger.info(f"Stripe payment provider initialized with mode: {self.mode}")
    
    @property
    def id(self) -> str:
        """Get provider ID."""
        return self.provider_id
    
    @property
    def name(self) -> str:
        """Get provider name."""
        return self.provider_name
    
    @property
    def description(self) -> str:
        """Get provider description."""
        return "Stripe payment processing for global businesses"
    
    @property
    def supported_methods(self) -> List[str]:
        """Get supported payment methods."""
        return ["card", "bank_transfer", "alipay", "apple_pay", "google_pay", "sepa", "ideal", "sofort"]
    
    @property
    def supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        return ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CNY", "INR", "NGN", "KES", "ZAR", "EGP", "GHS"]
    
    @property
    def supported_countries(self) -> List[str]:
        """Get supported countries."""
        return ["US", "GB", "DE", "FR", "CA", "AU", "JP", "SG", "HK", "IN", "NG", "KE", "ZA", "EG", "GH"]

    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through Stripe.
        
        Args:
            payment_request: Payment request details
            
        Returns:
            Provider response with payment details
        """
        try:
            # Validate the payment request for compliance
            if not self.validate_payment_request(payment_request):
                logger.error("Payment validation failed")
                return ProviderResponse(
                    success=False,
                    status=PaymentStatus.FAILED,
                    provider_reference="",
                    message="Payment validation failed",
                    raw_response={"error": "validation_failed"}
                )
            
            # Encrypt sensitive metadata before processing
            encrypted_metadata = None
            if payment_request.request_metadata:
                encrypted_metadata = self.encrypt_sensitive_data(payment_request.request_metadata)
            
            # Create a payment session with Stripe
            session_data = {
                "payment_method_types[]": "card",
                "line_items[0][price_data][currency]": payment_request.currency,
                "line_items[0][price_data][product_data][name]": payment_request.description or "Payment",
                "line_items[0][price_data][unit_amount]": int(payment_request.amount * 100),  # Stripe requires cents
                "line_items[0][quantity]": 1,
                "mode": "payment",
                "success_url": f"{self.success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": self.cancel_url,
            }
            
            # Add customer email if available
            if payment_request.customer_email:
                session_data["customer_email"] = payment_request.customer_email
            
            # Add metadata if available
            if encrypted_metadata:
                for key, value in encrypted_metadata.items():
                    session_data[f"request_metadata[{key}]"] = str(value)
            
            # Add payment ID reference
            session_data["request_metadata[payment_id]"] = payment_request.payment_id
            
            # Create checkout session
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/checkout/sessions",
                    headers=headers,
                    data=session_data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Stripe payment error: {error_text}")
                        return ProviderResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference="",
                            message="Failed to create Stripe checkout session",
                            raw_response={"error": error_text}
                        )
                    
                    result = await response.json()
                    session_id = result.get("id")
                    checkout_url = result.get("url")
                    
                    # Log successful payment initiation
                    payment_log_data = {
                        "amount": payment_request.amount,
                        "currency": payment_request.currency,
                        "checkout_session_id": session_id,
                        "payment_id": payment_request.payment_id
                    }
                    self.log_payment_transaction(
                        session_id,
                        payment_log_data,
                        "initiated"
                    )
                    
                    return ProviderResponse(
                        success=True,
                        status=PaymentStatus.PENDING,
                        provider_reference=session_id,
                        redirect_url=checkout_url,
                        message="Payment initiated. Redirect customer to checkout URL.",
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"Stripe payment error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )

    async def verify_payment(self, reference: str) -> ProviderResponse:
        """
        Verify a payment with Stripe.
        
        Args:
            reference: Provider reference to verify (session_id)
            
        Returns:
            Provider response with payment status
        """
        try:
            # Make API request to check session status
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/checkout/sessions/{reference}",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Stripe verification error: {error_text}")
                        return ProviderResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference=reference,
                            message="Failed to verify Stripe checkout session",
                            raw_response={"error": error_text}
                        )
                    
                    result = await response.json()
                    payment_status = result.get("payment_status")
                    payment_intent = result.get("payment_intent")
                    
                    # Map Stripe status to payment status
                    status = PaymentStatus.PENDING
                    success = False
                    
                    if payment_status == "paid":
                        status = PaymentStatus.SUCCESS
                        success = True
                    elif payment_status == "unpaid":
                        status = PaymentStatus.PENDING
                    else:
                        status = PaymentStatus.FAILED
                    
                    # Log payment verification
                    verification_log_data = {
                        "checkout_session_id": reference,
                        "payment_status": payment_status,
                        "payment_intent": payment_intent
                    }
                    self.log_payment_transaction(
                        reference,
                        verification_log_data,
                        "verified"
                    )
                    
                    return ProviderResponse(
                        success=success,
                        status=status,
                        provider_reference=reference,
                        message=f"Payment {payment_status}",
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"Stripe verification error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.UNKNOWN,
                provider_reference=reference,
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def process_refund(self, refund_request: RefundRequest) -> ProviderResponse:
        """
        Process a refund request through Stripe.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Provider response with refund details
        """
        try:
            # First, retrieve the payment intent from the checkout session
            # to get the payment intent ID for refunding
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # If the reference is a checkout session ID, get the payment intent first
            if refund_request.payment_reference.startswith("cs_"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.api_base_url}/checkout/sessions/{refund_request.payment_reference}",
                        headers=headers
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Stripe session retrieval error: {error_text}")
                            return ProviderResponse(
                                success=False,
                                status=RefundStatus.FAILED,
                                provider_reference="",
                                message="Failed to retrieve Stripe checkout session",
                                raw_response={"error": error_text}
                            )
                        
                        session_data = await response.json()
                        payment_intent_id = session_data.get("payment_intent")
                        
                        if not payment_intent_id:
                            return ProviderResponse(
                                success=False,
                                status=RefundStatus.FAILED,
                                provider_reference="",
                                message="No payment intent found for the session",
                                raw_response=session_data
                            )
            else:
                # Assume the reference is already a payment intent ID
                payment_intent_id = refund_request.payment_reference
            
            # Prepare refund data
            refund_data = {
                "payment_intent": payment_intent_id,
                "amount": int(refund_request.amount * 100) if refund_request.amount else None,  # Stripe requires cents
                "reason": refund_request.reason if refund_request.reason else "requested_by_customer",
                "refund_metadata[refund_id]": refund_request.refund_metadata.get("refund_id", "")
            }
            
            # Process refund
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/refunds",
                    headers=headers,
                    data=refund_data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Stripe refund error: {error_text}")
                        return ProviderResponse(
                            success=False,
                            status=RefundStatus.FAILED,
                            provider_reference="",
                            message="Failed to process Stripe refund",
                            raw_response={"error": error_text}
                        )
                    
                    result = await response.json()
                    refund_id = result.get("id")
                    refund_status = result.get("status")
                    
                    # Log refund transaction
                    refund_log_data = {
                        "refund_id": refund_id,
                        "payment_intent": payment_intent_id,
                        "amount": refund_request.amount,
                        "currency": result.get("currency", ""),
                        "reason": refund_request.reason,
                        "status": refund_status
                    }
                    self.log_refund_transaction(
                        refund_id,
                        refund_log_data,
                        "processed"
                    )
                    
                    # Map Stripe refund status to internal status
                    status = RefundStatus.PENDING
                    success = True
                    
                    if refund_status == "succeeded":
                        status = RefundStatus.SUCCESS
                    elif refund_status == "failed":
                        status = RefundStatus.FAILED
                        success = False
                    
                    return ProviderResponse(
                        success=success,
                        status=status,
                        provider_reference=refund_id,
                        message=f"Refund {refund_status}",
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"Stripe refund error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=RefundStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    def verify_webhook_signature(self, signature: str, payload: str) -> bool:
        """
        Verify webhook signature from Stripe.
        
        Args:
            signature: Signature from webhook request
            payload: Request body as string
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret or not signature or not payload:
            logger.warning("Missing webhook secret, signature, or payload for Stripe webhook verification")
            return False
            
        try:
            # Extract timestamp and signature from header
            signature_parts = signature.split(",")
            timestamp = ""
            sig_value = ""
            
            for part in signature_parts:
                key_val = part.split("=")
                if len(key_val) != 2:
                    continue
                    
                key, val = key_val
                if key == "t":
                    timestamp = val
                elif key == "v1":
                    sig_value = val
            
            if not timestamp or not sig_value:
                logger.error("Invalid Stripe signature format")
                return False
            
            # Recreate the expected signature
            signed_payload = f"{timestamp}.{payload}"
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Log webhook event for security auditing
            webhook_data = json.loads(payload)
            event_id = webhook_data.get("id", "unknown")
            
            self.log_payment_transaction(
                event_id,
                {
                    "webhook_event": webhook_data,
                    "signature": signature,
                    "signature_valid": sig_value == expected_signature
                },
                "webhook_received"
            )
            
            # Compare signatures (constant-time comparison to prevent timing attacks)
            return hmac.compare_digest(sig_value, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying Stripe webhook signature: {str(e)}")
            return False
            
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Handle webhook events from Stripe.
        
        Args:
            payload: Webhook payload as dict
            headers: HTTP request headers
            
        Returns:
            Processed data or None if validation fails
        """
        try:
            # Get signature from headers
            signature = headers.get("stripe-signature")
            if not signature:
                logger.warning("Missing Stripe signature header")
                return None
                
            # Verify signature
            is_valid = self.verify_webhook_signature(
                signature=signature,
                payload=json.dumps(payload)
            )
            
            if not is_valid:
                logger.warning("Invalid Stripe webhook signature")
                return None
                
            # Process webhook based on event type
            event_type = payload.get("type")
            event_data = payload.get("data", {}).get("object", {})
            
            if event_type == "checkout.session.completed":
                # Payment completed via checkout
                session_id = event_data.get("id")
                payment_status = event_data.get("payment_status")
                
                # Log webhook processing
                webhook_log_data = {
                    "event_type": event_type,
                    "session_id": session_id,
                    "payment_status": payment_status
                }
                self.log_payment_transaction(
                    session_id,
                    webhook_log_data,
                    "webhook_processed"
                )
                
                return {
                    "event_type": event_type,
                    "provider_reference": session_id,
                    "payment_status": payment_status,
                    "processed": True
                }
                
            elif event_type == "charge.refunded":
                # Refund processed
                refund_id = event_data.get("refunds", {}).get("data", [{}])[0].get("id", "")
                
                # Log webhook processing
                webhook_log_data = {
                    "event_type": event_type,
                    "refund_id": refund_id,
                    "status": "completed"
                }
                self.log_refund_transaction(
                    refund_id,
                    webhook_log_data,
                    "webhook_processed"
                )
                
                return {
                    "event_type": event_type,
                    "provider_reference": refund_id,
                    "status": "completed",
                    "processed": True
                }
                
            # For other events, just log and return the event
            logger.info(f"Unhandled Stripe webhook event: {event_type}")
            return {
                "event_type": event_type,
                "processed": True,
                "data": event_data
            }
            
        except Exception as e:
            logger.error(f"Error handling Stripe webhook: {str(e)}")
            return None
