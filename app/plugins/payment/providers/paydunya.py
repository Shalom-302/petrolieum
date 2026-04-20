"""
PayDunya payment provider implementation.

This module implements the PayDunya payment provider interface.
"""
import logging
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union

import aiohttp

from ..models.payment import PaymentStatus, RefundStatus, RefundResponse
from ..models.provider import ProviderResponse, PaymentRequest, RefundRequest
from ..models.subscription import SubscriptionRequest, SubscriptionStatus, SubscriptionResponse
from .base_provider import BasePaymentProvider
from .provider_factory import PaymentProviderFactory

logger = logging.getLogger("kaapi.payment.paydunya")

@PaymentProviderFactory.register
class PayDunyaProvider(BasePaymentProvider):
    """PayDunya payment provider implementation."""

    provider_id = "paydunya"
    provider_name = "PayDunya"
    logo_url = "https://paydunya.com/assets/images/logo.png"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize a PayDunya payment provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        self.master_key = config.get("master_key", "")
        self.private_key = config.get("private_key", "")
        self.public_key = config.get("public_key", "")
        self.token = config.get("token", "")
        self.mode = config.get("mode", "test").lower()  # test or live
        
        # Set API base URL based on mode
        self.api_base_url = "https://app.paydunya.com/api/v1"
        if self.mode == "test":
            self.api_base_url = "https://app.paydunya.com/sandbox-api/v1"
            
        # Webhook secret for signature verification
        self.webhook_secret = config.get("webhook_secret", "")
        
        logger.info(f"PayDunya payment provider initialized with mode: {self.mode}")
    
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
        return "PayDunya payment services for West Africa"
    
    @property
    def supported_methods(self) -> List[str]:
        """Get supported payment methods."""
        return ["card", "mobile_money", "bank_transfer"]
    
    @property
    def supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        return ["XOF", "XAF", "GHS", "GNF"]
    
    @property
    def supported_countries(self) -> List[str]:
        """Get supported countries."""
        return ["SN", "CI", "BJ", "TG", "CM", "GN", "GH"]
    
    def _generate_headers(self) -> Dict[str, str]:
        """
        Generate required headers for PayDunya API.
        
        Returns:
            Dictionary of header key-value pairs
        """
        return {
            "PAYDUNYA-MASTER-KEY": self.master_key,
            "PAYDUNYA-PRIVATE-KEY": self.private_key,
            "PAYDUNYA-PUBLIC-KEY": self.public_key,
            "PAYDUNYA-TOKEN": self.token,
            "Content-Type": "application/json"
        }
    
    def _prepare_payment_data(self, payment_request: PaymentRequest) -> Dict[str, Any]:
        """
        Prepare payment data for PayDunya API.
        
        Args:
            payment_request: Payment request details
            
        Returns:
            Prepared payment data for API request
        """
        # Extract customer information
        customer_name = payment_request.customer_name or ""
        customer_email = payment_request.customer_email or ""
        customer_phone = payment_request.customer_phone or ""
        
        # Encrypt sensitive metadata if available
        encrypted_metadata = {}
        if payment_request.metadata:
            encrypted_metadata = self.encrypt_sensitive_data(payment_request.metadata)
        
        # Create payment data structure
        payment_data = {
            "invoice": {
                "items": {},
                "total_amount": payment_request.amount,
                "description": payment_request.description or "Payment"
            },
            "store": {
                "name": self.config.get("store_name", "Store"),
                "tagline": self.config.get("store_tagline", "Secure payments"),
                "phone": self.config.get("store_phone", ""),
                "postal_address": self.config.get("store_address", "")
            },
            "custom_data": {
                "payment_id": payment_request.payment_id,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "encrypted_metadata": encrypted_metadata,
                "secure_transaction": True
            }
        }
        
        # Add callback URLs if available
        if hasattr(payment_request, 'success_url') and payment_request.success_url:
            if not payment_data.get("actions"):
                payment_data["actions"] = {}
            payment_data["actions"]["return_url"] = payment_request.success_url
            
        if hasattr(payment_request, 'cancel_url') and payment_request.cancel_url:
            if not payment_data.get("actions"):
                payment_data["actions"] = {}
            payment_data["actions"]["cancel_url"] = payment_request.cancel_url
            
        if hasattr(payment_request, 'callback_url') and payment_request.callback_url:
            if not payment_data.get("actions"):
                payment_data["actions"] = {}
            payment_data["actions"]["callback_url"] = payment_request.callback_url
        
        # Add items to payment data if available
        if hasattr(payment_request, 'items') and payment_request.items:
            for i, item in enumerate(payment_request.items):
                key = f"item_{i}"
                payment_data["invoice"]["items"][key] = {
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.quantity * item.unit_price,
                    "description": item.description or ""
                }
        
        return payment_data
    
    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through PayDunya.
        
        Args:
            payment_request: Payment request details
            
        Returns:
            Provider response with payment details
        """
        try:
            # Validate payment request
            if not self.validate_payment_request(payment_request):
                logger.error("Payment validation failed: Invalid payment data")
                return ProviderResponse(
                    success=False,
                    payment_id=payment_request.payment_id,
                    provider_payment_id=None,
                    redirect_url=None,
                    status=PaymentStatus.FAILED.value,
                    message="Payment validation failed: Invalid payment data",
                    raw_response={"error": "validation_failed"}
                )
            
            # Prepare data for API request
            payment_data = self._prepare_payment_data(payment_request)
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/checkout-invoice/create"
                headers = self._generate_headers()
                async with session.post(url, json=payment_data, headers=headers) as response:
                    response_data = await response.json()
                    
                    # Log the transaction attempt
                    payment_log_data = {
                        "amount": payment_request.amount,
                        "currency": payment_request.currency if hasattr(payment_request, 'currency') else "XOF",
                        "payment_id": payment_request.payment_id,
                        "provider_response": response_data
                    }
                    
                    if not response.ok or not response_data.get("response_code") == "00":
                        error_message = response_data.get("response_text", "Unknown error")
                        logger.error(f"PayDunya payment error: {error_message}")
                        
                        self.log_payment_transaction(
                            payment_request.payment_id,
                            payment_log_data,
                            "failed"
                        )
                        
                        return ProviderResponse(
                            success=False,
                            payment_id=payment_request.payment_id,
                            provider_payment_id=None,
                            redirect_url=None,
                            status=PaymentStatus.FAILED.value,
                            message=f"Payment failed: {error_message}",
                            raw_response=response_data
                        )
                    
                    # Extract payment details from response
                    token = response_data.get("token")
                    if not token:
                        logger.error("No token found in PayDunya response")
                        return ProviderResponse(
                            success=False,
                            payment_id=payment_request.payment_id,
                            provider_payment_id=None,
                            redirect_url=None,
                            status=PaymentStatus.FAILED.value,
                            message="No payment token found in response",
                            raw_response=response_data
                        )
                    
                    # Construct payment URL
                    payment_url = f"{self.api_base_url.replace('/api/v1', '')}/checkout/{token}"
                    
                    # Log the successful payment initiation
                    payment_log_data["token"] = token
                    payment_log_data["payment_url"] = payment_url
                    
                    self.log_payment_transaction(
                        payment_request.payment_id,
                        payment_log_data,
                        "initiated"
                    )
                    
                    return ProviderResponse(
                        success=True,
                        payment_id=payment_request.payment_id,
                        provider_payment_id=token,
                        redirect_url=payment_url,
                        status=PaymentStatus.PENDING.value,
                        message="Payment initiated, redirect customer to payment URL",
                        raw_response=response_data
                    )
        except Exception as e:
            logger.error(f"Error processing PayDunya payment: {str(e)}")
            return ProviderResponse(
                success=False,
                payment_id=payment_request.payment_id,
                provider_payment_id=None,
                redirect_url=None,
                status=PaymentStatus.FAILED.value,
                message=f"Error processing payment: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    async def verify_payment(self, payment_token: str) -> ProviderResponse:
        """
        Verify a payment status with PayDunya.
        
        Args:
            payment_token: PayDunya payment token
            
        Returns:
            Provider response with payment status
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/checkout-invoice/confirm/{payment_token}"
                headers = self._generate_headers()
                async with session.get(url, headers=headers) as response:
                    response_data = await response.json()
                    
                    # Log verification attempt
                    verification_log_data = {
                        "token": payment_token,
                        "provider_response": response_data
                    }
                    
                    self.log_payment_transaction(
                        payment_token,
                        verification_log_data,
                        "verified"
                    )
                    
                    if not response.ok or not response_data.get("response_code") == "00":
                        error_message = response_data.get("response_text", "Unknown error")
                        logger.error(f"PayDunya verification error: {error_message}")
                        return ProviderResponse(
                            success=False,
                            payment_id=None,
                            provider_payment_id=payment_token,
                            redirect_url=None,
                            status=PaymentStatus.UNKNOWN.value,
                            message=f"Payment verification failed: {error_message}",
                            raw_response=response_data
                        )
                    
                    # Extract payment status
                    status = response_data.get("status", "").lower()
                    invoice_data = response_data.get("invoice", {})
                    custom_data = invoice_data.get("custom_data", {})
                    payment_id = custom_data.get("payment_id")
                    
                    # Map status to internal status
                    if status == "completed":
                        internal_status = PaymentStatus.SUCCESS.value
                        success = True
                        message = "Payment completed successfully"
                    elif status == "pending":
                        internal_status = PaymentStatus.PENDING.value
                        success = False
                        message = "Payment is pending"
                    elif status == "cancelled":
                        internal_status = PaymentStatus.FAILED.value
                        success = False
                        message = "Payment was cancelled"
                    else:
                        internal_status = PaymentStatus.UNKNOWN.value
                        success = False
                        message = f"Unknown payment status: {status}"
                    
                    return ProviderResponse(
                        success=success,
                        payment_id=payment_id,
                        provider_payment_id=payment_token,
                        redirect_url=None,
                        status=internal_status,
                        message=message,
                        raw_response=response_data
                    )
        except Exception as e:
            logger.error(f"Error verifying PayDunya payment: {str(e)}")
            return ProviderResponse(
                success=False,
                payment_id=None,
                provider_payment_id=payment_token,
                redirect_url=None,
                status=PaymentStatus.UNKNOWN.value,
                message=f"Error verifying payment: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    async def process_refund(self, refund_request: RefundRequest) -> ProviderResponse:
        """
        Process a refund through PayDunya.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Provider response with refund status
        """
        try:
            # PayDunya doesn't have a direct API for refunds, typically this would be managed
            # through their dashboard or a support request, but we'll implement a dummy version
            
            # Encrypt sensitive refund data if available
            encrypted_metadata = {}
            if refund_request.metadata:
                encrypted_metadata = self.encrypt_sensitive_data(refund_request.metadata)
            
            # Log the refund request
            refund_log_data = {
                "payment_id": refund_request.payment_id if hasattr(refund_request, 'payment_id') else None,
                "provider_payment_id": refund_request.provider_payment_id,
                "amount": refund_request.amount,
                "reason": refund_request.reason if hasattr(refund_request, 'reason') else None,
                "metadata": encrypted_metadata
            }
            
            # Generate refund ID if not provided
            refund_id = getattr(refund_request, 'refund_id', f"refund-{int(time.time())}")
            
            self.log_refund_transaction(
                refund_id,
                refund_log_data,
                "requested"
            )
            
            # Return a response indicating manual processing is required
            # In a real implementation, this might be an API call to PayDunya's refund endpoint if available
            return ProviderResponse(
                success=True,
                payment_id=refund_request.payment_id if hasattr(refund_request, 'payment_id') else None,
                provider_payment_id=refund_request.provider_payment_id,
                redirect_url=None,
                status=RefundStatus.PENDING.value,
                message="Refund request logged. Manual processing required through PayDunya dashboard.",
                raw_response={"status": "manual_processing_required"}
            )
        except Exception as e:
            logger.error(f"Error processing PayDunya refund: {str(e)}")
            return ProviderResponse(
                success=False,
                payment_id=refund_request.payment_id if hasattr(refund_request, 'payment_id') else None,
                provider_payment_id=refund_request.provider_payment_id,
                redirect_url=None,
                status=RefundStatus.FAILED.value,
                message=f"Error processing refund: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    def verify_webhook_signature(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """
        Verify PayDunya webhook signature.
        
        Args:
            payload: Webhook payload
            headers: HTTP headers from webhook request
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.webhook_secret:
                logger.warning("PayDunya webhook secret not configured")
                return False
            
            # Get signature from headers
            signature = headers.get("X-Paydunya-Signature")
            if not signature:
                logger.warning("No signature found in PayDunya webhook headers")
                return False
            
            # Convert payload to string if it's a dict
            if isinstance(payload, dict):
                payload_str = json.dumps(payload)
            else:
                payload_str = payload
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Log webhook verification attempt
            self.log_payment_transaction(
                str(int(time.time())),  # Use current timestamp as ID
                {
                    "event_type": "webhook_verification",
                    "signature_valid": hmac.compare_digest(expected_signature, signature),
                    "payload_size": len(payload_str)
                },
                "webhook_received"
            )
            
            # Compare signatures (constant-time comparison to prevent timing attacks)
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying PayDunya webhook signature: {str(e)}")
            return False
    
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Handle webhook data from PayDunya.
        
        Args:
            payload: Webhook payload
            headers: HTTP headers
            
        Returns:
            Processed webhook data or None if verification failed
        """
        try:
            # Verify webhook signature
            if not self.verify_webhook_signature(payload, headers):
                logger.warning("Invalid PayDunya webhook signature")
                return None
            
            # Extract data from payload
            invoice_token = payload.get("invoice_token")
            status = payload.get("status", "").lower()
            
            # Log webhook processing
            webhook_log_data = {
                "invoice_token": invoice_token,
                "status": status,
                "payload": payload
            }
            
            self.log_payment_transaction(
                invoice_token or str(int(time.time())),
                webhook_log_data,
                "webhook_processed"
            )
            
            # Map status to internal status
            if status == "completed":
                internal_status = PaymentStatus.SUCCESS.value
            elif status == "pending":
                internal_status = PaymentStatus.PENDING.value
            elif status == "cancelled":
                internal_status = PaymentStatus.FAILED.value
            else:
                internal_status = PaymentStatus.UNKNOWN.value
            
            # Return processed webhook data
            return {
                "provider_payment_id": invoice_token,
                "status": internal_status,
                "processed": True,
                "data": payload
            }
            
        except Exception as e:
            logger.error(f"Error handling PayDunya webhook: {str(e)}")
            return None
