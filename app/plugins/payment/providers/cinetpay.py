"""
CinetPay payment provider implementation.

This module implements the CinetPay payment provider interface.
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
from ..models.provider import ProviderResponse, PaymentProviderConfig, PaymentRequest, RefundRequest
from ..models.subscription import SubscriptionRequest, SubscriptionStatus, SubscriptionResponse
from .base_provider import BasePaymentProvider
from .provider_factory import PaymentProviderFactory

logger = logging.getLogger("kaapi.payment.cinetpay")


@PaymentProviderFactory.register
class CinetPayProvider(BasePaymentProvider):
    """CinetPay payment provider implementation."""

    provider_id = "cinetpay"
    provider_name = "CinetPay"
    logo_url = "https://cinetpay.com/logo.png"

    def __init__(self, config: PaymentProviderConfig):
        """
        Initialize a CinetPay payment provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        
        # Store provider configuration
        self.api_base_url = config.get("api_base_url", "https://api-checkout.cinetpay.com/v2")
        self.mode = config.get("mode", "test").lower()  # test or live
        
        # Set API base URL based on mode
        if self.mode == "test":
            self.api_base_url = "https://api-checkout.cinetpay.com/v2/sandbox"
            
        # Store configuration
        self.return_url = config.get("return_url", "")
        self.cancel_url = config.get("cancel_url", "")
        self.notify_url = config.get("notify_url", "")
        
        # Store credentials securely
        self._store_credentials(config)
        
        logger.info(f"CinetPay payment provider initialized with mode: {self.mode}")
        
    def _store_credentials(self, config: PaymentProviderConfig) -> None:
        """
        Store provider credentials securely.
        
        Args:
            config: Provider configuration
        """
        credentials = {
            "api_key": config.get("api_key", ""),
            "site_id": config.get("site_id", ""),
            "webhook_secret": config.get("webhook_secret", ""),
            "mode": config.get("mode", "test")
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

    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through CinetPay.
        
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
            
            # Validate payment data for PCI compliance if card data is present
            if any(field in payment_request.request_metadata for field in ["card_number", "cvv", "expiry"]):
                validation_errors = self.security.validate_pci_data(payment_request.request_metadata)
                if validation_errors:
                    logger.error(f"PCI validation errors: {validation_errors}")
                    
                    # Log the validation failure
                    self.log_payment_transaction(
                        payment_request.payment_id,
                        {
                            "errors": validation_errors,
                            "payment_id": payment_request.payment_id
                        },
                        "validation_failed"
                    )
                    
                    return ProviderResponse(
                        provider_id=self.provider_id,
                        payment_id=payment_request.payment_id,
                        status=PaymentStatus.FAILED.value,
                        message=f"Payment failed due to validation errors: {', '.join(validation_errors)}"
                    )
            
            # Encrypt sensitive data before processing
            encrypted_metadata = {}
            if payment_request.request_metadata:
                encrypted_metadata = self.encrypt_sensitive_data(payment_request.request_metadata)
            
            # Extract customer information
            customer_name = payment_request.customer_name or "Customer"
            customer_email = payment_request.customer_email or ""
            customer_phone = payment_request.customer_phone or ""
            
            # Format amount (CinetPay expects amount in smallest currency unit)
            # For most currencies this is 100 = 1 unit (e.g., 100 cents = 1 USD)
            amount = int(payment_request.amount * 100)
            currency = payment_request.currency.upper()
            
            # Generate a unique transaction ID
            transaction_id = f"TX-{int(time.time())}-{payment_request.payment_id}"
            
            # Get credentials
            credentials = self._get_credentials()
            
            # Log payment initiation
            payment_log_data = {
                "payment_id": payment_request.payment_id,
                "transaction_id": transaction_id,
                "amount": payment_request.amount,
                "currency": currency,
                "customer_email": customer_email,
                "payment_method": "cinetpay"
            }
            
            self.log_payment_transaction(
                payment_request.payment_id,
                payment_log_data,
                "initiated"
            )
            
            # Prepare the payment data
            payment_data = {
                "apikey": credentials.get("api_key", ""),
                "site_id": credentials.get("site_id", ""),
                "transaction_id": transaction_id,
                "amount": amount,
                "currency": currency,
                "description": payment_request.description or "Payment",
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone_number": customer_phone,
                "return_url": self.return_url,
                "cancel_url": self.cancel_url,
                "notify_url": self.notify_url,
                "metadata": {  # This key remains "metadata" because that's what CinetPay expects
                    "payment_id": payment_request.payment_id,
                    "encrypted_data": encrypted_metadata,
                    "source": "kaapi"
                },
                "channels": "ALL"  # Accept all payment channels
            }
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/payment",
                    json=payment_data
                ) as response:
                    result = await response.json()
                    
                    # Update payment log with response
                    payment_log_data["provider_response"] = result
                    
                    if response.status != 200 or result.get("code") != "201":
                        error_message = result.get('message', 'Unknown error')
                        logger.error(f"CinetPay payment error: {error_message}")
                        
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
                    
                    # Extract payment URL and data
                    payment_data = result.get("data", {})
                    payment_url = payment_data.get("payment_url")
                    payment_token = payment_data.get("payment_token")
                    
                    if not payment_url:
                        logger.error(f"CinetPay payment missing payment URL: {result}")
                        
                        # Log failure due to missing URL
                        payment_log_data["error"] = "Missing payment URL in response"
                        self.log_payment_transaction(
                            payment_request.payment_id,
                            payment_log_data,
                            "failed"
                        )
                        
                        return ProviderResponse(
                            provider_id=self.provider_id,
                            payment_id=payment_request.payment_id,
                            status=PaymentStatus.FAILED.value,
                            message="Invalid response from CinetPay: Missing payment URL"
                        )
                    
                    # Log successful payment initiation
                    payment_log_data["payment_url"] = payment_url
                    payment_log_data["payment_token"] = payment_token
                    
                    self.log_payment_transaction(
                        payment_request.payment_id,
                        payment_log_data,
                        "pending"
                    )
                    
                    # Return provider response
                    return ProviderResponse(
                        provider_id=self.provider_id,
                        payment_id=payment_request.payment_id,
                        provider_payment_id=payment_token or transaction_id,
                        redirect_url=payment_url,
                        status=PaymentStatus.PENDING.value,
                        message="Payment initiated",
                        details={
                            "payment_url": payment_url,
                            "payment_token": payment_token,
                            "transaction_id": transaction_id
                        }
                    )
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"CinetPay payment error: {error_message}")
            
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
                message=f"Payment failed: {error_message}"
            )

    async def verify_payment(self, provider_payment_id: str, payment_id: str = None) -> ProviderResponse:
        """
        Verify the status of a payment with CinetPay.
        
        Args:
            provider_payment_id: CinetPay payment token or transaction ID
            payment_id: Optional internal payment ID
            
        Returns:
            Provider response with payment status
        """
        try:
            # Get credentials
            credentials = self._get_credentials()
            
            # Log verification attempt
            verification_log_data = {
                "provider_payment_id": provider_payment_id,
                "payment_id": payment_id,
                "verification_time": datetime.now().isoformat()
            }
            
            self.log_payment_transaction(
                payment_id or provider_payment_id,
                verification_log_data,
                "verification_initiated"
            )
            
            # Prepare the verification data
            verification_data = {
                "apikey": credentials.get("api_key", ""),
                "site_id": credentials.get("site_id", ""),
                "transaction_id": provider_payment_id
            }
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/payment/check",
                    json=verification_data
                ) as response:
                    result = await response.json()
                    
                    # Update verification log with response
                    verification_log_data["provider_response"] = result
                    
                    if response.status != 200:
                        error_message = result.get('message', 'Unknown error')
                        logger.error(f"CinetPay payment verification error: {error_message}")
                        
                        # Log verification failure
                        self.log_payment_transaction(
                            payment_id or provider_payment_id,
                            verification_log_data,
                            "verification_failed"
                        )
                        
                        return ProviderResponse(
                            provider_id=self.provider_id,
                            payment_id=payment_id,
                            provider_payment_id=provider_payment_id,
                            status=PaymentStatus.UNKNOWN.value,
                            message=f"Failed to verify payment: {error_message}"
                        )
                    
                    # Extract payment status
                    payment_data = result.get("data", {})
                    status_code = payment_data.get("status")
                    
                    # Map CinetPay status to internal status
                    if status_code == "ACCEPTED":
                        payment_status = PaymentStatus.COMPLETED.value
                        log_status = "completed"
                        message = "Payment completed successfully"
                    elif status_code == "PENDING":
                        payment_status = PaymentStatus.PENDING.value
                        log_status = "pending"
                        message = "Payment is pending"
                    elif status_code == "CANCELED":
                        payment_status = PaymentStatus.CANCELLED.value
                        log_status = "cancelled"
                        message = "Payment was cancelled"
                    elif status_code == "REFUSED":
                        payment_status = PaymentStatus.FAILED.value
                        log_status = "failed"
                        message = "Payment was refused"
                    else:
                        payment_status = PaymentStatus.FAILED.value
                        log_status = "unknown"
                        message = f"Payment failed with status: {status_code}"
                    
                    # Get amount from response
                    amount = None
                    try:
                        amount = float(payment_data.get("amount", 0)) / 100  # Convert from cents
                    except (ValueError, TypeError):
                        pass
                    
                    # Get currency from response
                    currency = payment_data.get("currency")
                    
                    # Log verification result
                    verification_log_data["status"] = payment_status
                    verification_log_data["amount"] = amount
                    verification_log_data["currency"] = currency
                    
                    self.log_payment_transaction(
                        payment_id or provider_payment_id,
                        verification_log_data,
                        log_status
                    )
                    
                    # Return provider response
                    return ProviderResponse(
                        provider_id=self.provider_id,
                        payment_id=payment_id,
                        provider_payment_id=provider_payment_id,
                        amount=amount,
                        currency=currency,
                        status=payment_status,
                        message=message,
                        details={
                            "status_code": status_code,
                            "payment_method": payment_data.get("payment_method"),
                            "payment_date": payment_data.get("payment_date"),
                            "metadata": payment_data.get("metadata", {})
                        }
                    )
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"CinetPay payment verification error: {error_message}")
            
            # Log exception during verification
            self.log_payment_transaction(
                payment_id or provider_payment_id,
                {"error": error_message},
                "verification_error"
            )
            
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=payment_id,
                provider_payment_id=provider_payment_id,
                status=PaymentStatus.UNKNOWN.value,
                message=f"Error verifying payment: {error_message}"
            )

    async def cancel_payment(self, provider_payment_id: str, payment_id: str = None) -> ProviderResponse:
        """
        Cancel a pending payment with CinetPay.
        
        Args:
            provider_payment_id: CinetPay payment token or transaction ID
            payment_id: Optional internal payment ID
            
        Returns:
            Provider response with cancellation status
        """
        try:
            # CinetPay doesn't have a direct API for cancelling payments
            # We'll verify the payment first, then return appropriate response
            verify_response = await self.verify_payment(provider_payment_id, payment_id)
            
            # If payment is already completed, we can't cancel it
            if verify_response.status == PaymentStatus.COMPLETED.value:
                return ProviderResponse(
                    provider_id=self.provider_id,
                    payment_id=payment_id,
                    provider_payment_id=provider_payment_id,
                    status=PaymentStatus.COMPLETED.value,
                    message="Cannot cancel a completed payment",
                    raw_response={"error": "Payment already completed"}
                )
                
            # If payment is already cancelled, return success
            if verify_response.status == PaymentStatus.CANCELLED.value:
                return ProviderResponse(
                    provider_id=self.provider_id,
                    payment_id=payment_id,
                    provider_payment_id=provider_payment_id,
                    status=PaymentStatus.CANCELLED.value,
                    message="Payment was already cancelled",
                    raw_response={"status": "cancelled"}
                )
                
            # For pending payments, we'll just return a message that the user should
            # not complete the payment, as CinetPay doesn't support direct cancellation
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=payment_id,
                provider_payment_id=provider_payment_id,
                status=PaymentStatus.CANCELLED.value,
                message="Payment marked as cancelled. Note: The payment must be abandoned by the customer.",
                raw_response={"status": "marked_as_cancelled"}
            )
                
        except Exception as e:
            logger.error(f"CinetPay payment cancellation error: {str(e)}")
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=payment_id,
                provider_payment_id=provider_payment_id,
                status=PaymentStatus.FAILED.value,
                message=f"Payment cancellation failed: {str(e)}",
                raw_response={"error": str(e)}
            )

    async def process_refund(self, refund_request: RefundRequest) -> ProviderResponse:
        """
        Process a refund through CinetPay.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Provider response with refund details
        """
        try:
            # CinetPay doesn't have a direct API for processing refunds through their API
            # We'll need to manually process this and then mark it in our system
            
            # First verify the payment exists and is completed
            verify_response = await self.verify_payment(
                refund_request.provider_payment_id, 
                refund_request.payment_id
            )
            
            if verify_response.status != PaymentStatus.COMPLETED.value:
                logger.error(f"Cannot refund a payment that is not completed: {verify_response.status}")
                return ProviderResponse(
                    provider_id=self.provider_id,
                    payment_id=refund_request.payment_id,
                    provider_payment_id=refund_request.provider_payment_id,
                    status=RefundStatus.FAILED.value,
                    message=f"Cannot refund a payment that is not completed. Current status: {verify_response.status}",
                    raw_response={"error": "Payment not completed"}
                )
            
            # For CinetPay, refunds are typically processed manually by contacting support
            # We'll return a success response with instructions for manual processing
            
            # Generate a refund reference for tracking
            refund_ref = f"RF-{int(time.time())}-{refund_request.payment_id}"
            
            # Create security audit log
            self.log_refund_transaction(
                refund_request.payment_id,
                {
                    "refund_id": refund_ref,
                    "amount": refund_request.amount,
                    "currency": refund_request.currency,
                    "status": RefundStatus.PENDING.value
                },
                "initiated"
            )
            
            # Encrypt sensitive refund metadata before processing
            encrypted_metadata = None
            if refund_request.refund_metadata:
                encrypted_metadata = self.encrypt_sensitive_data(refund_request.refund_metadata)
            
            refund_data = {
                "apikey": self._get_credentials().get("api_key", ""),
                "site_id": self._get_credentials().get("site_id", ""),
                "transaction_id": refund_request.payment_reference,
                "amount": refund_request.amount,
                "currency": refund_request.currency.value,
                "reason": refund_request.reason or "Customer refund request",
                "metadata": {  # This key remains "metadata" because that's what CinetPay expects
                    "refund_id": refund_request.refund_metadata.get("refund_id", ""),
                    "encrypted_data": encrypted_metadata,
                    "source": "kaapi"
                }
            }
            
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=refund_request.payment_id,
                provider_refund_id=refund_ref,
                status=RefundStatus.PENDING.value,
                message="Refund initiated. Please process this refund manually through CinetPay dashboard or support.",
                raw_response={
                    "refund_reference": refund_ref,
                    "amount": refund_request.amount,
                    "reason": refund_request.reason,
                    "note": "This refund requires manual processing through CinetPay"
                }
            )
            
        except Exception as e:
            logger.error(f"CinetPay refund error: {str(e)}")
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=refund_request.payment_id,
                provider_payment_id=refund_request.provider_payment_id,
                status=RefundStatus.FAILED.value,
                message=f"Refund failed: {str(e)}",
                raw_response={"error": str(e)}
            )

    async def verify_refund(self, provider_refund_id: str, payment_id: str = None) -> ProviderResponse:
        """
        Verify the status of a refund with CinetPay.
        
        Args:
            provider_refund_id: CinetPay refund reference
            payment_id: Optional internal payment ID
            
        Returns:
            Provider response with refund status
        """
        try:
            # CinetPay doesn't have a direct API for verifying refunds
            # Since refunds are processed manually, we'll return a pending status
            # with a message for manual verification
            
            # Create security audit log
            self.log_refund_transaction(
                payment_id or provider_refund_id,
                {
                    "refund_id": provider_refund_id,
                    "status": RefundStatus.PENDING.value
                },
                "verification_initiated"
            )
            
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=payment_id,
                provider_refund_id=provider_refund_id,
                status=RefundStatus.PENDING.value,
                message="Please verify this refund manually through CinetPay dashboard or support.",
                raw_response={
                    "refund_reference": provider_refund_id,
                    "note": "Manual verification required"
                }
            )
            
        except Exception as e:
            logger.error(f"CinetPay refund verification error: {str(e)}")
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=payment_id,
                provider_refund_id=provider_refund_id,
                status=RefundStatus.FAILED.value,
                message=f"Refund verification failed: {str(e)}",
                raw_response={"error": str(e)}
            )

    async def create_subscription(self, subscription_request: SubscriptionRequest) -> SubscriptionResponse:
        """
        Create a subscription with CinetPay.
        
        Args:
            subscription_request: Subscription request details
            
        Returns:
            Subscription response with subscription details
        """
        try:
            # CinetPay doesn't have a direct subscription API
            # We'll implement this by creating a normal payment first,
            # and then storing subscription details for future payments
            
            # Create a payment request for the first payment
            payment_request = PaymentRequest(
                payment_id=subscription_request.subscription_id,
                amount=subscription_request.amount,
                currency=subscription_request.currency,
                description=subscription_request.description or "Subscription payment",
                customer_email=subscription_request.customer_email,
                customer_name=subscription_request.customer_name,
                customer_phone=subscription_request.customer_phone,
                request_metadata={
                    "subscription_id": subscription_request.subscription_id,
                    "is_subscription": True,
                    "subscription_period": subscription_request.interval,
                    "billing_cycle": subscription_request.interval,
                    "autorenew": subscription_request.auto_renew,
                    "start_date": datetime.now().isoformat(),
                    "custom_data": subscription_request.metadata
                }
            )
            
            # Process the initial payment
            payment_response = await self.process_payment(payment_request)
            
            if not payment_response.success:
                logger.error(f"Failed to create initial payment for subscription: {payment_response.message}")
                return SubscriptionResponse(
                    provider_id=self.provider_id,
                    subscription_id=subscription_request.subscription_id,
                    status=SubscriptionStatus.FAILED.value,
                    message=f"Failed to create subscription: {payment_response.message}",
                    raw_response=payment_response.raw_response
                )
            
            # Generate a subscription reference
            subscription_ref = f"SUB-{int(time.time())}-{subscription_request.subscription_id}"
            
            # For subscription, we need to return the payment URL for the first payment
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_request.subscription_id,
                provider_subscription_id=subscription_ref,
                redirect_url=payment_response.redirect_url,
                status=SubscriptionStatus.ACTIVE.value,
                message="Subscription created. Customer must complete the first payment.",
                amount=subscription_request.amount,
                currency=subscription_request.currency,
                interval=subscription_request.interval,
                provider_payment_id=payment_response.provider_payment_id,
                next_payment_date=(datetime.now() + self._get_interval_timedelta(subscription_request.interval)).isoformat(),
                raw_response={
                    "subscription_reference": subscription_ref,
                    "initial_payment": payment_response.raw_response,
                    "note": "Manual renewal required for future payments"
                }
            )
            
        except Exception as e:
            logger.error(f"CinetPay subscription creation error: {str(e)}")
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_request.subscription_id,
                status=SubscriptionStatus.FAILED.value,
                message=f"Subscription creation failed: {str(e)}",
                raw_response={"error": str(e)}
            )

    def _get_interval_timedelta(self, interval: str) -> timedelta:
        """Convert interval string to timedelta."""
        interval = interval.lower()
        if interval == "daily":
            return timedelta(days=1)
        elif interval == "weekly":
            return timedelta(weeks=1)
        elif interval == "monthly":
            return timedelta(days=30)
        elif interval == "quarterly":
            return timedelta(days=90)
        elif interval == "biannual":
            return timedelta(days=182)
        elif interval == "annual":
            return timedelta(days=365)
        else:
            return timedelta(days=30)  # Default to monthly
    
    async def update_subscription(self, provider_subscription_id: str, metadata: Dict[str, Any] = None, 
                                  auto_renew: bool = None, subscription_id: str = None) -> SubscriptionResponse:
        """
        Update a subscription with CinetPay.
        
        Args:
            provider_subscription_id: CinetPay subscription reference
            metadata: Optional updated metadata
            auto_renew: Optional updated auto_renew setting
            subscription_id: Optional internal subscription ID
            
        Returns:
            Subscription response with update status
        """
        try:
            # CinetPay doesn't have a direct subscription API
            # We'll return a success response with updated metadata for our records
            
            response_metadata = {}
            if metadata is not None:
                response_metadata["metadata"] = metadata
                
            if auto_renew is not None:
                response_metadata["auto_renew"] = auto_renew
                
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.ACTIVE.value,
                message="Subscription updated in local records. Note: Changes are only reflected locally.",
                raw_response=response_metadata
            )
            
        except Exception as e:
            logger.error(f"CinetPay subscription update error: {str(e)}")
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.FAILED.value,
                message=f"Subscription update failed: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    async def cancel_subscription(self, provider_subscription_id: str, subscription_id: str = None) -> SubscriptionResponse:
        """
        Cancel a subscription with CinetPay.
        
        Args:
            provider_subscription_id: CinetPay subscription reference
            subscription_id: Optional internal subscription ID
            
        Returns:
            Subscription response with cancellation status
        """
        try:
            # CinetPay doesn't have a direct subscription API
            # We'll return a success response for our records
            
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.CANCELLED.value,
                message="Subscription cancelled in local records. No further payments will be processed.",
                raw_response={"status": "cancelled"}
            )
            
        except Exception as e:
            logger.error(f"CinetPay subscription cancellation error: {str(e)}")
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.FAILED.value,
                message=f"Subscription cancellation failed: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    async def pause_subscription(self, provider_subscription_id: str, subscription_id: str = None) -> SubscriptionResponse:
        """
        Pause a subscription with CinetPay.
        
        Args:
            provider_subscription_id: CinetPay subscription reference
            subscription_id: Optional internal subscription ID
            
        Returns:
            Subscription response with pause status
        """
        try:
            # CinetPay doesn't have a direct subscription API
            # We'll return a success response for our records
            
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.PAUSED.value,
                message="Subscription paused in local records. No payments will be processed until resumed.",
                raw_response={"status": "paused"}
            )
            
        except Exception as e:
            logger.error(f"CinetPay subscription pause error: {str(e)}")
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.FAILED.value,
                message=f"Subscription pause failed: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    async def resume_subscription(self, provider_subscription_id: str, subscription_id: str = None) -> SubscriptionResponse:
        """
        Resume a paused subscription with CinetPay.
        
        Args:
            provider_subscription_id: CinetPay subscription reference
            subscription_id: Optional internal subscription ID
            
        Returns:
            Subscription response with resume status
        """
        try:
            # CinetPay doesn't have a direct subscription API
            # We'll return a success response for our records
            
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.ACTIVE.value,
                message="Subscription resumed in local records. Payments will be processed on schedule.",
                raw_response={"status": "active"}
            )
            
        except Exception as e:
            logger.error(f"CinetPay subscription resume error: {str(e)}")
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.FAILED.value,
                message=f"Subscription resume failed: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    async def get_subscription(self, provider_subscription_id: str, subscription_id: str = None) -> SubscriptionResponse:
        """
        Get subscription details from CinetPay.
        
        Args:
            provider_subscription_id: CinetPay subscription reference
            subscription_id: Optional internal subscription ID
            
        Returns:
            Subscription response with subscription details
        """
        try:
            # CinetPay doesn't have a direct subscription API
            # We'll return a generic response for our records
            
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.ACTIVE.value,
                message="Subscription details retrieved from local records. Note: This doesn't reflect actual status in CinetPay.",
                raw_response={"provider_subscription_id": provider_subscription_id}
            )
            
        except Exception as e:
            logger.error(f"CinetPay subscription details retrieval error: {str(e)}")
            return SubscriptionResponse(
                provider_id=self.provider_id,
                subscription_id=subscription_id,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.FAILED.value,
                message=f"Failed to retrieve subscription details: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    async def list_customer_subscriptions(self, customer_email: str) -> List[SubscriptionResponse]:
        """
        List subscriptions for a customer with CinetPay.
        
        Args:
            customer_email: Customer email
            
        Returns:
            List of subscription responses
        """
        try:
            # CinetPay doesn't have a direct subscription API
            # We'll return an empty list since we can't query by customer email
            
            return []
            
        except Exception as e:
            logger.error(f"CinetPay customer subscriptions listing error: {str(e)}")
            return []
            
    async def handle_webhook(self, data: Dict[str, Any], headers: Dict[str, str]) -> ProviderResponse:
        """
        Handle webhook notifications from CinetPay.
        
        Args:
            data: Webhook data
            headers: Request headers
            
        Returns:
            Provider response
        """
        try:
            logger.info(f"Received CinetPay webhook: {data}")
            
            # Verify webhook signature if available
            signature_header = headers.get("x-cinetpay-signature")
            if signature_header and self._get_credentials().get("webhook_secret"):
                is_valid = self._verify_webhook_signature(data, signature_header)
                if not is_valid:
                    logger.error("Invalid CinetPay webhook signature")
                    return ProviderResponse(
                        provider_id=self.provider_id,
                        message="Invalid webhook signature",
                        raw_response={"error": "Invalid signature"}
                    )
            
            # Extract transaction ID and data
            transaction_id = data.get("transaction_id")
            if not transaction_id:
                logger.error("Missing transaction_id in CinetPay webhook")
                return ProviderResponse(
                    provider_id=self.provider_id,
                    message="Missing transaction_id in webhook data",
                    raw_response={"error": "Missing transaction_id"}
                )
            
            cpm_trans_status = data.get("cpm_trans_status")
            cpm_error_message = data.get("cpm_error_message")
            
            # Extract payment ID from metadata if available
            metadata = data.get("metadata", {})
            payment_id = metadata.get("payment_id")
            
            # Map CinetPay status to internal status
            if cpm_trans_status == "ACCEPTED":
                payment_status = PaymentStatus.COMPLETED.value
                success = True
                message = "Payment completed successfully"
            elif cpm_trans_status == "PENDING":
                payment_status = PaymentStatus.PENDING.value
                success = True
                message = "Payment is pending"
            elif cpm_trans_status == "CANCELED":
                payment_status = PaymentStatus.CANCELLED.value
                success = False
                message = "Payment was cancelled"
            elif cpm_trans_status == "REFUSED":
                payment_status = PaymentStatus.FAILED.value
                success = False
                message = f"Payment was refused: {cpm_error_message or 'Unknown reason'}"
            else:
                payment_status = PaymentStatus.FAILED.value
                success = False
                message = f"Payment failed with status: {cpm_trans_status}"
            
            # Get amount and currency from the webhook data
            amount = None
            try:
                amount = float(data.get("amount", 0)) / 100  # Convert from cents
            except (ValueError, TypeError):
                pass
            
            currency = data.get("currency")
            
            # Create security audit log
            self.log_payment_transaction(
                payment_id or transaction_id,
                {
                    "transaction_id": transaction_id,
                    "amount": amount,
                    "currency": currency,
                    "status": payment_status
                },
                "webhook_notification"
            )
            
            # Return provider response
            return ProviderResponse(
                provider_id=self.provider_id,
                payment_id=payment_id,
                provider_payment_id=transaction_id,
                status=payment_status,
                message=message,
                amount=amount,
                currency=currency,
                raw_response=data
            )
            
        except Exception as e:
            logger.error(f"CinetPay webhook processing error: {str(e)}")
            return ProviderResponse(
                provider_id=self.provider_id,
                message=f"Webhook processing failed: {str(e)}",
                raw_response={"error": str(e)}
            )
    
    def _verify_webhook_signature(self, data: Dict[str, Any], signature: str) -> bool:
        """
        Verify the signature of a webhook notification.
        
        Args:
            data: Webhook payload data
            signature: Signature from webhook headers
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Get webhook secret from credentials
            credentials = self._get_credentials()
            webhook_secret = credentials.get("webhook_secret", "")
            
            if not webhook_secret:
                logger.warning("Webhook secret not configured for CinetPay")
                return False
                
            # Prepare payload for signature verification
            # CinetPay uses the entire JSON payload to generate the signature
            payload = json.dumps(data, separators=(',', ':'), sort_keys=True)
            
            # Calculate HMAC with SHA256
            expected_signature = hmac.new(
                webhook_secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Verify signature matches
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying CinetPay webhook signature: {str(e)}")
            return False
            
    def validate_payment_request(self, payment_request: PaymentRequest) -> bool:
        """
        Validate a payment request.
        
        Args:
            payment_request: Payment request to validate
            
        Returns:
            True if the request is valid, False otherwise
        """
        if not payment_request:
            return False
            
        # Check required fields
        if not payment_request.payment_id:
            logger.error("Missing payment_id in payment request")
            return False
            
        if not payment_request.amount or payment_request.amount <= 0:
            logger.error(f"Invalid amount ({payment_request.amount}) in payment request")
            return False
            
        if not payment_request.currency:
            logger.error("Missing currency in payment request")
            return False
            
        # Validate currency code (CinetPay supports a limited set of currencies)
        supported_currencies = ['XOF', 'XAF', 'CDF', 'GNF', 'USD', 'EUR']
        if payment_request.currency.upper() not in supported_currencies:
            logger.error(f"Unsupported currency ({payment_request.currency}) for CinetPay")
            return False
            
        return True
        
    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive data in the request.
        
        Args:
            data: Data containing potentially sensitive information
            
        Returns:
            Dictionary with sensitive data encrypted
        """
        # Skip if no data
        if not data:
            return {}
            
        # Define sensitive fields to encrypt
        sensitive_fields = [
            'card_number', 'cvv', 'expiry', 'card_holder', 
            'phone', 'personal_info', 'address', 'id_number'
        ]
        
        # Create a copy of the data
        encrypted_data = data.copy()
        
        # Encrypt sensitive fields
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.security.encrypt_data(encrypted_data[field])
                
        return encrypted_data
        
    def log_payment_transaction(self, payment_id: str, data: Dict[str, Any], event_type: str) -> None:
        """
        Log a payment transaction event.
        
        Args:
            payment_id: Payment ID
            data: Transaction data
            event_type: Event type (initiated, completed, failed, etc.)
        """
        # Add standard fields
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "provider": self.provider_id,
            "event_type": event_type,
            "payment_id": payment_id,
            **data
        }
        
        # Log event
        logger.info(f"Payment transaction event: {event_type} for payment {payment_id}")
        
        # Store in transaction history if needed
        try:
            # The transaction will be stored in the database by the payment service
            # We just prepare the data here
            transaction_data = {
                "provider": self.provider_id,
                "event_type": event_type,
                "transaction_metadata": data  # Changed from "metadata" to "transaction_metadata"
            }
            
            # Log transaction data for debugging
            logger.debug(f"Transaction data: {json.dumps(transaction_data)}")
        except Exception as e:
            logger.exception(f"Error logging payment transaction: {e}")
            
    def log_refund_transaction(self, payment_id: str, refund_id: str, data: Dict[str, Any], event_type: str) -> None:
        """
        Log a refund transaction event.
        
        Args:
            payment_id: Payment ID
            refund_id: Refund ID
            data: Refund data
            event_type: Event type (initiated, completed, failed, etc.)
        """
        # Add standard fields
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "provider": self.provider_id,
            "event_type": event_type,
            "payment_id": payment_id,
            "refund_id": refund_id,
            **data
        }
        
        # Log event
        logger.info(f"Refund transaction event: {event_type} for payment {payment_id}, refund {refund_id}")
        
        # Store in transaction history if needed
        try:
            # The transaction will be stored in the database by the payment service
            # We just prepare the data here
            transaction_data = {
                "provider": self.provider_id,
                "event_type": event_type,
                "refund_id": refund_id,
                "refund_metadata": data  # Changed from "metadata" to "refund_metadata"
            }
            
            # Log transaction data for debugging
            logger.debug(f"Refund transaction data: {json.dumps(transaction_data)}")
        except Exception as e:
            logger.exception(f"Error logging refund transaction: {e}")
