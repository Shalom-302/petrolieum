"""
Hub2 payment provider implementation.

This module implements the Hub2 payment provider interface.
"""
import logging
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

import aiohttp

from ..models.payment import PaymentStatus, RefundStatus, RefundResponse
from ..models.provider import ProviderResponse, PaymentRequest, RefundRequest
from ..models.subscription import SubscriptionRequest, SubscriptionStatus, SubscriptionResponse
from .base_provider import BasePaymentProvider
from .provider_factory import PaymentProviderFactory

logger = logging.getLogger("kaapi.payment.hub2")


@PaymentProviderFactory.register
class Hub2Provider(BasePaymentProvider):
    """Hub2 payment provider implementation."""

    provider_id = "hub2"
    provider_name = "Hub2"
    logo_url = "https://hub2.io/images/logo.png"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize a Hub2 payment provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        
        # Initialize provider with needed credentials
        self.merchant_id = config.get("merchant_id", "")
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        
        # API configuration
        self.mode = config.get("mode", "sandbox").lower()
        self.api_base_url = "https://api.hub2.io" if self.mode == "live" else "https://sandbox.hub2.io"
        
        # Callbacks
        self.success_url = config.get("success_url", "")
        self.cancel_url = config.get("cancel_url", "")
        self.webhook_url = config.get("webhook_url", "")
        
        logger.info(f"Hub2 payment provider initialized with mode: {self.mode}")

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
        return "Hub2 payment processing for businesses in Africa"
    
    @property
    def supported_methods(self) -> List[str]:
        """Get supported payment methods."""
        return ["card", "bank_transfer", "mobile_money"]
    
    @property
    def supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        return ["XOF", "XAF", "NGN", "GHS", "USD", "EUR"]
    
    @property
    def supported_countries(self) -> List[str]:
        """Get supported countries."""
        return ["BJ", "BF", "CI", "GH", "ML", "NE", "NG", "SN", "TG"]

    def _generate_signature(self, payload: Dict[str, Any]) -> str:
        """
        Generate HMAC signature for API requests.
        
        Args:
            payload: Data to sign
            
        Returns:
            Signature string
        """
        # Convert payload to JSON string
        payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        
        # Create signature
        signature = hmac.new(
            self.api_secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature

    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through Hub2.
        
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
            
            # Create transaction reference
            transaction_ref = f"hub2-{int(time.time())}-{payment_request.payment_id}"
            
            # Prepare payment request
            payment_data = {
                "merchant_id": self.merchant_id,
                "transaction_ref": transaction_ref,
                "amount": payment_request.amount,
                "currency": payment_request.currency,
                "description": payment_request.description or "Payment",
                "customer": {
                    "email": payment_request.customer_email,
                    "name": payment_request.customer_name,
                    "phone": payment_request.customer_phone
                },
                "request_metadata": encrypted_metadata,
                "return_url": self.success_url,
                "cancel_url": self.cancel_url,
                "webhook_url": self.webhook_url
            }
            
            # Sign the request
            signature = self._generate_signature(payment_data)
            
            # Make API request
            headers = {
                "Content-Type": "application/json",
                "X-Hub2-Merchant-ID": self.merchant_id,
                "X-Hub2-API-Key": self.api_key,
                "X-Hub2-Signature": signature
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}payments",
                    headers=headers,
                    json=payment_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("success"):
                        error_message = result.get("message", "Unknown error")
                        logger.error(f"Hub2 payment error: {error_message}")
                        return ProviderResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference="",
                            message=error_message,
                            raw_response=result
                        )
                    
                    payment_data = result.get("data", {})
                    payment_id = payment_data.get("payment_id", "")
                    checkout_url = payment_data.get("checkout_url", "")
                    
                    # Log successful payment initiation
                    payment_log_data = {
                        "amount": payment_request.amount,
                        "currency": payment_request.currency,
                        "transaction_ref": transaction_ref,
                        "payment_id": payment_id
                    }
                    self.log_payment_transaction(payment_id, payment_log_data, "initiated")
                    
                    return ProviderResponse(
                        success=True,
                        status=PaymentStatus.PENDING,
                        provider_reference=payment_id,
                        redirect_url=checkout_url,
                        message="Payment initiated. Redirect customer to checkout URL.",
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"Hub2 payment error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )

    async def verify_payment(self, reference: str) -> ProviderResponse:
        """
        Verify a payment with Hub2.
        
        Args:
            reference: Provider reference to verify (payment_id)
            
        Returns:
            Provider response with payment status
        """
        try:
            # Prepare verification request
            verification_data = {
                "merchant_id": self.merchant_id,
                "payment_id": reference
            }
            
            # Sign the request
            signature = self._generate_signature(verification_data)
            
            # Make API request
            headers = {
                "Content-Type": "application/json",
                "X-Hub2-Merchant-ID": self.merchant_id,
                "X-Hub2-API-Key": self.api_key,
                "X-Hub2-Signature": signature
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}payments/{reference}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("success"):
                        error_message = result.get("message", "Unknown error")
                        logger.error(f"Hub2 verification error: {error_message}")
                        return ProviderResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference=reference,
                            message=error_message,
                            raw_response=result
                        )
                    
                    payment_data = result.get("data", {})
                    status = payment_data.get("status", "pending").lower()
                    
                    # Map Hub2 status to payment status
                    payment_status = PaymentStatus.PENDING
                    success = False
                    
                    if status == "completed" or status == "successful":
                        payment_status = PaymentStatus.SUCCESS
                        success = True
                    elif status == "failed" or status == "cancelled":
                        payment_status = PaymentStatus.FAILED
                    elif status == "pending":
                        payment_status = PaymentStatus.PENDING
                    
                    # Log payment verification
                    verification_log_data = {
                        "status": status,
                        "payment_id": reference,
                        "transaction_data": payment_data
                    }
                    self.log_payment_transaction(reference, verification_log_data, "verified")
                    
                    return ProviderResponse(
                        success=success,
                        status=payment_status,
                        provider_reference=reference,
                        message=payment_data.get("message", "Payment verification processed"),
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"Hub2 verification error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.UNKNOWN,
                provider_reference=reference,
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def process_refund(self, refund_request: RefundRequest) -> ProviderResponse:
        """
        Process a refund request through Hub2.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Provider response with refund details
        """
        try:
            # Prepare refund request
            refund_data = {
                "merchant_id": self.merchant_id,
                "payment_id": refund_request.payment_reference,
                "amount": refund_request.amount,
                "reason": refund_request.reason or "Customer requested refund",
                "refund_id": refund_request.refund_id
            }
            
            # Sign the request
            signature = self._generate_signature(refund_data)
            
            # Make API request
            headers = {
                "Content-Type": "application/json",
                "X-Hub2-Merchant-ID": self.merchant_id,
                "X-Hub2-API-Key": self.api_key,
                "X-Hub2-Signature": signature
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}refunds",
                    headers=headers,
                    json=refund_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("success"):
                        error_message = result.get("message", "Unknown error")
                        logger.error(f"Hub2 refund error: {error_message}")
                        return ProviderResponse(
                            success=False,
                            status=RefundStatus.FAILED,
                            provider_reference="",
                            message=error_message,
                            raw_response=result
                        )
                    
                    refund_data = result.get("data", {})
                    refund_id = refund_data.get("refund_id", "")
                    
                    # Log refund transaction
                    refund_log_data = {
                        "amount": refund_request.amount,
                        "payment_reference": refund_request.payment_reference,
                        "refund_id": refund_id,
                        "reason": refund_request.reason,
                        "refund_metadata": refund_request.refund_metadata
                    }
                    self.log_refund_transaction(refund_id, refund_log_data, "processed")
                    
                    return ProviderResponse(
                        success=True,
                        status=RefundStatus.SUCCESS,
                        provider_reference=refund_id,
                        message="Refund processed successfully",
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"Hub2 refund error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=RefundStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    def verify_webhook_signature(self, signature: str, payload: str) -> bool:
        """
        Verify webhook signature from Hub2.
        
        Args:
            signature: Signature from webhook request
            payload: Request body as string
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.api_secret or not payload:
            logger.warning("Missing API secret or payload for webhook verification")
            return False
            
        try:
            # Calculate expected signature
            expected_signature = hmac.new(
                self.api_secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Log webhook event for security auditing
            webhook_data = json.loads(payload)
            payment_id = webhook_data.get("data", {}).get("payment_id", "unknown")
            
            self.log_payment_transaction(
                payment_id,
                {
                    "webhook_event": webhook_data,
                    "signature": signature,
                    "signature_valid": signature == expected_signature
                },
                "webhook_received"
            )
            
            # Compare signatures (constant-time comparison to prevent timing attacks)
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
