"""
Flutterwave payment provider implementation.

This module implements the Flutterwave payment provider interface.
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

logger = logging.getLogger("kaapi.payment.flutterwave")

@PaymentProviderFactory.register
class FlutterwaveProvider(BasePaymentProvider):
    """Flutterwave payment provider implementation."""

    provider_id = "flutterwave"
    provider_name = "Flutterwave"
    logo_url = "https://flutterwave.com/images/logo-colored.svg"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize a Flutterwave payment provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        
        # Initialize provider with needed credentials
        self.secret_key = config.get("secret_key", "")
        self.public_key = config.get("public_key", "")
        self.encryption_key = config.get("encryption_key", "")
        
        # API configuration
        self.api_base_url = "https://api.flutterwave.com/v3"
        self.webhook_secret = config.get("webhook_secret", "")
        
        # Callback URLs
        self.redirect_url = config.get("redirect_url", "")
        self.webhook_url = config.get("webhook_url", "")
        
        logger.info("Flutterwave payment provider initialized")
    
    @property
    def id(self) -> str:
        """Get provider ID."""
        return self.provider_id
    
    @property
    def name(self) -> str:
        """Get provider name."""
        return self.provider_name

    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through Flutterwave.
        
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
                    message="Payment failed due to validation errors",
                    raw_response={"errors": ["Invalid payment data"]}
                )
            
            # Encrypt sensitive metadata before processing
            encrypted_metadata = {}
            if payment_request.metadata:
                encrypted_metadata = self.encrypt_sensitive_data(payment_request.metadata)
            
            # Extract customer information
            customer_name = payment_request.customer_name or "Customer"
            customer_email = payment_request.customer_email or ""
            customer_phone = payment_request.customer_phone or ""
            
            # Split name into first name and last name (required by Flutterwave)
            name_parts = customer_name.split(maxsplit=1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else first_name
            
            # Generate transaction reference
            tx_ref = f"FW-{int(time.time())}-{payment_request.payment_id}"
            
            # Prepare payment data
            payment_data = {
                "tx_ref": tx_ref,
                "amount": payment_request.amount,
                "currency": payment_request.currency.upper(),
                "redirect_url": self.redirect_url,
                "payment_options": "card,banktransfer,ussd,mpesa",  # Enable multiple payment options
                "meta": {
                    "payment_id": payment_request.payment_id,
                    "metadata": encrypted_metadata
                },
                "customer": {
                    "email": customer_email,
                    "phone_number": customer_phone,
                    "name": customer_name
                },
                "customizations": {
                    "title": "Payment for " + (payment_request.description or "Order"),
                    "description": payment_request.description or "Payment",
                    "logo": ""  # Optional logo URL
                }
            }
            
            # Make API request
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/payments",
                    headers=headers,
                    json=payment_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        error_message = result.get("message", "Unknown error")
                        logger.error(f"Flutterwave payment error: {error_message}")
                        
                        # Log failed payment attempt
                        self.log_payment_transaction(
                            tx_ref,
                            {
                                "payment_id": payment_request.payment_id,
                                "amount": payment_request.amount,
                                "currency": payment_request.currency,
                                "error": error_message,
                                "provider_response": result
                            },
                            "failed"
                        )
                        
                        return ProviderResponse(
                            success=False,
                            payment_id=payment_request.payment_id,
                            provider_payment_id=None,
                            redirect_url=None,
                            status=PaymentStatus.FAILED.value,
                            message=f"Failed to initiate payment: {error_message}",
                            raw_response=result
                        )
                    
                    # Extract payment URL and data
                    data = result.get("data", {})
                    payment_link = data.get("link")
                    flw_ref = data.get("flw_ref")
                    transaction_id = data.get("id")
                    
                    if not payment_link:
                        logger.error(f"Flutterwave missing payment link: {result}")
                        return ProviderResponse(
                            success=False,
                            payment_id=payment_request.payment_id,
                            provider_payment_id=None,
                            redirect_url=None,
                            status=PaymentStatus.FAILED.value,
                            message="Invalid response from Flutterwave: missing payment link",
                            raw_response=result
                        )
                    
                    # Log payment transaction
                    self.log_payment_transaction(
                        transaction_id or tx_ref,
                        {
                            "payment_id": payment_request.payment_id,
                            "tx_ref": tx_ref,
                            "flw_ref": flw_ref,
                            "amount": payment_request.amount,
                            "currency": payment_request.currency,
                            "provider_response": result
                        },
                        "initiated"
                    )
                    
                    return ProviderResponse(
                        success=True,
                        payment_id=payment_request.payment_id,
                        provider_payment_id=str(transaction_id) if transaction_id else flw_ref,
                        redirect_url=payment_link,
                        status=PaymentStatus.PENDING.value,
                        message="Payment initiated successfully. Redirect customer to the payment link.",
                        raw_response=result
                    )
        
        except Exception as e:
            logger.error(f"Error processing Flutterwave payment: {str(e)}")
            return ProviderResponse(
                success=False,
                payment_id=payment_request.payment_id,
                provider_payment_id=None,
                redirect_url=None,
                status=PaymentStatus.FAILED.value,
                message=f"Error processing payment: {str(e)}",
                raw_response={"error": str(e)}
            )

    async def verify_payment(self, provider_payment_id: str) -> ProviderResponse:
        """
        Verify a payment status with Flutterwave.
        
        Args:
            provider_payment_id: Flutterwave transaction ID
            
        Returns:
            Provider response with payment status
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            # Check if provider_payment_id is a transaction ID or reference
            is_transaction_id = provider_payment_id.isdigit()
            
            # Determine the appropriate endpoint
            endpoint = f"{self.api_base_url}/transactions/{provider_payment_id}/verify" if is_transaction_id else \
                       f"{self.api_base_url}/transactions/verify_by_reference?tx_ref={provider_payment_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=headers) as response:
                    result = await response.json()
                    
                    # Log verification attempt
                    self.log_payment_transaction(
                        provider_payment_id,
                        {
                            "verification_method": "transaction_id" if is_transaction_id else "tx_ref",
                            "provider_response": result
                        },
                        "verified"
                    )
                    
                    if response.status != 200 or result.get("status") != "success":
                        error_message = result.get("message", "Unknown error")
                        logger.error(f"Flutterwave verification error: {error_message}")
                        return ProviderResponse(
                            success=False,
                            payment_id=None,  # We don't have this information at verification
                            provider_payment_id=provider_payment_id,
                            redirect_url=None,
                            status=PaymentStatus.UNKNOWN.value,
                            message=f"Payment verification failed: {error_message}",
                            raw_response=result
                        )
                    
                    # Extract payment details
                    data = result.get("data", {})
                    status = data.get("status", "").lower()
                    amount = data.get("amount")
                    currency = data.get("currency")
                    payment_id = data.get("meta", {}).get("payment_id")
                    
                    # Map status to internal status
                    if status == "successful":
                        internal_status = PaymentStatus.SUCCESS.value
                        success = True
                    elif status == "failed":
                        internal_status = PaymentStatus.FAILED.value
                        success = False
                    elif status in ["pending", "new"]:
                        internal_status = PaymentStatus.PENDING.value
                        success = False
                    else:
                        internal_status = PaymentStatus.UNKNOWN.value
                        success = False
                    
                    return ProviderResponse(
                        success=success,
                        payment_id=payment_id,
                        provider_payment_id=provider_payment_id,
                        redirect_url=None,
                        status=internal_status,
                        message=f"Payment status: {status}",
                        raw_response=result
                    )
        
        except Exception as e:
            logger.error(f"Error verifying Flutterwave payment: {str(e)}")
            return ProviderResponse(
                success=False,
                payment_id=None,
                provider_payment_id=provider_payment_id,
                redirect_url=None,
                status=PaymentStatus.UNKNOWN.value,
                message=f"Error verifying payment: {str(e)}",
                raw_response={"error": str(e)}
            )

    async def process_refund(self, refund_request: RefundRequest) -> ProviderResponse:
        """
        Process a refund through Flutterwave.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Provider response with refund status
        """
        try:
            transaction_id = refund_request.provider_payment_id
            
            # Prepare refund data
            refund_data = {
                "id": transaction_id,
                "amount": refund_request.amount
            }
            
            # Encrypt any sensitive metadata
            if refund_request.metadata:
                encrypted_metadata = self.encrypt_sensitive_data(refund_request.metadata)
                # Add to log later since Flutterwave API doesn't accept this field
            
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/transactions/{transaction_id}/refund",
                    headers=headers,
                    json=refund_data
                ) as response:
                    result = await response.json()
                    
                    # Log refund attempt
                    refund_metadata = refund_request.metadata or {}
                    if hasattr(refund_request, 'refund_id') and refund_request.refund_id:
                        refund_ref = refund_request.refund_id
                    else:
                        refund_ref = f"refund-{transaction_id}-{int(time.time())}"
                    
                    self.log_refund_transaction(
                        refund_ref,
                        {
                            "transaction_id": transaction_id,
                            "amount": refund_request.amount,
                            "currency": refund_request.currency,
                            "reason": refund_request.reason if hasattr(refund_request, 'reason') else None,
                            "metadata": refund_metadata,
                            "provider_response": result
                        },
                        "processed"
                    )
                    
                    if response.status != 200 or result.get("status") != "success":
                        error_message = result.get("message", "Unknown error")
                        logger.error(f"Flutterwave refund error: {error_message}")
                        return ProviderResponse(
                            success=False,
                            payment_id=refund_request.payment_id if hasattr(refund_request, 'payment_id') else None,
                            provider_payment_id=transaction_id,
                            redirect_url=None,
                            status=RefundStatus.FAILED.value,
                            message=f"Refund failed: {error_message}",
                            raw_response=result
                        )
                    
                    # Extract refund details
                    data = result.get("data", {})
                    refund_id = data.get("id")
                    status = data.get("status", "").lower()
                    
                    # Map status to internal status
                    if status == "completed":
                        internal_status = RefundStatus.SUCCESS.value
                        success = True
                    elif status == "pending":
                        internal_status = RefundStatus.PENDING.value
                        success = True
                    else:
                        internal_status = RefundStatus.FAILED.value
                        success = False
                    
                    return ProviderResponse(
                        success=success,
                        payment_id=refund_request.payment_id if hasattr(refund_request, 'payment_id') else None,
                        provider_payment_id=refund_id or transaction_id,
                        redirect_url=None,
                        status=internal_status,
                        message=f"Refund status: {status}",
                        raw_response=result
                    )
        
        except Exception as e:
            logger.error(f"Error processing Flutterwave refund: {str(e)}")
            return ProviderResponse(
                success=False,
                payment_id=refund_request.payment_id if hasattr(refund_request, 'payment_id') else None,
                provider_payment_id=refund_request.provider_payment_id,
                redirect_url=None,
                status=RefundStatus.FAILED.value,
                message=f"Error processing refund: {str(e)}",
                raw_response={"error": str(e)}
            )

    def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify Flutterwave webhook signature.
        
        Args:
            payload: Raw request body as string or dict
            signature: Signature from HTTP header
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.webhook_secret:
                logger.warning("Flutterwave webhook secret not configured")
                return False
            
            # Convert payload to string if it's a dict
            if isinstance(payload, dict):
                payload_str = json.dumps(payload)
            else:
                payload_str = payload
            
            # Calculate HMAC signature
            computed_signature = hmac.new(
                self.webhook_secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Log webhook verification
            self.log_payment_transaction(
                str(int(time.time())),  # Use timestamp as ID if we don't have a specific one
                {
                    "event_type": "webhook_verification",
                    "signature_valid": hmac.compare_digest(computed_signature, signature),
                    "payload_size": len(payload_str)
                },
                "webhook_received"
            )
            
            # Compare signatures (constant-time comparison to prevent timing attacks)
            return hmac.compare_digest(computed_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying Flutterwave webhook signature: {str(e)}")
            return False

    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Handle webhook data from Flutterwave.
        
        Args:
            payload: Webhook payload
            headers: Webhook headers
            
        Returns:
            Processed webhook data or None if verification failed
        """
        try:
            # Get the signature from headers
            signature = headers.get("verif-hash")
            
            if not signature:
                logger.warning("Missing Flutterwave webhook signature header (verif-hash)")
                return None
            
            # Verify webhook signature
            if not self.verify_webhook_signature(payload, signature):
                logger.warning("Invalid Flutterwave webhook signature")
                return None
            
            # Process event based on type
            event_type = payload.get("event", "")
            data = payload.get("data", {})
            
            # Log webhook processing
            event_id = data.get("id", f"webhook-{int(time.time())}")
            tx_ref = data.get("tx_ref", "unknown")
            
            self.log_payment_transaction(
                event_id,
                {
                    "event_type": event_type,
                    "tx_ref": tx_ref,
                    "processor_response": data.get("processor_response", ""),
                    "amount": data.get("amount"),
                    "currency": data.get("currency")
                },
                "webhook_processed"
            )
            
            if event_type == "charge.completed":
                status = data.get("status", "").lower()
                
                if status == "successful":
                    internal_status = PaymentStatus.SUCCESS.value
                elif status == "failed":
                    internal_status = PaymentStatus.FAILED.value
                else:
                    internal_status = PaymentStatus.PENDING.value
                
                return {
                    "event_type": event_type,
                    "provider_payment_id": str(data.get("id", "")),
                    "tx_ref": tx_ref,
                    "status": internal_status,
                    "amount": data.get("amount"),
                    "currency": data.get("currency"),
                    "customer": data.get("customer", {}),
                    "processed": True,
                    "metadata": data.get("meta", {})
                }
            
            elif event_type == "transfer.completed":
                # Handle wallet transfer events
                status = data.get("status", "").lower()
                
                return {
                    "event_type": event_type,
                    "provider_payment_id": str(data.get("id", "")),
                    "reference": data.get("reference", ""),
                    "status": status,
                    "amount": data.get("amount"),
                    "currency": data.get("currency"),
                    "processed": True,
                    "metadata": data.get("meta", {})
                }
            
            # For other events, just return the event data
            return {
                "event_type": event_type,
                "processed": True,
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Error handling Flutterwave webhook: {str(e)}")
            return None
