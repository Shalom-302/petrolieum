"""
PayStack payment provider implementation.

This module implements the PayStack payment provider interface.
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

logger = logging.getLogger("kaapi.payment.paystack")


@PaymentProviderFactory.register
class PaystackProvider(BasePaymentProvider):
    """PayStack payment provider implementation."""

    provider_id = "paystack"
    provider_name = "PayStack"
    logo_url = "https://website-v3-assets.s3.amazonaws.com/assets/img/hero/Paystack-mark-white-twitter.png"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize a PayStack payment provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        
        # Initialize with needed credentials
        self.secret_key = config.get("secret_key", "")
        self.public_key = config.get("public_key", "")
        
        self.api_base_url = "https://api.paystack.co"
        self.webhook_secret = config.get("webhook_secret", "")
        
        # Callbacks
        self.callback_url = config.get("callback_url", "")
        
        logger.info("PayStack payment provider initialized")
    
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
        return "PayStack payment processing service for Africa"
    
    @property
    def supported_methods(self) -> List[str]:
        """Get supported payment methods."""
        return ["card", "bank_transfer", "mobile_money", "ussd"]
    
    @property
    def supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        return ["NGN", "GHS", "USD", "ZAR"]
    
    @property
    def supported_countries(self) -> List[str]:
        """Get supported countries."""
        return ["NG", "GH", "ZA", "KE"]
    
    @property
    def supports_subscriptions(self) -> bool:
        """Whether this provider supports subscriptions."""
        return True
        
    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through PayStack.
        
        Args:
            payment_request: Payment request details
            
        Returns:
            Provider response with payment details
        """
        try:
            # Validate the payment request for PCI compliance
            if not self.validate_payment_request(payment_request):
                logger.error("Payment validation failed")
                return ProviderResponse(
                    success=False,
                    status=PaymentStatus.FAILED,
                    provider_reference="",
                    message="Payment validation failed",
                    raw_response={"error": "validation_failed"}
                )
                
            # Prepare the payment data for PayStack
            payment_data = {
                "amount": int(payment_request.amount * 100),  # PayStack amount is in kobo (1/100 of currency)
                "email": payment_request.customer_email,
                "currency": payment_request.currency,
                "callback_url": self.callback_url,
                "metadata": {
                    "order_id": payment_request.order_id,
                    "customer_id": payment_request.customer_id,
                    "custom_fields": payment_request.metadata if payment_request.metadata else {}
                }
            }
            
            # Encrypt sensitive metadata before processing
            if payment_request.metadata:
                encrypted_metadata = self.encrypt_sensitive_data(payment_request.metadata)
                payment_data["metadata"]["custom_fields"] = encrypted_metadata
            
            # Add reference if provided
            if payment_request.reference:
                payment_data["reference"] = payment_request.reference
                
            # Add payment method if specified
            if payment_request.payment_method:
                payment_data["channels"] = [payment_request.payment_method]
            
            # Initialize the payment
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/transaction/initialize",
                    headers=headers,
                    json=payment_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("status"):
                        logger.error(f"PayStack payment error: {result}")
                        return ProviderResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference="",
                            message=result.get("message", "Payment initialization failed"),
                            raw_response=result
                        )
                    
                    # Extract important data from the response
                    data = result.get("data", {})
                    authorization_url = data.get("authorization_url")
                    reference = data.get("reference")
                    
                    # Log successful payment transaction
                    payment_log_data = {
                        "amount": payment_request.amount,
                        "currency": payment_request.currency,
                        "customer_id": payment_request.customer_id,
                        "reference": reference
                    }
                    self.log_payment_transaction(reference, payment_log_data, "initialized")
                    
                    return ProviderResponse(
                        success=True,
                        status=PaymentStatus.PENDING,
                        provider_reference=reference,
                        message="Payment initialized successfully",
                        raw_response=result,
                        redirect_url=authorization_url
                    )
                    
        except Exception as e:
            logger.error(f"PayStack payment error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def verify_payment(self, reference: str) -> ProviderResponse:
        """
        Verify a payment with PayStack.
        
        Args:
            reference: Provider reference to verify
            
        Returns:
            Provider response with payment status
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/transaction/verify/{reference}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("status"):
                        logger.error(f"PayStack verification error: {result}")
                        return ProviderResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference=reference,
                            message=result.get("message", "Payment verification failed"),
                            raw_response=result
                        )
                    
                    # Extract data from the response
                    data = result.get("data", {})
                    status = data.get("status")
                    
                    # Map PayStack status to our status
                    payment_status = self._map_paystack_status_to_internal(status)
                    
                    # Get amount and currency
                    amount = data.get("amount", 0) / 100  # Convert from kobo
                    currency = data.get("currency", "NGN")
                    
                    # Extract metadata if available
                    metadata = data.get("metadata", {})
                    order_id = metadata.get("order_id") if metadata else None
                    
                    # Log successful payment verification
                    payment_log_data = {
                        "amount": amount,
                        "currency": currency,
                        "customer_id": metadata.get("customer_id"),
                        "reference": reference
                    }
                    self.log_payment_transaction(reference, payment_log_data, "verified")
                    
                    return ProviderResponse(
                        success=payment_status == PaymentStatus.SUCCESS,
                        status=payment_status,
                        provider_reference=reference,
                        message=f"Payment {payment_status.value}",
                        raw_response=result,
                        amount=amount,
                        currency=currency,
                        order_id=order_id
                    )
                    
        except Exception as e:
            logger.error(f"PayStack verification error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.UNKNOWN,
                provider_reference=reference,
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def cancel_payment(self, reference: str) -> ProviderResponse:
        """
        Cancel a payment with PayStack.
        
        Args:
            reference: Provider reference to cancel
            
        Returns:
            Provider response with cancellation result
        """
        # PayStack doesn't have a direct API to cancel transactions
        # We can only verify the transaction and return if it's not completed
        try:
            verification = await self.verify_payment(reference)
            
            if verification.status != PaymentStatus.SUCCESS:
                # If the payment is not successful, we consider it "canceled"
                return ProviderResponse(
                    success=True,
                    status=PaymentStatus.CANCELLED,
                    provider_reference=reference,
                    message="Payment not completed, considered canceled",
                    raw_response=verification.raw_response
                )
            else:
                # If the payment is already successful, it can't be canceled
                return ProviderResponse(
                    success=False,
                    status=PaymentStatus.SUCCESS,
                    provider_reference=reference,
                    message="Payment already successful, cannot be canceled",
                    raw_response=verification.raw_response
                )
                
        except Exception as e:
            logger.error(f"PayStack cancellation error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.UNKNOWN,
                provider_reference=reference,
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def process_refund(self, refund_request: RefundRequest) -> ProviderResponse:
        """
        Process a refund through PayStack.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Provider response with refund details
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            refund_data = {
                "transaction": refund_request.payment_reference,
                "amount": int(refund_request.amount * 100) if refund_request.amount else None
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/refund",
                    headers=headers,
                    json=refund_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("status"):
                        logger.error(f"PayStack refund error: {result}")
                        return ProviderResponse(
                            success=False,
                            status=RefundStatus.FAILED,
                            provider_reference=refund_request.payment_reference,
                            message=result.get("message", "Refund failed"),
                            raw_response=result
                        )
                    
                    # Extract data from the response
                    data = result.get("data", {})
                    refund_reference = data.get("reference")
                    refund_status = data.get("status")
                    
                    # Map PayStack refund status to our status
                    internal_status = self._map_paystack_refund_status_to_internal(refund_status)
                    
                    # Log successful refund transaction
                    refund_log_data = {
                        "amount": refund_request.amount,
                        "currency": refund_request.currency,
                        "customer_id": refund_request.customer_id,
                        "reference": refund_reference
                    }
                    self.log_refund_transaction(refund_reference, refund_log_data, "processed")
                    
                    return ProviderResponse(
                        success=True,
                        status=internal_status,
                        provider_reference=refund_reference,
                        message=f"Refund {internal_status.value}",
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"PayStack refund error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=RefundStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def verify_refund(self, reference: str) -> ProviderResponse:
        """
        Verify a refund with PayStack.
        
        Args:
            reference: Provider reference to verify
            
        Returns:
            Provider response with refund status
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/refund/{reference}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("status"):
                        logger.error(f"PayStack refund verification error: {result}")
                        return ProviderResponse(
                            success=False,
                            status=RefundStatus.FAILED,
                            provider_reference=reference,
                            message=result.get("message", "Refund verification failed"),
                            raw_response=result
                        )
                    
                    # Extract data from the response
                    data = result.get("data", {})
                    refund_status = data.get("status")
                    
                    # Map PayStack refund status to our status
                    internal_status = self._map_paystack_refund_status_to_internal(refund_status)
                    
                    # Log successful refund verification
                    refund_log_data = {
                        "amount": data.get("amount", 0) / 100,
                        "currency": data.get("currency", "NGN"),
                        "customer_id": data.get("customer", {}).get("customer_id"),
                        "reference": reference
                    }
                    self.log_refund_transaction(reference, refund_log_data, "verified")
                    
                    return ProviderResponse(
                        success=internal_status != RefundStatus.FAILED,
                        status=internal_status,
                        provider_reference=reference,
                        message=f"Refund {internal_status.value}",
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"PayStack refund verification error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=RefundStatus.UNKNOWN,
                provider_reference=reference,
                message=str(e),
                raw_response={"error": str(e)}
            )
            
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Handle webhook data from PayStack.
        
        Args:
            payload: Webhook payload
            headers: Webhook headers
            
        Returns:
            Processed webhook data or None if not applicable
        """
        try:
            # Verify webhook signature
            signature = headers.get("x-paystack-signature")
            if not signature or not self._verify_webhook_signature(signature, payload):
                logger.warning("Invalid PayStack webhook signature")
                return None
                
            # Process based on event type
            event_type = payload.get("event")
            data = payload.get("data", {})
            
            if event_type == "charge.success":
                # Handle successful payment
                return {
                    "type": "payment",
                    "action": "success",
                    "reference": data.get("reference"),
                    "amount": data.get("amount", 0) / 100,  # Convert from kobo
                    "currency": data.get("currency", "NGN"),
                    "customer_email": data.get("customer", {}).get("email"),
                    "metadata": data.get("metadata", {})
                }
            elif event_type == "charge.failed":
                # Handle failed payment
                return {
                    "type": "payment",
                    "action": "failed",
                    "reference": data.get("reference"),
                    "amount": data.get("amount", 0) / 100,
                    "currency": data.get("currency", "NGN"),
                    "customer_email": data.get("customer", {}).get("email"),
                    "metadata": data.get("metadata", {})
                }
            elif event_type == "refund.processed":
                # Handle processed refund
                return {
                    "type": "refund",
                    "action": "processed",
                    "reference": data.get("reference"),
                    "payment_reference": data.get("transaction_reference"),
                    "amount": data.get("amount", 0) / 100,
                    "currency": data.get("currency", "NGN")
                }
            elif event_type == "subscription.create":
                # Handle new subscription
                return {
                    "type": "subscription",
                    "action": "created",
                    "reference": data.get("subscription_code"),
                    "customer_email": data.get("customer", {}).get("email"),
                    "plan": data.get("plan", {}).get("name")
                }
            elif event_type == "subscription.disable":
                # Handle disabled/canceled subscription
                return {
                    "type": "subscription",
                    "action": "canceled",
                    "reference": data.get("subscription_code"),
                    "customer_email": data.get("customer", {}).get("email")
                }
            
            # Return raw payload for unhandled events
            return {
                "type": "unhandled",
                "event": event_type,
                "data": data
            }
                
        except Exception as e:
            logger.error(f"PayStack webhook error: {str(e)}")
            return None
    
    def _verify_webhook_signature(self, signature: str, payload: Dict[str, Any]) -> bool:
        """
        Verify PayStack webhook signature.
        
        Args:
            signature: The signature from the webhook header
            payload: The webhook payload
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("No webhook secret configured for PayStack")
            return False
            
        try:
            # Convert payload to string
            payload_string = json.dumps(payload)
            
            # Create HMAC signature
            computed_hmac = hmac.new(
                self.webhook_secret.encode("utf-8"),
                payload_string.encode("utf-8"),
                hashlib.sha512
            ).hexdigest()
            
            return computed_hmac == signature
            
        except Exception as e:
            logger.error(f"Error verifying PayStack webhook signature: {str(e)}")
            return False
    
    def _map_paystack_status_to_internal(self, status: str) -> PaymentStatus:
        """
        Map PayStack payment status to internal status.
        
        Args:
            status: PayStack payment status
            
        Returns:
            Internal payment status
        """
        status_map = {
            "success": PaymentStatus.SUCCESS,
            "failed": PaymentStatus.FAILED,
            "abandoned": PaymentStatus.FAILED,
            "pending": PaymentStatus.PENDING,
            "reversed": PaymentStatus.REFUNDED
        }
        
        return status_map.get(status.lower(), PaymentStatus.UNKNOWN)
    
    def _map_paystack_refund_status_to_internal(self, status: str) -> RefundStatus:
        """
        Map PayStack refund status to internal status.
        
        Args:
            status: PayStack refund status
            
        Returns:
            Internal refund status
        """
        status_map = {
            "pending": RefundStatus.PENDING,
            "processing": RefundStatus.PENDING,
            "success": RefundStatus.SUCCESS,
            "failed": RefundStatus.FAILED,
            "completed": RefundStatus.SUCCESS
        }
        
        return status_map.get(status.lower(), RefundStatus.UNKNOWN)

    async def create_subscription(self, subscription: SubscriptionRequest) -> SubscriptionResponse:
        """
        Create a new subscription with PayStack.
        
        Args:
            subscription: Subscription data
            
        Returns:
            Subscription response with provider data
        """
        try:
            # First check if we need to create a customer
            customer_code = await self._get_or_create_customer(subscription.customer_email)
            
            # Create or get a plan
            plan_code = await self._create_or_get_plan(
                subscription.name,
                subscription.description,
                subscription.amount,
                subscription.currency,
                subscription.billing_period,
                subscription.billing_interval
            )
            
            if not plan_code:
                logger.error("Failed to create or get PayStack plan")
                raise ValueError("Failed to create PayStack plan")
            
            # Create the subscription
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            subscription_data = {
                "customer": customer_code,
                "plan": plan_code,
                "start_date": datetime.now().strftime("%Y-%m-%d") if not subscription.start_date else subscription.start_date.strftime("%Y-%m-%d")
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/subscription",
                    headers=headers,
                    json=subscription_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("status"):
                        logger.error(f"PayStack subscription error: {result}")
                        raise ValueError(f"Failed to create subscription: {result.get('message', 'Unknown error')}")
                    
                    data = result.get("data", {})
                    
                    # Map status
                    status = self._map_paystack_subscription_status_to_internal(data.get("status"))
                    
                    # Prepare response
                    response = SubscriptionResponse(
                        id=0,  # Will be set by database
                        name=subscription.name,
                        description=subscription.description,
                        status=status,
                        amount=subscription.amount,
                        currency=subscription.currency,
                        billing_period=subscription.billing_period,
                        billing_interval=subscription.billing_interval,
                        customer_id=subscription.customer_id,
                        customer_email=subscription.customer_email,
                        created_by_id=subscription.created_by_id,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        start_date=subscription.start_date or datetime.now(),
                        end_date=None,
                        next_billing_date=None,  # PayStack doesn't provide this directly
                        trial_enabled=subscription.trial_enabled,
                        trial_start_date=subscription.trial_start_date,
                        trial_end_date=subscription.trial_end_date,
                        payment_method_id=None,
                        payment_provider="paystack",
                        provider_subscription_id=data.get("subscription_code"),
                        auto_renew=True,
                        metadata={
                            "paystack_customer_code": customer_code,
                            "paystack_plan_code": plan_code,
                            "paystack_email_token": data.get("email_token"),
                            **(subscription.metadata or {})
                        },
                        is_active=status == SubscriptionStatus.ACTIVE.value,
                        is_past_due=status == SubscriptionStatus.PAST_DUE.value,
                        is_canceled=status == SubscriptionStatus.CANCELED.value,
                        is_in_trial=subscription.trial_enabled and subscription.trial_end_date and subscription.trial_end_date > datetime.now(),
                        days_until_next_billing=None
                    )
                    
                    return response
        
        except Exception as e:
            logger.error(f"PayStack subscription error: {str(e)}")
            raise ValueError(f"Failed to create subscription: {str(e)}")
    
    async def update_subscription(self, subscription_id: str, update_data: SubscriptionRequest) -> SubscriptionResponse:
        """
        Update an existing subscription with PayStack.
        
        Note: PayStack doesn't provide many update options for subscriptions.
        The main update action is to enable/disable auto-renewal.
        
        Args:
            subscription_id: PayStack subscription code
            update_data: Data to update
            
        Returns:
            Updated subscription response
        """
        try:
            # Get current subscription
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            # Check if auto_renew is provided
            if update_data.auto_renew is not None:
                # Enable/disable subscription based on auto_renew
                action = "enable" if update_data.auto_renew else "disable"
                
                # PayStack doesn't allow enabling disabled subscriptions, so we need to check current status
                if action == "enable":
                    # Check current status first
                    subscription_data = await self.get_subscription(subscription_id)
                    if subscription_data.get("is_canceled") or not subscription_data.get("auto_renew"):
                        # We'd need to create a new subscription as PayStack doesn't allow re-enabling
                        logger.warning("PayStack doesn't support re-enabling canceled subscriptions. A new subscription would need to be created.")
            
                # Update subscription
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_base_url}/subscription/{action}",
                        headers=headers,
                        json={"code": subscription_id, "token": update_data.metadata.get("paystack_email_token") if update_data.metadata else None}
                    ) as response:
                        result = await response.json()
                        
                        if response.status != 200 or not result.get("status"):
                            logger.error(f"PayStack subscription update error: {result}")
                            raise ValueError(f"Failed to update subscription: {result.get('message', 'Unknown error')}")
            
            # Get updated subscription details
            subscription_data = await self.get_subscription(subscription_id)
            
            # Prepare response
            response = SubscriptionResponse(
                id=0,
                name=update_data.name,
                description=update_data.description,
                status=subscription_data.get("status"),
                amount=update_data.amount,
                currency=update_data.currency,
                billing_period=update_data.billing_period,
                billing_interval=update_data.billing_interval,
                customer_id=None,
                customer_email=None,
                created_by_id=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                start_date=subscription_data.get("start_date"),
                end_date=subscription_data.get("end_date"),
                next_billing_date=subscription_data.get("next_billing_date"),
                trial_enabled=False,
                trial_start_date=None,
                trial_end_date=None,
                payment_method_id=None,
                payment_provider="paystack",
                provider_subscription_id=subscription_id,
                auto_renew=subscription_data.get("auto_renew"),
                metadata=update_data.metadata,
                is_active=subscription_data.get("is_active"),
                is_past_due=subscription_data.get("is_past_due"),
                is_canceled=subscription_data.get("is_canceled"),
                is_in_trial=False,
                days_until_next_billing=None
            )
            
            return response
            
        except Exception as e:
            logger.error(f"PayStack subscription update error: {str(e)}")
            raise ValueError(f"Failed to update subscription: {str(e)}")
    
    async def cancel_subscription(self, subscription_id: str, cancel_request: SubscriptionRequest) -> SubscriptionResponse:
        """
        Cancel a subscription with PayStack.
        
        Args:
            subscription_id: PayStack subscription code
            cancel_request: Cancellation details
            
        Returns:
            Updated subscription response
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            # Disable the subscription (PayStack's way of canceling)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/subscription/disable",
                    headers=headers,
                    json={
                        "code": subscription_id,
                        "token": cancel_request.metadata.get("paystack_email_token") if cancel_request.metadata else None
                    }
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("status"):
                        logger.error(f"PayStack subscription cancel error: {result}")
                        raise ValueError(f"Failed to cancel subscription: {result.get('message', 'Unknown error')}")
            
            # Get subscription data for response
            subscription_data = await self.get_subscription(subscription_id)
            
            # Prepare response
            response = SubscriptionResponse(
                id=0,
                name="",
                description="",
                status=SubscriptionStatus.CANCELED.value,
                amount=0,
                currency="",
                billing_period="",
                billing_interval=0,
                customer_id=None,
                customer_email=None,
                created_by_id=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                start_date=subscription_data.get("start_date"),
                end_date=datetime.now(),
                next_billing_date=None,
                trial_enabled=False,
                trial_start_date=None,
                trial_end_date=None,
                payment_method_id=None,
                payment_provider="paystack",
                provider_subscription_id=subscription_id,
                auto_renew=False,
                metadata={"cancel_reason": cancel_request.reason} if cancel_request.reason else None,
                is_active=False,
                is_past_due=False,
                is_canceled=True,
                is_in_trial=False,
                days_until_next_billing=None
            )
            
            return response
                
        except Exception as e:
            logger.error(f"PayStack subscription cancel error: {str(e)}")
            raise ValueError(f"Failed to cancel subscription: {str(e)}")
    
    async def pause_subscription(self, subscription_id: str) -> SubscriptionResponse:
        """
        Pause a subscription with PayStack.
        
        Note: PayStack doesn't have a direct pause feature.
        Instead, we disable the subscription which is the equivalent of canceling.
        
        Args:
            subscription_id: PayStack subscription code
            
        Returns:
            Updated subscription response
        """
        try:
            logger.warning("PayStack doesn't support pausing subscriptions, disabling instead")
            
            # Use cancel subscription method as PayStack doesn't have pause
            cancel_request = SubscriptionRequest(reason="Paused by user")
            return await self.cancel_subscription(subscription_id, cancel_request)
                
        except Exception as e:
            logger.error(f"PayStack subscription pause error: {str(e)}")
            raise ValueError(f"Failed to pause subscription: {str(e)}")
    
    async def resume_subscription(self, subscription_id: str) -> SubscriptionResponse:
        """
        Resume a paused subscription with PayStack.
        
        Note: PayStack doesn't support resuming disabled subscriptions.
        A new subscription would need to be created.
        
        Args:
            subscription_id: PayStack subscription code
            
        Returns:
            Updated subscription response
        """
        try:
            logger.warning("PayStack doesn't support resuming subscriptions, a new subscription would need to be created")
            
            # Get current subscription details
            subscription_data = await self.get_subscription(subscription_id)
            
            # Return current data with appropriate message
            response = SubscriptionResponse(
                id=0,
                name="",
                description="",
                status=SubscriptionStatus.CANCELED.value,
                amount=0,
                currency="",
                billing_period="",
                billing_interval=0,
                customer_id=None,
                customer_email=None,
                created_by_id=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                start_date=subscription_data.get("start_date"),
                end_date=subscription_data.get("end_date"),
                next_billing_date=None,
                trial_enabled=False,
                trial_start_date=None,
                trial_end_date=None,
                payment_method_id=None,
                payment_provider="paystack",
                provider_subscription_id=subscription_id,
                auto_renew=False,
                metadata={"resume_error": "PayStack doesn't support resuming canceled subscriptions"},
                is_active=False,
                is_past_due=False,
                is_canceled=True,
                is_in_trial=False,
                days_until_next_billing=None
            )
            
            return response
                
        except Exception as e:
            logger.error(f"PayStack subscription resume error: {str(e)}")
            raise ValueError(f"Failed to resume subscription: {str(e)}")
    
    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details from PayStack.
        
        Args:
            subscription_id: PayStack subscription code
            
        Returns:
            Subscription details
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/subscription/{subscription_id}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("status"):
                        logger.error(f"PayStack get subscription error: {result}")
                        raise ValueError(f"Failed to get subscription: {result.get('message', 'Unknown error')}")
                    
                    data = result.get("data", {})
                    
                    # Map status
                    status = self._map_paystack_subscription_status_to_internal(data.get("status"))
                    
                    # Extract plan details
                    plan = data.get("plan", {})
                    amount = plan.get("amount", 0) / 100 if plan else 0
                    currency = plan.get("currency", "NGN") if plan else "NGN"
                    
                    # Determine dates
                    created_at = datetime.strptime(data.get("createdAt"), "%Y-%m-%dT%H:%M:%S.%fZ") if data.get("createdAt") else datetime.now()
                    
                    # PayStack doesn't provide next billing date directly
                    # Calculate approximate next billing based on interval
                    next_billing_date = None
                    if data.get("status") == "active" and plan:
                        interval = plan.get("interval")
                        if interval == "monthly":
                            next_billing_date = created_at.replace(month=created_at.month + 1)
                        elif interval == "yearly":
                            next_billing_date = created_at.replace(year=created_at.year + 1)
                        elif interval == "weekly":
                            next_billing_date = created_at + timedelta(days=7)
                        elif interval == "daily":
                            next_billing_date = created_at + timedelta(days=1)
                    
                    return {
                        "status": status,
                        "is_active": status == SubscriptionStatus.ACTIVE.value,
                        "is_past_due": status == SubscriptionStatus.PAST_DUE.value,
                        "is_canceled": status == SubscriptionStatus.CANCELED.value,
                        "is_in_trial": False,  # PayStack doesn't have trial period feature
                        "amount": amount,
                        "currency": currency,
                        "start_date": created_at,
                        "end_date": None,
                        "next_billing_date": next_billing_date,
                        "provider_subscription_id": data.get("subscription_code"),
                        "auto_renew": data.get("status") == "active",
                        "customer_email": data.get("customer", {}).get("email"),
                        "customer_code": data.get("customer", {}).get("customer_code")
                    }
                    
        except Exception as e:
            logger.error(f"PayStack get subscription error: {str(e)}")
            raise ValueError(f"Failed to get subscription: {str(e)}")
    
    async def list_customer_subscriptions(self, customer_email: str) -> List[Dict[str, Any]]:
        """
        List all subscriptions for a customer.
        
        Args:
            customer_email: Customer email address
            
        Returns:
            List of subscription details
        """
        try:
            # First get customer code
            customer_code = await self._get_customer_code(customer_email)
            
            if not customer_code:
                return []
            
            headers = {
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/subscription?customer={customer_code}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or not result.get("status") or not result.get("data"):
                        logger.error(f"PayStack list subscriptions error: {result}")
                        return []
                    
                    subscriptions = []
                    for item in result.get("data", []):
                        # Map status
                        status = self._map_paystack_subscription_status_to_internal(item.get("status"))
                        
                        # Extract plan details
                        plan = item.get("plan", {})
                        amount = plan.get("amount", 0) / 100 if plan else 0
                        currency = plan.get("currency", "NGN") if plan else "NGN"
                        
                        # Determine dates
                        created_at = datetime.strptime(item.get("createdAt"), "%Y-%m-%dT%H:%M:%S.%fZ") if item.get("createdAt") else datetime.now()
                        
                        subscription = {
                            "status": status,
                            "is_active": status == SubscriptionStatus.ACTIVE.value,
                            "is_past_due": status == SubscriptionStatus.PAST_DUE.value,
                            "is_canceled": status == SubscriptionStatus.CANCELED.value,
                            "is_in_trial": False,
                            "amount": amount,
                            "currency": currency,
                            "start_date": created_at,
                            "end_date": None,
                            "next_billing_date": None,
                            "provider_subscription_id": item.get("subscription_code"),
                            "auto_renew": item.get("status") == "active",
                            "customer_email": customer_email,
                            "customer_code": customer_code
                        }
                        
                        subscriptions.append(subscription)
                    
                    return subscriptions
                    
        except Exception as e:
            logger.error(f"PayStack list subscriptions error: {str(e)}")
            return []
    
    async def _get_or_create_customer(self, email: str) -> str:
        """
        Get or create a PayStack customer.
        
        Args:
            email: Customer email
            
        Returns:
            Customer code
        """
        # First try to get existing customer
        customer_code = await self._get_customer_code(email)
        
        if customer_code:
            return customer_code
        
        # Create new customer
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        customer_data = {
            "email": email
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/customer",
                headers=headers,
                json=customer_data
            ) as response:
                result = await response.json()
                
                if response.status != 200 or not result.get("status"):
                    logger.error(f"PayStack create customer error: {result}")
                    raise ValueError(f"Failed to create customer: {result.get('message', 'Unknown error')}")
                
                return result.get("data", {}).get("customer_code")
    
    async def _get_customer_code(self, email: str) -> Optional[str]:
        """
        Get PayStack customer code by email.
        
        Args:
            email: Customer email
            
        Returns:
            Customer code or None if not found
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_base_url}/customer?email={email}",
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status != 200 or not result.get("status") or not result.get("data"):
                    return None
                
                for customer in result.get("data", []):
                    if customer.get("email").lower() == email.lower():
                        return customer.get("customer_code")
                
                return None
    
    async def _create_or_get_plan(self, name: str, description: str, amount: float, currency: str, 
                                 billing_period: str, billing_interval: int) -> Optional[str]:
        """
        Create or get a PayStack plan.
        
        Args:
            name: Plan name
            description: Plan description
            amount: Plan amount
            currency: Plan currency
            billing_period: Billing period
            billing_interval: Billing interval
            
        Returns:
            Plan code or None if failed
        """
        # First check if plan exists
        plan_code = await self._get_plan_by_name(name, amount, currency)
        
        if plan_code:
            return plan_code
        
        # Create new plan
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        # Convert billing period to PayStack interval
        interval = self._map_billing_period_to_paystack_interval(billing_period)
        
        # Note: PayStack plans don't support multiple intervals (e.g., every 3 months)
        # If billing_interval > 1, we need to adjust accordingly
        if billing_interval > 1 and interval == "monthly":
            # Adjust amount for quarterly, biannual, etc.
            amount = amount * billing_interval
            
        plan_data = {
            "name": name,
            "description": description,
            "amount": int(amount * 100),  # Convert to kobo
            "interval": interval,
            "currency": currency
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/plan",
                headers=headers,
                json=plan_data
            ) as response:
                result = await response.json()
                
                if response.status != 200 or not result.get("status"):
                    logger.error(f"PayStack create plan error: {result}")
                    return None
                
                return result.get("data", {}).get("plan_code")
    
    async def _get_plan_by_name(self, name: str, amount: float, currency: str) -> Optional[str]:
        """
        Get PayStack plan by name and amount.
        
        Args:
            name: Plan name
            amount: Plan amount
            currency: Plan currency
            
        Returns:
            Plan code or None if not found
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_base_url}/plan?name={name}",
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status != 200 or not result.get("status") or not result.get("data"):
                    return None
                
                amount_in_kobo = int(amount * 100)
                
                for plan in result.get("data", []):
                    if (plan.get("name") == name and 
                        plan.get("amount") == amount_in_kobo and 
                        plan.get("currency") == currency):
                        return plan.get("plan_code")
                
                return None
    
    def _map_billing_period_to_paystack_interval(self, billing_period: str) -> str:
        """
        Map billing period to PayStack interval.
        
        Args:
            billing_period: Billing period
            
        Returns:
            PayStack interval
        """
        mapping = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "quarterly": "monthly",  # PayStack doesn't have quarterly, use monthly
            "biannual": "monthly",   # PayStack doesn't have biannual, use monthly
            "annual": "annually"
        }
        
        return mapping.get(billing_period.lower(), "monthly")
    
    def _map_paystack_subscription_status_to_internal(self, status: str) -> str:
        """
        Map PayStack subscription status to internal status.
        
        Args:
            status: PayStack subscription status
            
        Returns:
            Internal subscription status
        """
        mapping = {
            "active": SubscriptionStatus.ACTIVE.value,
            "cancelled": SubscriptionStatus.CANCELED.value,
            "completed": SubscriptionStatus.CANCELED.value,
            "non-renewing": SubscriptionStatus.CANCELED.value
        }
        
        return mapping.get(status.lower(), SubscriptionStatus.UNKNOWN.value)
