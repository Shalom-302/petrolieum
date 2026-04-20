"""
Wave payment provider implementation.

This module provides integration with the Wave Mobile Money payment service.
"""
import logging
import json
import aiohttp
import hmac
import hashlib
import base64
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..models.provider import PaymentProviderConfig, PaymentRequest, ProviderResponse, RefundRequest
from ..models.payment import PaymentStatus, RefundStatus, RefundResponse
from ..models.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
    SubscriptionCancelRequest,
    SubscriptionStatus
)
from .base_provider import BasePaymentProvider
from .provider_factory import PaymentProviderFactory

logger = logging.getLogger("kaapi.payment.wave")

@PaymentProviderFactory.register
class WaveProvider(BasePaymentProvider):
    """Wave Mobile Money payment provider implementation."""
    
    provider_id = "wave"
    provider_name = "Wave Mobile Money"
    logo_url = "https://wave.com/assets/images/wave-logo.svg"
    
    def __init__(self, config: PaymentProviderConfig):
        """Initialize the provider with configuration."""
        super().__init__(config)
        
        # Set API URLs and configuration
        self.api_base_url = config.get("api_base_url", "https://api.wave.com")
        self.payment_success_url = config.get("success_url") 
        self.payment_cancel_url = config.get("cancel_url")
        
        # Securely store credentials
        self._store_credentials(config)
        
        # Store provider metadata
        self.metadata = {
            "website": "https://wave.com/",
            "docs": "https://developer.wave.com/"
        }
        
        logger.info(f"Wave payment provider initialized")
    
    def _store_credentials(self, config: PaymentProviderConfig) -> None:
        """
        Securely store provider credentials.
        
        Args:
            config: Provider configuration
        """
        credentials = {
            "api_key": config.get("secret_key"),
            "api_client_id": config.get("public_key"),
            "webhook_secret": config.get("webhook_secret")
        }
        
        # Use the security module to store credentials
        self.security.store_provider_credentials(self.provider_id, credentials)
    
    def _get_credentials(self) -> Dict[str, str]:
        """
        Retrieve the stored credentials.
        
        Returns:
            Dictionary with credential key-value pairs
        """
        credentials = self.security.get_provider_credentials(self.provider_id)
        return credentials
        
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
        return "Wave Mobile Money payment service for West Africa"
    
    @property
    def supported_methods(self) -> List[str]:
        """Get supported payment methods."""
        return ["mobile_money", "qr_code"]
    
    @property
    def supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        return ["XOF", "USD", "EUR", "GHS", "GNF", "CFA"]
    
    @property
    def supported_countries(self) -> List[str]:
        """Get supported countries."""
        return ["SN", "CI", "ML", "BJ", "TG", "GH", "GN"]
    
    @property
    def supports_subscriptions(self) -> bool:
        """Whether this provider supports subscriptions."""
        return True

    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through Wave Mobile Money.
        
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
                    provider_id=self.provider_id,
                    payment_id=payment_request.payment_id,
                    status=PaymentStatus.FAILED.value,
                    message="Payment validation failed: Invalid payment data"
                )
            
            amount = payment_request.amount
            currency = payment_request.currency.upper()
            description = payment_request.description
            customer_email = payment_request.customer_email
            phone_number = payment_request.metadata.get("phone_number", "")
            
            if not phone_number:
                logger.error("Phone number is required for Wave payments")
                return ProviderResponse(
                    provider_id=self.provider_id,
                    payment_id=payment_request.payment_id,
                    status=PaymentStatus.FAILED.value,
                    message="Phone number is required for Wave payments"
                )
                
            # Format amount with correct decimals based on currency
            # Wave requires amount in the smallest currency unit (e.g., cents for USD)
            amount_in_cents = int(amount * 100)
            
            # Get API credentials securely
            credentials = self._get_credentials()
            
            headers = {
                "Authorization": f"Bearer {credentials.get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # Encrypt sensitive metadata
            encrypted_metadata = {}
            if payment_request.metadata:
                encrypted_metadata = self.encrypt_sensitive_data(payment_request.metadata)
            
            payload = {
                "amount": amount_in_cents,
                "currency": currency,
                "description": description,
                "customer": {
                    "email": customer_email,
                    "phone": phone_number
                },
                "return_url": self.payment_success_url,
                "cancel_url": self.payment_cancel_url,
                "reference": payment_request.payment_id,
                "metadata": {
                    "payment_id": payment_request.payment_id,
                    "customer_id": payment_request.customer_id,
                    "encrypted_data": encrypted_metadata,
                    "source": "kaapi"
                }
            }
            
            # Log the payment request attempt
            payment_log_data = {
                "payment_id": payment_request.payment_id,
                "amount": amount,
                "currency": currency,
                "customer_email": customer_email,
                "description": description,
                "payment_method": "mobile_money"
            }
            
            self.log_payment_transaction(
                payment_request.payment_id,
                payment_log_data,
                "initiated"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}payments",
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    # Update payment log with response
                    payment_log_data["provider_response"] = result
                    
                    if response.status != 200 or result.get("status") != "success":
                        error_message = result.get('message', 'Unknown error')
                        logger.error(f"Wave payment error: {error_message}")
                        
                        # Log failure
                        self.log_payment_transaction(
                            payment_request.payment_id,
                            payment_log_data,
                            "failed"
                        )
                        
                        return ProviderResponse(
                            provider_id=self.provider_id,
                            payment_id=payment_request.payment_id,
                            status=PaymentStatus.FAILED.value,
                            message=f"Failed to process payment: {error_message}"
                        )
                    
                    payment_data = result.get("data", {})
                    
                    # Log successful payment initiation
                    payment_log_data["checkout_url"] = payment_data.get("checkout_url")
                    payment_log_data["provider_payment_id"] = payment_data.get("id")
                    
                    self.log_payment_transaction(
                        payment_request.payment_id,
                        payment_log_data,
                        "pending"
                    )
                    
                    return ProviderResponse(
                        provider_id=self.provider_id,
                        payment_id=payment_request.payment_id,
                        provider_payment_id=payment_data.get("id"),
                        amount=amount,
                        currency=currency,
                        status=PaymentStatus.PENDING.value,
                        redirect_url=payment_data.get("checkout_url"),
                        details={
                            "payment_link": payment_data.get("checkout_url"),
                            "reference": payment_data.get("reference"),
                            "checkout_id": payment_data.get("id"),
                            "expires_at": payment_data.get("expires_at")
                        }
                    )
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"Wave payment error: {error_message}")
            
            # Log exception
            if payment_request and hasattr(payment_request, 'payment_id'):
                self.log_payment_transaction(
                    payment_request.payment_id,
                    {"error": error_message},
                    "error"
                )
            
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=payment_request.payment_id if payment_request and hasattr(payment_request, 'payment_id') else None,
                status=PaymentStatus.FAILED.value,
                message=f"Error processing payment: {error_message}"
            )
    
    async def verify_payment(self, payment_id: str) -> ProviderResponse:
        """
        Verify a payment with Wave.
        
        Args:
            payment_id: Wave payment ID
            
        Returns:
            Provider response with payment details
        """
        try:
            # Get API credentials securely
            credentials = self._get_credentials()
            
            headers = {
                "Authorization": f"Bearer {credentials.get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # Log verification attempt
            verification_log_data = {
                "provider_payment_id": payment_id,
                "verification_time": datetime.now().isoformat()
            }
            
            self.log_payment_transaction(
                payment_id,
                verification_log_data,
                "verification_initiated"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}payments/{payment_id}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    # Update verification log with response
                    verification_log_data["provider_response"] = result
                    
                    if response.status != 200 or result.get("status") != "success":
                        error_message = result.get('message', 'Unknown error')
                        logger.error(f"Wave payment verification error: {error_message}")
                        
                        # Log verification failure
                        self.log_payment_transaction(
                            payment_id,
                            verification_log_data,
                            "verification_failed"
                        )
                        
                        return ProviderResponse(
                            provider_id=self.provider_id,
                            provider_payment_id=payment_id,
                            status=PaymentStatus.UNKNOWN.value,
                            message=f"Failed to verify payment: {error_message}"
                        )
                    
                    payment_data = result.get("data", {})
                    
                    # Extract payment details from metadata
                    metadata = payment_data.get("metadata", {})
                    app_payment_id = metadata.get("payment_id")
                    
                    # Map Wave payment status to internal status
                    wave_status = payment_data.get("status", "").lower()
                    if wave_status == "successful" or wave_status == "success":
                        status = PaymentStatus.SUCCESSFUL.value
                        log_status = "completed"
                    elif wave_status == "pending":
                        status = PaymentStatus.PENDING.value
                        log_status = "pending"
                    elif wave_status == "failed":
                        status = PaymentStatus.FAILED.value
                        log_status = "failed"
                    elif wave_status == "cancelled" or wave_status == "canceled":
                        status = PaymentStatus.CANCELED.value
                        log_status = "canceled"
                    else:
                        status = PaymentStatus.UNKNOWN.value
                        log_status = "unknown"
                    
                    amount = payment_data.get("amount", 0) / 100  # Convert from cents to base unit
                    
                    # Log verification result
                    verification_log_data["status"] = status
                    verification_log_data["amount"] = amount
                    verification_log_data["currency"] = payment_data.get("currency")
                    
                    self.log_payment_transaction(
                        app_payment_id or payment_id,
                        verification_log_data,
                        log_status
                    )
                    
                    return ProviderResponse(
                        provider_id=self.provider_id,
                        payment_id=app_payment_id,
                        provider_payment_id=payment_id,
                        amount=amount,
                        currency=payment_data.get("currency"),
                        status=status,
                        transaction_id=payment_data.get("transaction_id"),
                        details={
                            "payment_method": payment_data.get("payment_method", "mobile_money"),
                            "customer_email": payment_data.get("customer", {}).get("email"),
                            "customer_phone": payment_data.get("customer", {}).get("phone"),
                            "reference": payment_data.get("reference"),
                            "payment_date": payment_data.get("created_at"),
                            "metadata": payment_data.get("metadata", {})
                        }
                    )
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"Wave payment verification error: {error_message}")
            
            # Log exception during verification
            self.log_payment_transaction(
                payment_id,
                {"error": error_message},
                "verification_error"
            )
            
            return ProviderResponse(
                provider_id=self.provider_id,
                provider_payment_id=payment_id,
                status=PaymentStatus.UNKNOWN.value,
                message=f"Error verifying payment: {error_message}"
            )
    
    async def cancel_payment(self, payment_id: str) -> ProviderResponse:
        """
        Cancel a payment with Wave.
        
        Args:
            payment_id: Wave payment ID
            
        Returns:
            Provider response with payment details
        """
        try:
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}payments/{payment_id}/cancel",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        logger.error(f"Wave payment cancellation error: {result}")
                        raise ValueError(f"Failed to cancel payment: {result.get('message', 'Unknown error')}")
                    
                    payment_data = result.get("data", {})
                    
                    amount = payment_data.get("amount", 0) / 100  # Convert from cents to base unit
                    
                    return ProviderResponse(
                        provider_id=self.provider_id,
                        payment_id=payment_id,
                        amount=amount,
                        currency=payment_data.get("currency"),
                        status=PaymentStatus.CANCELED.value,
                        transaction_id=payment_data.get("transaction_id"),
                        details={
                            "canceled_at": payment_data.get("canceled_at"),
                            "reason": payment_data.get("cancel_reason", "Canceled by merchant")
                        }
                    )
        
        except Exception as e:
            logger.error(f"Wave payment cancellation error: {str(e)}")
            raise ValueError(f"Failed to cancel payment: {str(e)}")

    async def process_refund(self, refund_request: RefundRequest) -> RefundResponse:
        """
        Process a refund through Wave.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Refund response with details
        """
        try:
            payment_id = refund_request.payment_id
            amount = refund_request.amount
            reason = refund_request.reason
            
            # Format amount with correct decimals
            # Wave requires amount in the smallest currency unit (e.g., cents for USD)
            amount_in_cents = int(amount * 100)
            
            # Get API credentials securely
            credentials = self._get_credentials()
            
            # Encrypt sensitive metadata if available
            encrypted_metadata = {}
            if hasattr(refund_request, 'metadata') and refund_request.metadata:
                encrypted_metadata = self.encrypt_sensitive_data(refund_request.metadata)
            
            headers = {
                "Authorization": f"Bearer {credentials.get('api_key')}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "amount": amount_in_cents,
                "reason": reason,
                "metadata": {
                    "refund_id": refund_request.refund_id,
                    "encrypted_data": encrypted_metadata,
                    "source": "kaapi"
                }
            }
            
            # Log refund initiation
            refund_log_data = {
                "refund_id": refund_request.refund_id,
                "payment_id": payment_id,
                "amount": amount,
                "reason": reason
            }
            
            self.log_refund_transaction(
                refund_request.refund_id,
                refund_log_data,
                "initiated"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}payments/{payment_id}/refunds",
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    # Update refund log with response
                    refund_log_data["provider_response"] = result
                    
                    if response.status != 200 or result.get("status") != "success":
                        error_message = result.get('message', 'Unknown error')
                        logger.error(f"Wave refund error: {error_message}")
                        
                        # Log failure
                        self.log_refund_transaction(
                            refund_request.refund_id,
                            refund_log_data,
                            "failed"
                        )
                        
                        return RefundResponse(
                            provider_id=self.provider_id,
                            refund_id=refund_request.refund_id,
                            payment_id=payment_id,
                            status=RefundStatus.FAILED.value,
                            message=f"Failed to process refund: {error_message}"
                        )
                    
                    refund_data = result.get("data", {})
                    
                    # Log successful refund initiation
                    refund_log_data["provider_refund_id"] = refund_data.get("id")
                    self.log_refund_transaction(
                        refund_request.refund_id,
                        refund_log_data,
                        "pending"
                    )
                    
                    return RefundResponse(
                        provider_id=self.provider_id,
                        refund_id=refund_data.get("id"),
                        payment_id=payment_id,
                        amount=amount,
                        currency=refund_data.get("currency"),
                        status=RefundStatus.PENDING.value,
                        details={
                            "created_at": refund_data.get("created_at"),
                            "reason": reason,
                            "transaction_id": refund_data.get("transaction_id")
                        }
                    )
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"Wave refund error: {error_message}")
            
            # Log exception
            if refund_request and hasattr(refund_request, 'refund_id'):
                self.log_refund_transaction(
                    refund_request.refund_id,
                    {"error": error_message, "payment_id": getattr(refund_request, 'payment_id', None)},
                    "error"
                )
            
            return RefundResponse(
                provider_id=self.provider_id,
                refund_id=getattr(refund_request, 'refund_id', None),
                payment_id=getattr(refund_request, 'payment_id', None),
                status=RefundStatus.FAILED.value,
                message=f"Error processing refund: {error_message}"
            )
            
    async def verify_refund(self, refund_id: str) -> RefundResponse:
        """
        Verify a refund with Wave.
        
        Args:
            refund_id: Wave refund ID
            
        Returns:
            Refund response with details
        """
        try:
            # Get API credentials securely
            credentials = self._get_credentials()
            
            headers = {
                "Authorization": f"Bearer {credentials.get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # Log verification attempt
            verification_log_data = {
                "refund_id": refund_id,
                "verification_time": datetime.now().isoformat()
            }
            
            self.log_refund_transaction(
                refund_id,
                verification_log_data,
                "verification_initiated"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}refunds/{refund_id}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    # Update verification log with response
                    verification_log_data["provider_response"] = result
                    
                    if response.status != 200 or result.get("status") != "success":
                        error_message = result.get('message', 'Unknown error')
                        logger.error(f"Wave refund verification error: {error_message}")
                        
                        # Log verification failure
                        self.log_refund_transaction(
                            refund_id,
                            verification_log_data,
                            "verification_failed"
                        )
                        
                        return RefundResponse(
                            provider_id=self.provider_id,
                            refund_id=refund_id,
                            status=RefundStatus.UNKNOWN.value,
                            message=f"Failed to verify refund: {error_message}"
                        )
                    
                    refund_data = result.get("data", {})
                    
                    # Map Wave refund status to internal status
                    wave_status = refund_data.get("status", "").lower()
                    if wave_status == "successful" or wave_status == "success":
                        status = RefundStatus.SUCCESSFUL.value
                        log_status = "completed"
                    elif wave_status == "pending":
                        status = RefundStatus.PENDING.value
                        log_status = "pending"
                    elif wave_status == "failed":
                        status = RefundStatus.FAILED.value
                        log_status = "failed"
                    else:
                        status = RefundStatus.UNKNOWN.value
                        log_status = "unknown"
                    
                    amount = refund_data.get("amount", 0) / 100  # Convert from cents to base unit
                    
                    # Extract app-specific refund ID from metadata if available
                    metadata = refund_data.get("metadata", {})
                    app_refund_id = metadata.get("refund_id")
                    
                    # Log verification result
                    verification_log_data["status"] = status
                    verification_log_data["amount"] = amount
                    verification_log_data["currency"] = refund_data.get("currency")
                    
                    self.log_refund_transaction(
                        app_refund_id or refund_id,
                        verification_log_data,
                        log_status
                    )
                    
                    return RefundResponse(
                        provider_id=self.provider_id,
                        refund_id=refund_id,
                        app_refund_id=app_refund_id,
                        payment_id=refund_data.get("payment_id"),
                        amount=amount,
                        currency=refund_data.get("currency"),
                        status=status,
                        details={
                            "created_at": refund_data.get("created_at"),
                            "processed_at": refund_data.get("processed_at"),
                            "reason": refund_data.get("reason"),
                            "transaction_id": refund_data.get("transaction_id")
                        }
                    )
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"Wave refund verification error: {error_message}")
            
            # Log exception during verification
            self.log_refund_transaction(
                refund_id,
                {"error": error_message},
                "verification_error"
            )
            
            return RefundResponse(
                provider_id=self.provider_id,
                refund_id=refund_id,
                status=RefundStatus.UNKNOWN.value,
                message=f"Error verifying refund: {error_message}"
            )
    
    async def handle_webhook(self, payload: Dict[str, Any], signature: str) -> Dict[str, Any]:
        """
        Handle a webhook notification from Wave.
        
        Args:
            payload: Webhook payload
            signature: Webhook signature
            
        Returns:
            Dictionary with processed webhook result
        """
        try:
            # Log webhook receipt
            webhook_log_data = {
                "event_type": payload.get("event", "unknown"),
                "webhook_time": datetime.now().isoformat(),
                "payload_size": len(json.dumps(payload)) if payload else 0
            }
            
            webhook_id = str(int(time.time()))  # Use current timestamp as ID
            
            self.log_payment_transaction(
                webhook_id,
                webhook_log_data,
                "webhook_received"
            )
            
            # Verify the webhook signature
            is_valid = self.verify_webhook_signature(payload, signature)
            if not is_valid:
                logger.error("Invalid Wave webhook signature")
                
                # Log invalid signature
                webhook_log_data["signature_valid"] = False
                self.log_payment_transaction(
                    webhook_id,
                    webhook_log_data,
                    "webhook_invalid_signature"
                )
                
                return {
                    "status": "error",
                    "message": "Invalid webhook signature"
                }
            
            # Log valid signature
            webhook_log_data["signature_valid"] = True
            
            event_type = payload.get("event", "")
            event_data = payload.get("data", {})
            
            # Handle different webhook events
            if "payment.success" in event_type:
                # Payment successful webhook
                payment_id = event_data.get("id")
                metadata = event_data.get("metadata", {})
                app_payment_id = metadata.get("payment_id")
                
                # Log webhook processing
                webhook_log_data["provider_payment_id"] = payment_id
                webhook_log_data["app_payment_id"] = app_payment_id
                webhook_log_data["status"] = PaymentStatus.SUCCESSFUL.value
                
                self.log_payment_transaction(
                    app_payment_id or payment_id,
                    webhook_log_data,
                    "webhook_processed_payment_success"
                )
                
                return {
                    "event": "payment.success",
                    "payment_id": app_payment_id,
                    "provider_payment_id": payment_id,
                    "status": PaymentStatus.SUCCESSFUL.value,
                    "amount": event_data.get("amount", 0) / 100,  # Convert from cents
                    "currency": event_data.get("currency"),
                    "transaction_id": event_data.get("transaction_id"),
                    "metadata": metadata
                }
                
            elif "payment.failed" in event_type:
                # Payment failed webhook
                payment_id = event_data.get("id")
                metadata = event_data.get("metadata", {})
                app_payment_id = metadata.get("payment_id")
                
                # Log webhook processing
                webhook_log_data["provider_payment_id"] = payment_id
                webhook_log_data["app_payment_id"] = app_payment_id
                webhook_log_data["status"] = PaymentStatus.FAILED.value
                webhook_log_data["failure_reason"] = event_data.get("failure_reason")
                
                self.log_payment_transaction(
                    app_payment_id or payment_id,
                    webhook_log_data,
                    "webhook_processed_payment_failed"
                )
                
                return {
                    "event": "payment.failed",
                    "payment_id": app_payment_id,
                    "provider_payment_id": payment_id,
                    "status": PaymentStatus.FAILED.value,
                    "reason": event_data.get("failure_reason"),
                    "metadata": metadata
                }
                
            elif "refund.success" in event_type:
                # Refund successful webhook
                refund_id = event_data.get("id")
                metadata = event_data.get("metadata", {})
                app_refund_id = metadata.get("refund_id")
                
                # Log webhook processing
                webhook_log_data["provider_refund_id"] = refund_id
                webhook_log_data["app_refund_id"] = app_refund_id
                webhook_log_data["status"] = RefundStatus.SUCCESSFUL.value
                
                self.log_refund_transaction(
                    app_refund_id or refund_id,
                    webhook_log_data,
                    "webhook_processed_refund_success"
                )
                
                return {
                    "event": "refund.success",
                    "refund_id": app_refund_id,
                    "provider_refund_id": refund_id,
                    "payment_id": event_data.get("payment_id"),
                    "status": RefundStatus.SUCCESSFUL.value,
                    "amount": event_data.get("amount", 0) / 100,  # Convert from cents
                    "currency": event_data.get("currency"),
                    "metadata": metadata
                }
                
            elif "refund.failed" in event_type:
                # Refund failed webhook
                refund_id = event_data.get("id")
                metadata = event_data.get("metadata", {})
                app_refund_id = metadata.get("refund_id")
                
                # Log webhook processing
                webhook_log_data["provider_refund_id"] = refund_id
                webhook_log_data["app_refund_id"] = app_refund_id
                webhook_log_data["status"] = RefundStatus.FAILED.value
                webhook_log_data["failure_reason"] = event_data.get("failure_reason")
                
                self.log_refund_transaction(
                    app_refund_id or refund_id,
                    webhook_log_data,
                    "webhook_processed_refund_failed"
                )
                
                return {
                    "event": "refund.failed",
                    "refund_id": app_refund_id,
                    "provider_refund_id": refund_id,
                    "payment_id": event_data.get("payment_id"),
                    "status": RefundStatus.FAILED.value,
                    "reason": event_data.get("failure_reason"),
                    "metadata": metadata
                }
            
            # Log unsupported event
            webhook_log_data["status"] = "ignored"
            self.log_payment_transaction(
                webhook_id,
                webhook_log_data,
                "webhook_ignored"
            )
            
            # Return empty dict for unsupported events
            return {"event": event_type, "status": "ignored"}
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Wave webhook error: {error_message}")
            
            # Log exception
            self.log_payment_transaction(
                str(int(time.time())),
                {"error": error_message, "payload": payload},
                "webhook_error"
            )
            
            return {
                "status": "error",
                "message": f"Failed to process webhook: {error_message}"
            }
    
    def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify the webhook signature from Wave.
        
        Args:
            payload: Webhook payload
            signature: Webhook signature
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            credentials = self._get_credentials()
            webhook_secret = credentials.get("webhook_secret")
            
            if not webhook_secret:
                logger.warning("No webhook secret configured for Wave")
                return False
                
            # Create the signature using HMAC-SHA256
            payload_string = json.dumps(payload, separators=(',', ':'))
            computed_signature = hmac.new(
                webhook_secret.encode(),
                payload_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures using constant-time comparison to prevent timing attacks
            return hmac.compare_digest(computed_signature, signature)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Wave webhook signature verification error: {error_message}")
            return False
            
    def log_refund_transaction(self, refund_id: str, data: Dict[str, Any], status: str) -> None:
        """
        Log a refund transaction.
        
        Args:
            refund_id: Refund ID
            data: Transaction data
            status: Transaction status
        """
        try:
            # Create log entry with standardized fields
            log_entry = {
                "provider": self.provider_id,
                "refund_id": refund_id,
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "data": data
            }
            
            # Use the security module to log the transaction
            self.security.log_transaction("refund", log_entry)
        except Exception as e:
            logger.error(f"Failed to log refund transaction: {str(e)}")
    
    async def create_subscription(self, subscription_request: SubscriptionCreate) -> SubscriptionResponse:
        """
        Create a subscription through Wave.
        
        Args:
            subscription_request: Subscription request details
            
        Returns:
            Subscription response with details
        """
        try:
            customer_email = subscription_request.customer_email
            plan_name = subscription_request.plan_name
            plan_description = subscription_request.plan_description
            amount = subscription_request.amount
            currency = subscription_request.currency.upper()
            billing_period = subscription_request.billing_period
            billing_interval = subscription_request.billing_interval
            start_date = subscription_request.start_date
            metadata = subscription_request.metadata or {}
            
            # Get or create customer
            customer_id = await self._get_or_create_customer(customer_email)
            
            if not customer_id:
                raise ValueError(f"Failed to create or find customer with email {customer_email}")
            
            # Get or create subscription plan
            plan_id = await self._create_or_get_plan(
                plan_name,
                plan_description,
                amount,
                currency,
                billing_period,
                billing_interval
            )
            
            if not plan_id:
                raise ValueError(f"Failed to create or find plan {plan_name}")
            
            # Format start date if provided
            start_date_str = None
            if start_date:
                start_date_str = start_date.strftime("%Y-%m-%d")
            
            # Format amount with correct decimals
            # Wave requires amount in the smallest currency unit (e.g., cents for USD)
            amount_in_cents = int(amount * 100)
            
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # Prepare the subscription payload
            payload = {
                "customer": customer_id,
                "plan": plan_id,
                "start_date": start_date_str,
                "auto_renew": True,  # Default to auto-renew
                "metadata": {
                    **metadata,
                    "source": "kaapi"
                }
            }
            
            # Add trial period if specified
            if subscription_request.trial_period_days:
                payload["trial_period_days"] = subscription_request.trial_period_days
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}subscriptions",
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        logger.error(f"Wave subscription creation error: {result}")
                        raise ValueError(f"Failed to create subscription: {result.get('message', 'Unknown error')}")
                    
                    subscription_data = result.get("data", {})
                    
                    # Determine subscription status
                    wave_status = subscription_data.get("status", "").lower()
                    if wave_status == "active":
                        status = SubscriptionStatus.ACTIVE.value
                    elif wave_status == "trialing":
                        status = SubscriptionStatus.ACTIVE.value
                    elif wave_status == "past_due":
                        status = SubscriptionStatus.PAST_DUE.value
                    elif wave_status == "canceled" or wave_status == "cancelled":
                        status = SubscriptionStatus.CANCELED.value
                    else:
                        status = SubscriptionStatus.PENDING.value
                    
                    # Determine next billing date
                    next_billing_date = None
                    if subscription_data.get("next_billing_date"):
                        try:
                            next_billing_date = datetime.strptime(
                                subscription_data.get("next_billing_date"), 
                                "%Y-%m-%d"
                            ).date()
                        except:
                            pass
                    
                    # Prepare response
                    return SubscriptionResponse(
                        provider_id=self.provider_id,
                        subscription_id=subscription_data.get("id"),
                        customer_email=customer_email,
                        plan_name=plan_name,
                        amount=amount,
                        currency=currency,
                        status=status,
                        current_period_end=next_billing_date,
                        created_at=datetime.now(),
                        metadata={
                            **metadata,
                            "plan_id": plan_id,
                            "customer_id": customer_id
                        }
                    )
        
        except Exception as e:
            logger.error(f"Wave subscription creation error: {str(e)}")
            raise ValueError(f"Failed to create subscription: {str(e)}")
    
    async def update_subscription(self, subscription_id: str, subscription_update: SubscriptionUpdate) -> SubscriptionResponse:
        """
        Update a subscription with Wave.
        
        Args:
            subscription_id: Wave subscription ID
            subscription_update: Subscription update details
            
        Returns:
            Updated subscription response
        """
        try:
            # Get current subscription details
            current_subscription = await self.get_subscription(subscription_id)
            
            # Wave doesn't support directly changing plan or amount on an existing subscription
            # We can only update metadata and auto-renew flag
            metadata = subscription_update.metadata or {}
            auto_renew = subscription_update.auto_renew
            
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # Prepare update payload
            payload = {
                "auto_renew": auto_renew
            }
            
            # If metadata provided, update it
            if metadata:
                payload["metadata"] = {
                    **current_subscription.get("metadata", {}),
                    **metadata,
                    "updated_at": datetime.now().isoformat()
                }
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    f"{self.api_base_url}subscriptions/{subscription_id}",
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        logger.error(f"Wave subscription update error: {result}")
                        raise ValueError(f"Failed to update subscription: {result.get('message', 'Unknown error')}")
                    
                    subscription_data = result.get("data", {})
                    
                    # Get the updated subscription details
                    updated_subscription = await self.get_subscription(subscription_id)
                    
                    # Prepare response using updated details
                    return SubscriptionResponse(
                        provider_id=self.provider_id,
                        subscription_id=subscription_id,
                        customer_email=updated_subscription.get("customer_email", ""),
                        plan_name=updated_subscription.get("name", ""),
                        amount=updated_subscription.get("amount", 0),
                        currency=updated_subscription.get("currency", ""),
                        status=updated_subscription.get("status", SubscriptionStatus.UNKNOWN.value),
                        current_period_end=updated_subscription.get("next_billing_date"),
                        created_at=None,  # We don't have this from the update response
                        metadata=updated_subscription.get("metadata", {})
                    )
        
        except Exception as e:
            logger.error(f"Wave subscription update error: {str(e)}")
            raise ValueError(f"Failed to update subscription: {str(e)}")
    
    async def cancel_subscription(self, subscription_id: str, cancel_request: SubscriptionCancelRequest = None) -> SubscriptionResponse:
        """
        Cancel a subscription with Wave.
        
        Args:
            subscription_id: Wave subscription ID
            cancel_request: Optional cancel request details
            
        Returns:
            Canceled subscription response
        """
        try:
            # Wave allows cancellation by setting auto_renew to False
            # and providing a cancellation reason if specified
            
            # Get current subscription details
            current_subscription = await self.get_subscription(subscription_id)
            
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "auto_renew": False
            }
            
            # Add cancellation reason if provided
            if cancel_request and cancel_request.reason:
                payload["cancellation_reason"] = cancel_request.reason
            
            # Add to metadata
            payload["metadata"] = {
                **current_subscription.get("metadata", {}),
                "canceled_at": datetime.now().isoformat(),
                "auto_renew": False
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    f"{self.api_base_url}subscriptions/{subscription_id}",
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        logger.error(f"Wave subscription cancellation error: {result}")
                        raise ValueError(f"Failed to cancel subscription: {result.get('message', 'Unknown error')}")
                    
                    # Get the updated subscription details
                    updated_subscription = await self.get_subscription(subscription_id)
                    
                    # For Wave, we're essentially disabling auto-renewal, but the subscription
                    # remains active until the end of the current period
                    status = SubscriptionStatus.ACTIVE.value
                    if updated_subscription.get("end_date") and datetime.now().date() >= updated_subscription.get("end_date"):
                        status = SubscriptionStatus.CANCELED.value
                    
                    # Prepare response
                    return SubscriptionResponse(
                        provider_id=self.provider_id,
                        subscription_id=subscription_id,
                        customer_email=updated_subscription.get("customer_email", ""),
                        plan_name=updated_subscription.get("name", ""),
                        amount=updated_subscription.get("amount", 0),
                        currency=updated_subscription.get("currency", ""),
                        status=status,
                        current_period_end=updated_subscription.get("end_date"),
                        created_at=None,  # We don't have this from the update response
                        metadata={
                            **updated_subscription.get("metadata", {}),
                            "canceled_at": datetime.now().isoformat(),
                            "auto_renew": False
                        }
                    )
        
        except Exception as e:
            logger.error(f"Wave subscription cancellation error: {str(e)}")
            raise ValueError(f"Failed to cancel subscription: {str(e)}")
    
    async def pause_subscription(self, subscription_id: str) -> SubscriptionResponse:
        """
        Pause a subscription with Wave.
        Note: Wave doesn't directly support pausing, so we'll disable auto-renew
        which effectively pauses the subscription after the current period ends.
        
        Args:
            subscription_id: Wave subscription ID
            
        Returns:
            Paused subscription response
        """
        try:
            # Wave doesn't directly support pausing, so we'll update the metadata
            # and disable auto-renew to prevent renewal after the current period
            
            # Get current subscription details
            current_subscription = await self.get_subscription(subscription_id)
            
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "auto_renew": False,
                "metadata": {
                    **current_subscription.get("metadata", {}),
                    "paused_at": datetime.now().isoformat(),
                    "is_paused": True,
                    "auto_renew_before_pause": current_subscription.get("auto_renew", True)
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    f"{self.api_base_url}subscriptions/{subscription_id}",
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        logger.error(f"Wave subscription pause error: {result}")
                        raise ValueError(f"Failed to pause subscription: {result.get('message', 'Unknown error')}")
                    
                    # Get the updated subscription details
                    updated_subscription = await self.get_subscription(subscription_id)
                    
                    # Prepare response
                    return SubscriptionResponse(
                        provider_id=self.provider_id,
                        subscription_id=subscription_id,
                        customer_email=updated_subscription.get("customer_email", ""),
                        plan_name=updated_subscription.get("name", ""),
                        amount=updated_subscription.get("amount", 0),
                        currency=updated_subscription.get("currency", ""),
                        status=SubscriptionStatus.PAUSED.value,  # Mark as paused in our system
                        current_period_end=updated_subscription.get("end_date"),
                        created_at=None,  # We don't have this from the update response
                        metadata={
                            **updated_subscription.get("metadata", {}),
                            "paused_at": datetime.now().isoformat(),
                            "is_paused": True,
                            "auto_renew_before_pause": current_subscription.get("auto_renew", True)
                        }
                    )
        
        except Exception as e:
            logger.error(f"Wave subscription pause error: {str(e)}")
            raise ValueError(f"Failed to pause subscription: {str(e)}")
    
    async def resume_subscription(self, subscription_id: str) -> SubscriptionResponse:
        """
        Resume a paused subscription with Wave.
        Note: Since Wave doesn't directly support pausing, we just re-enable auto-renew
        if the subscription is still active. If it has ended, we'll need to create a new one.
        
        Args:
            subscription_id: Wave subscription ID
            
        Returns:
            Resumed subscription response or indication that a new subscription is needed
        """
        try:
            # Get current subscription details
            current_subscription = await self.get_subscription(subscription_id)
            
            # Check if subscription has metadata indicating it was paused
            metadata = current_subscription.get("metadata", {})
            
            if not metadata.get("is_paused"):
                logger.warning(f"Subscription {subscription_id} was not paused")
                # Just return current details if not paused
                return SubscriptionResponse(
                    provider_id=self.provider_id,
                    subscription_id=subscription_id,
                    customer_email=current_subscription.get("customer_email", ""),
                    plan_name=current_subscription.get("name", ""),
                    amount=current_subscription.get("amount", 0),
                    currency=current_subscription.get("currency", ""),
                    status=current_subscription.get("status", SubscriptionStatus.UNKNOWN.value),
                    current_period_end=current_subscription.get("next_billing_date"),
                    created_at=None,
                    metadata=metadata
                )
            
            # Check if subscription has ended
            end_date = current_subscription.get("end_date")
            if end_date and datetime.now().date() > end_date:
                # Subscription has ended, need to create a new one
                logger.info(f"Subscription {subscription_id} has ended, needs to be recreated")
                
                # Return a response indicating a new subscription is needed
                return SubscriptionResponse(
                    provider_id=self.provider_id,
                    subscription_id=subscription_id,
                    customer_email=current_subscription.get("customer_email", ""),
                    plan_name=current_subscription.get("name", ""),
                    amount=current_subscription.get("amount", 0),
                    currency=current_subscription.get("currency", ""),
                    status=SubscriptionStatus.EXPIRED.value,
                    current_period_end=end_date,
                    created_at=None,
                    metadata={
                        **metadata,
                        "requires_new_subscription": True,
                        "resumed_at": datetime.now().isoformat()
                    }
                )
            
            # Subscription is still active, re-enable auto-renew
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # Check if we stored the previous auto-renew value
            auto_renew = metadata.get("auto_renew_before_pause", True)
            
            payload = {
                "auto_renew": auto_renew
            }
            
            # If metadata provided, update it
            if metadata:
                payload["metadata"] = {
                    **metadata,
                    "is_paused": False,
                    "resumed_at": datetime.now().isoformat(),
                    "auto_renew": auto_renew
                }
            
            # Remove the paused-related metadata
            if "paused_at" in payload["metadata"]:
                del payload["metadata"]["paused_at"]
            if "auto_renew_before_pause" in payload["metadata"]:
                del payload["metadata"]["auto_renew_before_pause"]
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    f"{self.api_base_url}subscriptions/{subscription_id}",
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        logger.error(f"Wave subscription resume error: {result}")
                        raise ValueError(f"Failed to resume subscription: {result.get('message', 'Unknown error')}")
                    
                    # Get the updated subscription details
                    updated_subscription = await self.get_subscription(subscription_id)
                    
                    # Prepare response
                    return SubscriptionResponse(
                        provider_id=self.provider_id,
                        subscription_id=subscription_id,
                        customer_email=updated_subscription.get("customer_email", ""),
                        plan_name=updated_subscription.get("name", ""),
                        amount=updated_subscription.get("amount", 0),
                        currency=updated_subscription.get("currency", ""),
                        status=SubscriptionStatus.ACTIVE.value,
                        current_period_end=updated_subscription.get("next_billing_date"),
                        created_at=None,
                        metadata={
                            **updated_subscription.get("metadata", {}),
                            "resumed_at": datetime.now().isoformat(),
                            "is_paused": False
                        }
                    )
        
        except Exception as e:
            logger.error(f"Wave subscription resume error: {str(e)}")
            raise ValueError(f"Failed to resume subscription: {str(e)}")

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details from Wave.
        
        Args:
            subscription_id: Wave subscription ID
            
        Returns:
            Dictionary with subscription details
        """
        try:
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}subscriptions/{subscription_id}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        logger.error(f"Wave get subscription error: {result}")
                        raise ValueError(f"Failed to get subscription: {result.get('message', 'Unknown error')}")
                    
                    data = result.get("data", {})
                    
                    # Map status
                    status = self._map_wave_subscription_status_to_internal(data.get("status"))
                    
                    # Determine dates
                    start_date = None
                    end_date = None
                    next_billing_date = None
                    
                    if data.get("start_date"):
                        try:
                            start_date = datetime.strptime(data.get("start_date"), "%Y-%m-%d").date()
                        except:
                            pass
                            
                    if data.get("end_date"):
                        try:
                            end_date = datetime.strptime(data.get("end_date"), "%Y-%m-%d").date()
                        except:
                            pass
                            
                    if data.get("next_billing_date"):
                        try:
                            next_billing_date = datetime.strptime(data.get("next_billing_date"), "%Y-%m-%d").date()
                        except:
                            pass
                    
                    # Extract plan details
                    plan = data.get("plan", {})
                    amount = plan.get("amount", 0) / 100  # Convert from cents
                    currency = plan.get("currency", "USD")
                    billing_period = "monthly"  # Default
                    billing_interval = 1  # Default
                    
                    # Try to extract billing details from plan name or interval
                    if plan.get("interval"):
                        interval_parts = plan.get("interval", "").lower().split("_")
                        if len(interval_parts) >= 2:
                            try:
                                billing_interval = int(interval_parts[0])
                                if "day" in interval_parts[1]:
                                    billing_period = "daily"
                                elif "week" in interval_parts[1]:
                                    billing_period = "weekly"
                                elif "month" in interval_parts[1]:
                                    billing_period = "monthly"
                                elif "year" in interval_parts[1]:
                                    billing_period = "yearly"
                            except:
                                pass
                    
                    # Extract customer email
                    customer = data.get("customer", {})
                    customer_email = customer.get("email", "")
                    
                    # Check if subscription is in trial
                    is_in_trial = data.get("is_in_trial", False)
                    
                    # Check auto-renew status
                    auto_renew = data.get("auto_renew", True)
                    
                    # Prepare the response
                    subscription_data = {
                        "name": plan.get("name", ""),
                        "description": plan.get("description", ""),
                        "status": status,
                        "amount": amount,
                        "currency": currency,
                        "billing_period": billing_period,
                        "billing_interval": billing_interval,
                        "customer_email": customer_email,
                        "start_date": start_date,
                        "end_date": end_date,
                        "next_billing_date": next_billing_date,
                        "is_in_trial": is_in_trial,
                        "auto_renew": auto_renew,
                        "metadata": data.get("metadata", {}),
                        "is_active": status == SubscriptionStatus.ACTIVE.value,
                        "is_past_due": status == SubscriptionStatus.PAST_DUE.value,
                        "is_canceled": status == SubscriptionStatus.CANCELED.value
                    }
                    
                    return subscription_data
        
        except Exception as e:
            logger.error(f"Wave get subscription error: {str(e)}")
            raise ValueError(f"Failed to get subscription: {str(e)}")
    
    async def list_customer_subscriptions(self, customer_email: str) -> List[Dict[str, Any]]:
        """
        List all subscriptions for a customer with Wave.
        
        Args:
            customer_email: Customer email
            
        Returns:
            List of dictionaries with subscription details
        """
        try:
            # First get customer ID
            customer_id = await self._get_or_create_customer(customer_email, create_if_not_exists=False)
            
            if not customer_id:
                logger.info(f"Customer with email {customer_email} not found in Wave")
                return []
            
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}customers/{customer_id}/subscriptions",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get("status") != "success":
                        logger.error(f"Wave list subscriptions error: {result}")
                        raise ValueError(f"Failed to list subscriptions: {result.get('message', 'Unknown error')}")
                    
                    subscriptions = result.get("data", [])
                    
                    # Process each subscription
                    result_list = []
                    for sub in subscriptions:
                        try:
                            subscription_id = sub.get("id")
                            # Get full details for each subscription
                            subscription_data = await self.get_subscription(subscription_id)
                            result_list.append(subscription_data)
                        except Exception as sub_error:
                            logger.error(f"Error getting subscription details: {str(sub_error)}")
                            continue
                    
                    return result_list
        
        except Exception as e:
            logger.error(f"Wave list subscriptions error: {str(e)}")
            raise ValueError(f"Failed to list subscriptions: {str(e)}")
    
    async def _get_or_create_customer(self, email: str, create_if_not_exists: bool = True) -> Optional[str]:
        """
        Get or create a customer in Wave.
        
        Args:
            email: Customer email
            create_if_not_exists: Whether to create the customer if not found
            
        Returns:
            Customer ID or None if not found/created
        """
        try:
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # First try to find the customer
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}customers",
                    headers=headers,
                    params={"email": email}
                ) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("status") == "success":
                        customers = result.get("data", [])
                        if customers:
                            # Return the first matching customer
                            return customers[0].get("id")
            
            # If customer not found and we're allowed to create
            if create_if_not_exists:
                customer_data = {
                    "email": email,
                    "first_name": email.split("@")[0],  # Default name from email
                    "metadata": {
                        "source": "kaapi"
                    }
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_base_url}customers",
                        headers=headers,
                        json=customer_data
                    ) as response:
                        result = await response.json()
                        
                        if response.status == 200 and result.get("status") == "success":
                            return result.get("data", {}).get("id")
            
            # Customer not found or created
            return None
            
        except Exception as e:
            logger.error(f"Wave get/create customer error: {str(e)}")
            return None
    
    async def _create_or_get_plan(
        self, 
        name: str, 
        description: str, 
        amount: float, 
        currency: str,
        billing_period: str,
        billing_interval: int
    ) -> Optional[str]:
        """
        Create or get a subscription plan in Wave.
        
        Args:
            name: Plan name
            description: Plan description
            amount: Plan amount
            currency: Plan currency
            billing_period: Billing period (daily, weekly, monthly, yearly)
            billing_interval: Billing interval
            
        Returns:
            Plan ID or None if failed
        """
        try:
            headers = {
                "Authorization": f"Bearer {self._get_credentials().get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # Map billing period to Wave interval
            interval = "monthly"  # Default
            if billing_period == "daily":
                interval = f"{billing_interval}_days"
            elif billing_period == "weekly":
                interval = f"{billing_interval}_weeks"
            elif billing_period == "monthly":
                interval = f"{billing_interval}_months"
            elif billing_period == "yearly":
                interval = f"{billing_interval}_years"
                
            # Format amount with correct decimals
            # Wave requires amount in the smallest currency unit (e.g., cents for USD)
            amount_in_cents = int(amount * 100)
                
            # Generate a unique plan code
            plan_code = f"kaapi_{name.lower().replace(' ', '_')}_{currency.lower()}_{interval}"
            
            # First check if the plan already exists
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}plans",
                    headers=headers,
                    params={"code": plan_code}
                ) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("status") == "success":
                        plans = result.get("data", [])
                        if plans:
                            # Return the first matching plan
                            return plans[0].get("id")
            
            # If plan not found, create it
            plan_data = {
                "name": name,
                "description": description,
                "amount": amount_in_cents,
                "currency": currency,
                "interval": interval,
                "code": plan_code,
                "metadata": {
                    "source": "kaapi",
                    "billing_period": billing_period,
                    "billing_interval": billing_interval
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}plans",
                    headers=headers,
                    json=plan_data
                ) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get("status") == "success":
                        return result.get("data", {}).get("id")
            
            # Plan not found or created
            return None
            
        except Exception as e:
            logger.error(f"Wave create/get plan error: {str(e)}")
            return None
    
    def _map_wave_subscription_status_to_internal(self, status: str) -> str:
        """
        Map Wave subscription status to internal status.
        
        Args:
            status: Wave subscription status
            
        Returns:
            Internal subscription status
        """
        status_map = {
            "active": SubscriptionStatus.ACTIVE.value,
            "canceled": SubscriptionStatus.CANCELED.value,
            "cancelled": SubscriptionStatus.CANCELED.value,
            "past_due": SubscriptionStatus.PAST_DUE.value,
            "unpaid": SubscriptionStatus.PAST_DUE.value,
            "incomplete": SubscriptionStatus.PENDING.value,
            "trialing": SubscriptionStatus.ACTIVE.value,
            "trial": SubscriptionStatus.ACTIVE.value,
            "paused": SubscriptionStatus.PAUSED.value,
            "completed": SubscriptionStatus.EXPIRED.value,
            "expired": SubscriptionStatus.EXPIRED.value
        }
        
        return status_map.get(status.lower() if status else "", SubscriptionStatus.UNKNOWN.value)

    def log_payment_transaction(self, payment_id: str, data: Dict[str, Any], status: str) -> None:
        """
        Log a payment transaction.
        
        Args:
            payment_id: Payment ID
            data: Transaction data
            status: Transaction status
        """
        # Implement logging logic here
        pass

    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data
        """
        # Implement encryption logic here
        pass
