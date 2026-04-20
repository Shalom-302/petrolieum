"""
M-Pesa payment provider implementation.

This module implements the M-Pesa payment provider interface.
"""
import logging
import hashlib
import hmac
import json
import time
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union

import aiohttp

from ..models.payment import PaymentStatus, RefundStatus, RefundResponse
from ..models.provider import ProviderResponse, PaymentRequest, RefundRequest
from ..models.subscription import SubscriptionRequest, SubscriptionStatus, SubscriptionResponse
from .base_provider import BasePaymentProvider
from .provider_factory import PaymentProviderFactory

logger = logging.getLogger("kaapi.payment.mpesa")


@PaymentProviderFactory.register
class MPesaProvider(BasePaymentProvider):
    """M-Pesa payment provider implementation."""

    provider_id = "mpesa"
    provider_name = "M-Pesa"
    logo_url = "https://www.safaricom.co.ke/images/M-PESA_logo.png"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize an M-Pesa payment provider.
        
        Args:
            config: Provider configuration
        """
        super().__init__(config)
        
        # Initialize provider with needed credentials
        self.consumer_key = config.get("consumer_key", "")
        self.consumer_secret = config.get("consumer_secret", "")
        self.business_shortcode = config.get("business_shortcode", "")
        self.passkey = config.get("passkey", "")
        
        # API configuration
        self.mode = config.get("mode", "sandbox").lower()
        self.api_base_url = "https://api.safaricom.co.ke" if self.mode == "live" else "https://sandbox.safaricom.co.ke"
        
        # Callbacks
        self.callback_url = config.get("callback_url", "")
        self.timeout_url = config.get("timeout_url", "")
        
        logger.info(f"M-Pesa payment provider initialized with mode: {self.mode}")
            
    async def _get_access_token(self) -> str:
        """
        Get OAuth access token for M-Pesa API.
        
        Returns:
            Access token string
        """
        try:
            # Encode consumer key and secret
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/oauthgenerate?grant_type=client_credentials",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if "access_token" not in result:
                        raise ValueError("Failed to obtain access token")
                    
                    return result["access_token"]
                    
        except Exception as e:
            logger.error(f"Error getting M-Pesa access token: {str(e)}")
            raise

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
        return "M-Pesa mobile money payment service for East Africa"
    
    @property
    def supported_methods(self) -> List[str]:
        """Get supported payment methods."""
        return ["mobile_money", "ussd", "stk_push"]
    
    @property
    def supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        return ["KES", "TZS", "UGX"]
    
    @property
    def supported_countries(self) -> List[str]:
        """Get supported countries."""
        return ["KE", "TZ", "UG"]

    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through M-Pesa.
        
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
            
            # Create a copy with encrypted metadata
            secure_payment_request = PaymentRequest(
                payment_id=payment_request.payment_id,
                amount=payment_request.amount,
                currency=payment_request.currency,
                description=payment_request.description,
                customer_email=payment_request.customer_email,
                customer_name=payment_request.customer_name,
                customer_phone=payment_request.customer_phone,
                request_metadata=encrypted_metadata
            )
        
            # Check for required phone number
            if not secure_payment_request.customer_phone:
                raise ValueError("Phone number is required for M-Pesa payments")
            
            # Format phone number (ensure it starts with country code)
            phone = secure_payment_request.customer_phone
            if phone.startswith("+"):
                phone = phone[1:]  # Remove leading +
            if not phone.startswith("254"):  # Kenya country code
                if phone.startswith("0"):
                    phone = f"254{phone[1:]}"
                else:
                    phone = f"254{phone}"
            
            # Get access token
            access_token = await self._get_access_token()
            
            # Generate transaction timestamp
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            
            # Generate password (Base64 of shortcode + passkey + timestamp)
            password_str = f"{self.business_shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_str.encode()).decode()
            
            # Create unique transaction reference
            transaction_ref = f"MP-{int(time.time())}-{secure_payment_request.payment_id}"
            
            # Prepare STK push request
            stk_push_data = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(secure_payment_request.amount),
                "PartyA": phone,
                "PartyB": self.business_shortcode,
                "PhoneNumber": phone,
                "CallBackURL": self.callback_url,
                "AccountReference": transaction_ref,
                "TransactionDesc": secure_payment_request.description or "Payment"
            }
            
            # Make API request
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/mpesa/stkpushprocessrequest",
                    headers=headers,
                    json=stk_push_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or "ErrorCode" in result:
                        error_message = result.get("errorMessage", "Unknown error")
                        logger.error(f"M-Pesa STK push error: {error_message}")
                        return ProviderResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference="",
                            message=error_message,
                            raw_response=result
                        )
                    
                    # Process successful response
                    checkout_request_id = result.get("CheckoutRequestID")
                    merchant_request_id = result.get("MerchantRequestID")
                    
                    # Log successful payment initiation
                    payment_log_data = {
                        "amount": secure_payment_request.amount,
                        "currency": secure_payment_request.currency,
                        "phone": phone,
                        "checkout_request_id": checkout_request_id,
                        "merchant_request_id": merchant_request_id
                    }
                    self.log_payment_transaction(checkout_request_id, payment_log_data, "initiated")
                    
                    return ProviderResponse(
                        success=True,
                        status=PaymentStatus.PENDING,
                        provider_reference=checkout_request_id,
                        message="STK push initiated. Please check your phone to complete payment.",
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"M-Pesa payment error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )

    async def verify_payment(self, reference: str) -> ProviderResponse:
        """
        Verify a payment with M-Pesa.
        
        Args:
            reference: Provider reference to verify (CheckoutRequestID)
            
        Returns:
            Provider response with payment status
        """
        try:
            # Get access token
            access_token = await self._get_access_token()
            
            # Prepare verification request
            verify_data = {
                "BusinessShortCode": self.business_shortcode,
                "CheckoutRequestID": reference,
                "Timestamp": datetime.now().strftime("%Y%m%d%H%M%S"),
                "Password": base64.b64encode(
                    f"{self.business_shortcode}{self.passkey}{datetime.now().strftime('%Y%m%d%H%M%S')}".encode()
                ).decode()
            }
            
            # Make API request
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/mpesa/stkpushqueryquery",
                    headers=headers,
                    json=verify_data
                ) as response:
                    result = await response.json()
                    
                    # Check for errors
                    if response.status != 200 or "errorCode" in result:
                        error_message = result.get("errorMessage", "Unknown error")
                        logger.error(f"M-Pesa verification error: {error_message}")
                        return ProviderResponse(
                            success=False,
                            status=PaymentStatus.FAILED,
                            provider_reference=reference,
                            message=error_message,
                            raw_response=result
                        )
                    
                    # Get result code
                    result_code = result.get("ResultCode")
                    
                    # Determine payment status
                    payment_status = PaymentStatus.PENDING
                    if result_code == "0":
                        payment_status = PaymentStatus.SUCCESS
                    elif result_code == "1":
                        payment_status = PaymentStatus.FAILED
                    
                    # Log payment verification
                    verification_log_data = {
                        "checkout_request_id": reference,
                        "result_code": result_code,
                        "result_desc": result.get("ResultDesc", "")
                    }
                    self.log_payment_transaction(reference, verification_log_data, "verified")
                    
                    return ProviderResponse(
                        success=payment_status == PaymentStatus.SUCCESS,
                        status=payment_status,
                        provider_reference=reference,
                        message=result.get("ResultDesc", "Payment verification processed"),
                        raw_response=result
                    )
                    
        except Exception as e:
            logger.error(f"M-Pesa verification error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=PaymentStatus.UNKNOWN,
                provider_reference=reference,
                message=str(e),
                raw_response={"error": str(e)}
            )
    
    async def process_refund(self, refund_request: RefundRequest) -> ProviderResponse:
        """
        Process a refund request through M-Pesa.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Provider response with refund details
        """
        try:
            # M-Pesa doesn't have a direct API for refunds
            # Typically, this is done manually through the M-Pesa business portal
            # For the purpose of this implementation, we'll log the refund request
            
            # Log refund request
            refund_log_data = {
                "payment_reference": refund_request.payment_reference,
                "amount": refund_request.amount,
                "reason": refund_request.reason,
                "refund_metadata": refund_request.refund_metadata
            }
            self.log_refund_transaction(
                refund_request.refund_id, 
                refund_log_data, 
                "manual_processing_required"
            )
            
            # Return response indicating manual processing is required
            return ProviderResponse(
                success=True,
                status=RefundStatus.PENDING,
                provider_reference=refund_request.refund_id,
                message="Refund request recorded. Manual processing required.",
                raw_response={
                    "status": "manual_processing",
                    "refund_id": refund_request.refund_id,
                    "note": "M-Pesa refunds require manual processing via the M-Pesa business portal"
                }
            )
                    
        except Exception as e:
            logger.error(f"M-Pesa refund error: {str(e)}")
            return ProviderResponse(
                success=False,
                status=RefundStatus.FAILED,
                provider_reference="",
                message=str(e),
                raw_response={"error": str(e)}
            )
            
    def verify_webhook_signature(self, signature: str, payload: str) -> bool:
        """
        Verify webhook signature from M-Pesa.
        
        Args:
            signature: Signature from webhook request
            payload: Request body as string
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.passkey or not payload:
            logger.warning("Missing passkey or payload for webhook verification")
            return False
            
        try:
            # M-Pesa doesn't use traditional webhook signatures
            # Instead, we typically validate by checking specific fields in the payload
            # For additional security, we can implement custom signature validation
            
            payload_data = json.loads(payload)
            
            # Log webhook event for security auditing
            self.log_payment_transaction(
                payload_data.get("CheckoutRequestID", "unknown"),
                {
                    "webhook_event": payload_data,
                    "signature": signature
                },
                "webhook_received"
            )
            
            # Verify basic structure of payload
            if not payload_data.get("Body") or not payload_data.get("Body").get("stkCallback"):
                logger.error("Invalid webhook payload structure")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
