"""
PayPal payment provider implementation.

This module provides integration with the PayPal payment service.
"""
import logging
import json
import aiohttp
from typing import Dict, Any, List, Optional, Tuple, Union
import asyncio
from datetime import datetime
import base64
import hmac
import hashlib

from ..models.payment import PaymentStatus, RefundStatus, RefundResponse, PaymentResponse
from ..models.provider import PaymentRequest, RefundRequest
from .base_provider import BasePaymentProvider
from .provider_factory import PaymentProviderFactory

logger = logging.getLogger("kaapi.payment.paypal")

@PaymentProviderFactory.register
class PayPalProvider(BasePaymentProvider):
    """PayPal payment provider implementation."""
    
    provider_id = "paypal"
    provider_name = "PayPal"
    logo_url = "https://www.paypalobjects.com/webstatic/mktg/logo/pp_cc_mark_37x23.jpg"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize a PayPal payment provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        self.client_id = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")
        self.mode = config.get("mode", "sandbox").lower()  # sandbox or live
        
        # Set API base URL based on mode
        if self.mode == "live":
            self.api_base_url = "https://api-m.paypal.com"
        else:
            self.api_base_url = "https://api-m.sandbox.paypal.com"
            
        # Webhook ID for webhook validation
        self.webhook_id = config.get("webhook_id", "")
        
        logger.info(f"PayPal payment provider initialized with mode: {self.mode}")
    
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
        return "PayPal payment services for global payments"
    
    @property
    def supported_methods(self) -> List[str]:
        """Get supported payment methods."""
        return ["card", "paypal", "venmo", "paylater"]
    
    @property
    def supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        return ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY", "MXN", "BRL"]
    
    @property
    def supported_countries(self) -> List[str]:
        """Get supported countries."""
        return ["US", "CA", "MX", "GB", "DE", "FR", "ES", "IT", "JP", "AU", "BR"]
    
    @property
    def supports_subscriptions(self) -> bool:
        """Whether this provider supports subscriptions."""
        return True
    
    async def _get_access_token(self) -> str:
        """
        Get PayPal OAuth access token.
        
        Returns:
            Access token string
        """
        try:
            # Create basic auth header with encrypted credentials
            auth_string = f"{self.client_id}:{self.client_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}oauth2/token",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Basic {encoded_auth}"
                    },
                    data={"grant_type": "client_credentials"}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get PayPal access token: {error_text}")
                        raise ValueError(f"Failed to get PayPal access token: {response.status}")
                    
                    data = await response.json()
                    return data["access_token"]
        except Exception as e:
            logger.error(f"Error getting PayPal access token: {str(e)}")
            raise

    async def process_payment(self, payment_request: PaymentRequest) -> PaymentResponse:
        """
        Process a payment through PayPal.
        
        Args:
            payment_request: Payment request details
            
        Returns:
            Provider response with payment details
        """
        try:
            # Get access token
            access_token = await self._get_access_token()
            
            # Prepare order data
            order_data = self._prepare_order_data(payment_request)
            
            # Validate payment data
            if not self.validate_payment_request(payment_request):
                logger.error("Payment validation failed: Invalid payment data")
                return PaymentResponse(
                    success=False,
                    status=PaymentStatus.FAILED,
                    provider_reference="",
                    message="Payment validation failed: Invalid payment data",
                    raw_response={"error": "validation_failed"}
                )
            
            # Encrypt sensitive metadata before processing
            if payment_request.metadata:
                encrypted_metadata = self.encrypt_sensitive_data(payment_request.metadata)
                # Add encrypted metadata to order data if available
                if order_data.get("purchase_units"):
                    for unit in order_data["purchase_units"]:
                        if not unit.get("custom_id"):
                            unit["custom_id"] = payment_request.payment_id
                        if not unit.get("custom"):
                            unit["custom"] = json.dumps(encrypted_metadata)
            
            # Create order
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/v2/checkout/orders",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {access_token}"
                    },
                    json=order_data
                ) as response:
                    response_data = await response.json()
                    
                    # Log payment attempt
                    payment_log_data = {
                        "amount": payment_request.amount,
                        "currency": payment_request.currency,
                        "payment_id": payment_request.payment_id,
                        "provider_response": response_data
                    }
                    transaction_id = response_data.get("id", payment_request.payment_id)
                    self.log_payment_transaction(
                        transaction_id,
                        payment_log_data,
                        "initiated"
                    )
                    
                    if response.status == 201:
                        # Extract approval URL and ID
                        order_id = response_data.get("id", "")
                        approval_url = next(
                            (link["href"] for link in response_data.get("links", []) 
                             if link.get("rel") == "approve"),
                            None
                        )
                        
                        if not approval_url:
                            logger.error(f"No approval URL found in PayPal response: {response_data}")
                            return PaymentResponse(
                                success=False,
                                status=PaymentStatus.FAILED,
                                provider_reference=order_id,
                                message="No approval URL found in PayPal response",
                                raw_response=response_data
                            )
                        
                        return PaymentResponse(
                            success=True,
                            status=PaymentStatus.PENDING,
                            provider_reference=order_id,
                            redirect_url=approval_url,
                            message="Payment initiated. Redirect customer to approval URL.",
                            raw_response=response_data
                        )
                    else:
                        error_message = response_data.get("message", "Unknown error")
                        logger.error(f"PayPal payment error: {error_message}")
                        return PaymentResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference="",
                            message=f"PayPal payment error: {error_message}",
                            raw_response=response_data
                        )
        except Exception as e:
            logger.error(f"Error processing PayPal payment: {str(e)}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    def _prepare_order_data(self, payment_request: PaymentRequest) -> Dict[str, Any]:
        """
        Prepare PayPal order data from payment request.
        
        Args:
            payment_request: Payment request details
            
        Returns:
            PayPal order data
        """
        # Create basic order data
        order_data = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": payment_request.currency,
                        "value": str(payment_request.amount)
                    },
                    "description": payment_request.description or "Payment"
                }
            ],
            "application_context": {
                "return_url": payment_request.success_url or "",
                "cancel_url": payment_request.cancel_url or ""
            }
        }
        
        # Add reference ID (payment ID)
        if payment_request.payment_id:
            order_data["purchase_units"][0]["reference_id"] = payment_request.payment_id
        
        # Add customer data if available
        if payment_request.customer_email:
            if "payer" not in order_data:
                order_data["payer"] = {}
            order_data["payer"]["email_address"] = payment_request.customer_email
        
        if payment_request.customer_name:
            if "payer" not in order_data:
                order_data["payer"] = {}
            name_parts = payment_request.customer_name.split(" ", 1)
            order_data["payer"]["name"] = {
                "given_name": name_parts[0],
                "surname": name_parts[1] if len(name_parts) > 1 else ""
            }
        
        return order_data
    
    async def verify_payment(self, reference: str) -> PaymentResponse:
        """
        Verify a payment status with PayPal.
        
        Args:
            reference: PayPal order ID
            
        Returns:
            Payment response with status
        """
        try:
            # Get access token
            access_token = await self._get_access_token()
            
            # Get order details
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/v2/checkout/orders/{reference}",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {access_token}"
                    }
                ) as response:
                    response_data = await response.json()
                    
                    if response.status != 200:
                        error_message = response_data.get("message", "Unknown error")
                        logger.error(f"PayPal verification error: {error_message}")
                        return PaymentResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference=reference,
                            message=f"PayPal verification error: {error_message}",
                            raw_response=response_data
                        )
                    
                    # Extract status
                    order_status = response_data.get("status", "")
                    
                    # Log verification
                    verification_log_data = {
                        "order_id": reference,
                        "status": order_status,
                        "provider_response": response_data
                    }
                    self.log_payment_transaction(
                        reference,
                        verification_log_data,
                        "verified"
                    )
                    
                    # Map PayPal status to internal status
                    if order_status == "COMPLETED":
                        return PaymentResponse(
                            success=True,
                            status=PaymentStatus.SUCCESS,
                            provider_reference=reference,
                            message="Payment completed",
                            raw_response=response_data
                        )
                    elif order_status == "APPROVED":
                        return PaymentResponse(
                            success=True,
                            status=PaymentStatus.PENDING,
                            provider_reference=reference,
                            message="Payment approved but not yet captured",
                            raw_response=response_data
                        )
                    elif order_status == "CREATED":
                        return PaymentResponse(
                            success=False,
                            status=PaymentStatus.PENDING,
                            provider_reference=reference,
                            message="Payment created but not yet approved",
                            raw_response=response_data
                        )
                    elif order_status == "SAVED":
                        return PaymentResponse(
                            success=False,
                            status=PaymentStatus.PENDING,
                            provider_reference=reference,
                            message="Payment saved but not yet approved",
                            raw_response=response_data
                        )
                    elif order_status == "VOIDED" or order_status == "PAYER_ACTION_REQUIRED":
                        return PaymentResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference=reference,
                            message=f"Payment {order_status.lower()}",
                            raw_response=response_data
                        )
                    else:
                        return PaymentResponse(
                            success=False,
                            status=PaymentStatus.UNKNOWN,
                            provider_reference=reference,
                            message=f"Unknown payment status: {order_status}",
                            raw_response=response_data
                        )
        except Exception as e:
            logger.error(f"Error verifying PayPal payment: {str(e)}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.UNKNOWN,
                provider_reference=reference,
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def capture_payment(self, reference: str) -> PaymentResponse:
        """
        Capture an approved PayPal payment.
        
        Args:
            reference: PayPal order ID
            
        Returns:
            Payment response with capture status
        """
        try:
            # Get access token
            access_token = await self._get_access_token()
            
            # Capture the payment
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/v2/checkout/orders/{reference}/capture",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {access_token}"
                    }
                ) as response:
                    response_data = await response.json()
                    
                    if response.status != 201:
                        error_message = response_data.get("message", "Unknown error")
                        logger.error(f"PayPal capture error: {error_message}")
                        return PaymentResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference=reference,
                            message=f"PayPal capture error: {error_message}",
                            raw_response=response_data
                        )
                    
                    # Extract capture ID
                    capture_id = None
                    if response_data.get("purchase_units"):
                        for unit in response_data["purchase_units"]:
                            if unit.get("payments", {}).get("captures"):
                                for capture in unit["payments"]["captures"]:
                                    capture_id = capture.get("id")
                                    break
                    
                    # Log capture
                    capture_log_data = {
                        "order_id": reference,
                        "capture_id": capture_id,
                        "status": response_data.get("status"),
                        "provider_response": response_data
                    }
                    self.log_payment_transaction(
                        reference,
                        capture_log_data,
                        "captured"
                    )
                    
                    return PaymentResponse(
                        success=True,
                        status=PaymentStatus.SUCCESS,
                        provider_reference=reference,
                        message="Payment captured successfully",
                        raw_response=response_data
                    )
        except Exception as e:
            logger.error(f"Error capturing PayPal payment: {str(e)}")
            return PaymentResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference=reference,
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def process_refund(self, refund_request: RefundRequest) -> RefundResponse:
        """
        Process a refund through PayPal.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Refund response
        """
        try:
            # Get access token
            access_token = await self._get_access_token()
            
            # First check if the reference is an order ID or capture ID
            # For PayPal, we need the capture ID to process a refund
            capture_id = None
            
            if refund_request.payment_reference.startswith("EC-"):  # This is an order ID
                # Get order details to find capture ID
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.api_base_url}/v2/checkout/orders/{refund_request.payment_reference}",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {access_token}"
                        }
                    ) as response:
                        order_data = await response.json()
                        
                        if response.status != 200:
                            error_message = order_data.get("message", "Unknown error")
                            logger.error(f"PayPal order retrieval error: {error_message}")
                            return RefundResponse(
                                success=False,
                                status=RefundStatus.FAILED,
                                provider_reference="",
                                message=f"PayPal order retrieval error: {error_message}",
                                raw_response=order_data
                            )
                        
                        # Extract capture ID from order
                        if order_data.get("purchase_units"):
                            for unit in order_data["purchase_units"]:
                                if unit.get("payments", {}).get("captures"):
                                    for capture in unit["payments"]["captures"]:
                                        capture_id = capture.get("id")
                                        break
            else:
                # Assume the reference is already a capture ID
                capture_id = refund_request.payment_reference
            
            if not capture_id:
                logger.error(f"No capture ID found for refund: {refund_request.payment_reference}")
                return RefundResponse(
                    success=False,
                    status=RefundStatus.FAILED,
                    provider_reference="",
                    message="No capture ID found for refund",
                    raw_response={"error": "no_capture_id"}
                )
            
            # Prepare refund data
            refund_data = {}
            if refund_request.amount:
                # This is a partial refund
                refund_data["amount"] = {
                    "value": str(refund_request.amount),
                    "currency_code": refund_request.currency
                }
            
            # Add note to seller if reason is provided
            if refund_request.reason:
                refund_data["note_to_payer"] = refund_request.reason[:255]  # PayPal limits this to 255 chars
            
            # Encrypt any sensitive refund data if needed
            if refund_request.metadata:
                encrypted_metadata = self.encrypt_sensitive_data(refund_request.metadata)
                # We can't directly add this to refund data as PayPal doesn't support custom fields in refunds
                # But we log it for record-keeping
                logger.info(f"Encrypted refund metadata for reference: {refund_request.refund_id}")
            
            # Process the refund
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/v2/payments/captures/{capture_id}/refund",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {access_token}"
                    },
                    json=refund_data
                ) as response:
                    response_data = await response.json()
                    
                    # Log refund attempt
                    refund_log_data = {
                        "refund_id": refund_request.refund_id,
                        "capture_id": capture_id,
                        "amount": refund_request.amount,
                        "currency": refund_request.currency,
                        "reason": refund_request.reason,
                        "provider_response": response_data
                    }
                    transaction_id = response_data.get("id", refund_request.refund_id)
                    self.log_refund_transaction(
                        transaction_id,
                        refund_log_data,
                        "processed"
                    )
                    
                    if response.status != 201:
                        error_message = response_data.get("message", "Unknown error")
                        logger.error(f"PayPal refund error: {error_message}")
                        return RefundResponse(
                            success=False,
                            status=RefundStatus.FAILED,
                            provider_reference="",
                            message=f"PayPal refund error: {error_message}",
                            raw_response=response_data
                        )
                    
                    # Extract refund ID and status
                    refund_id = response_data.get("id", "")
                    refund_status = response_data.get("status", "")
                    
                    # Map PayPal refund status to internal status
                    if refund_status == "COMPLETED":
                        return RefundResponse(
                            success=True,
                            status=RefundStatus.SUCCESS,
                            provider_reference=refund_id,
                            message="Refund completed",
                            raw_response=response_data
                        )
                    elif refund_status == "PENDING":
                        return RefundResponse(
                            success=True,
                            status=RefundStatus.PENDING,
                            provider_reference=refund_id,
                            message="Refund pending",
                            raw_response=response_data
                        )
                    else:
                        return RefundResponse(
                            success=False,
                            status=RefundStatus.FAILED,
                            provider_reference=refund_id,
                            message=f"Refund status: {refund_status}",
                            raw_response=response_data
                        )
        except Exception as e:
            logger.error(f"Error processing PayPal refund: {str(e)}")
            return RefundResponse(
                success=False,
                status=RefundStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    def verify_webhook_signature(self, event_body: str, headers: Dict[str, str]) -> bool:
        """
        Verify PayPal webhook signature.
        
        Args:
            event_body: Raw request body as string
            headers: HTTP headers from the webhook request
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.webhook_id:
                logger.warning("PayPal webhook ID not configured")
                return False
            
            # Extract required headers
            transmission_id = headers.get("paypal-transmission-id")
            timestamp = headers.get("paypal-transmission-time")
            actual_sig = headers.get("paypal-transmission-sig")
            cert_url = headers.get("paypal-cert-url")
            
            if not all([transmission_id, timestamp, actual_sig, cert_url]):
                logger.warning("Missing required PayPal webhook headers")
                return False
            
            # Construct the validation message
            validation_message = f"{transmission_id}|{timestamp}|{self.webhook_id}|{event_body}"
            
            # We should validate against PayPal's certificate, but for simplicity
            # we'll just use a shared secret verification approach here
            # In a production system, you would verify using PayPal's certificate
            
            # For this example, we'll use the client secret as the key
            expected_sig = hmac.new(
                self.client_secret.encode(),
                validation_message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Log webhook verification
            webhook_log_data = {
                "transmission_id": transmission_id,
                "timestamp": timestamp,
                "body_length": len(event_body),
                "signature_valid": hmac.compare_digest(actual_sig, expected_sig)
            }
            self.log_payment_transaction(
                transmission_id,
                webhook_log_data,
                "webhook_received"
            )
            
            # Compare signatures (constant-time comparison to prevent timing attacks)
            return hmac.compare_digest(actual_sig, expected_sig)
            
        except Exception as e:
            logger.error(f"Error verifying PayPal webhook signature: {str(e)}")
            return False
    
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Handle PayPal webhook events.
        
        Args:
            payload: Webhook payload
            headers: HTTP headers
            
        Returns:
            Processed event data or None if signature validation fails
        """
        try:
            # Verify webhook signature
            is_valid = self.verify_webhook_signature(
                json.dumps(payload),
                headers
            )
            
            if not is_valid:
                logger.warning("Invalid PayPal webhook signature")
                return None
            
            # Process event based on type
            event_type = payload.get("event_type", "")
            resource = payload.get("resource", {})
            
            # Log webhook processing
            webhook_log_data = {
                "event_type": event_type,
                "resource_id": resource.get("id"),
                "resource_type": payload.get("resource_type")
            }
            event_id = payload.get("id", "unknown")
            self.log_payment_transaction(
                event_id,
                webhook_log_data,
                "webhook_processed"
            )
            
            if event_type == "PAYMENT.CAPTURE.COMPLETED":
                # Payment completed
                return {
                    "event_type": event_type,
                    "provider_reference": resource.get("id"),
                    "status": PaymentStatus.SUCCESS,
                    "processed": True,
                    "data": resource
                }
                
            elif event_type == "PAYMENT.CAPTURE.DENIED" or event_type == "PAYMENT.CAPTURE.DECLINED":
                # Payment failed
                return {
                    "event_type": event_type,
                    "provider_reference": resource.get("id"),
                    "status": PaymentStatus.FAILED,
                    "processed": True,
                    "data": resource
                }
                
            elif event_type == "PAYMENT.CAPTURE.PENDING":
                # Payment pending
                return {
                    "event_type": event_type,
                    "provider_reference": resource.get("id"),
                    "status": PaymentStatus.PENDING,
                    "processed": True,
                    "data": resource
                }
                
            elif event_type.startswith("PAYMENT.CAPTURE.REFUNDED"):
                # Refund completed
                return {
                    "event_type": event_type,
                    "provider_reference": resource.get("id"),
                    "status": RefundStatus.SUCCESS,
                    "processed": True,
                    "data": resource
                }
                
            # For other events, just return the event data
            return {
                "event_type": event_type,
                "processed": True,
                "data": resource
            }
            
        except Exception as e:
            logger.error(f"Error handling PayPal webhook: {str(e)}")
            return None
