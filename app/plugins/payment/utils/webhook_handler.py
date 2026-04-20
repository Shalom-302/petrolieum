"""
Webhook handler for payment providers.

This module contains functions to handle webhooks from various payment providers.
"""
import logging
import hmac
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import Request, HTTPException, status, Depends

from app.core.db import get_db
from ..models.payment import PaymentDB, PaymentStatus, PaymentTransactionDB
from ..providers.provider_factory import PaymentProviderFactory
from .config import payment_settings

logger = logging.getLogger("kaapi.payment.webhook_handler")

async def handle_webhook(
    request: Request,
    provider_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Handle webhooks from payment providers."""
    # Get the raw webhook payload
    payload_bytes = await request.body()
    payload_str = payload_bytes.decode('utf-8')
    
    try:
        # Parse the payload as JSON if possible
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        # Some providers might not send JSON
        payload = {
            "raw_payload": payload_str,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers)
        }
    
    # Get the provider configuration
    provider_config = payment_settings.get_provider_config(provider_id)
    
    # Get the provider instance
    provider = PaymentProviderFactory.get_provider(provider_id)
    if not provider:
        logger.error(f"Unknown payment provider: {provider_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown payment provider: {provider_id}"
        )
    
    # Verify the webhook signature if applicable
    verification_result, verification_message = await _verify_webhook_signature(
        provider_id=provider_id,
        request=request,
        payload_bytes=payload_bytes,
        provider_config=provider_config
    )
    
    if not verification_result:
        logger.error(f"Webhook signature verification failed: {verification_message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook signature verification failed: {verification_message}"
        )
    
    # Log the webhook
    logger.info(f"Received webhook from {provider_id}: {payload}")
    
    # Extract payment information using the provider
    try:
        webhook_data = await provider.handle_webhook(payload, dict(request.headers))
        
        if not webhook_data:
            logger.warning(f"Provider {provider_id} returned empty webhook data")
            return {"status": "acknowledged"}
        
        # Process the webhook data
        await _process_webhook_data(db, provider_id, webhook_data)
        
        return {"status": "success", "message": "Webhook processed successfully"}
    
    except Exception as e:
        logger.error(f"Error processing webhook from {provider_id}: {e}")
        # We don't want to return an error to the provider, as they may retry
        # the webhook which could lead to duplicate processing
        return {"status": "acknowledged", "error": str(e)}

async def _verify_webhook_signature(
    provider_id: str,
    request: Request,
    payload_bytes: bytes,
    provider_config: Dict[str, Any]
) -> Tuple[bool, str]:
    """Verify the webhook signature."""
    # Different providers have different signature verification methods
    if provider_id == "flutterwave":
        return await _verify_flutterwave_signature(request, payload_bytes, provider_config)
    
    elif provider_id == "mpesa":
        # M-Pesa doesn't provide a way to verify webhook signatures
        # In a production environment, you would use IP whitelisting
        return True, "No signature verification for MPesa"
    
    elif provider_id == "stripe":
        return await _verify_stripe_signature(request, payload_bytes, provider_config)
    
    elif provider_id == "paypal":
        return await _verify_paypal_signature(request, payload_bytes, provider_config)
    
    elif provider_id == "paystack":
        return await _verify_paystack_signature(request, payload_bytes, provider_config)
    
    # For other providers, assume no signature verification
    return True, "No signature verification for this provider"

async def _verify_flutterwave_signature(
    request: Request,
    payload_bytes: bytes,
    provider_config: Dict[str, Any]
) -> Tuple[bool, str]:
    """Verify Flutterwave webhook signature."""
    webhook_secret = provider_config.get("webhook_secret")
    if not webhook_secret:
        logger.warning("Flutterwave webhook secret not configured")
        return True, "Webhook secret not configured"
    
    # Get the signature from the headers
    signature = request.headers.get("verif-hash")
    if not signature:
        return False, "No signature provided in headers"
    
    # Verify the signature
    if signature != webhook_secret:
        return False, "Invalid signature"
    
    return True, "Signature verified"

async def _verify_stripe_signature(
    request: Request,
    payload_bytes: bytes,
    provider_config: Dict[str, Any]
) -> Tuple[bool, str]:
    """Verify Stripe webhook signature."""
    webhook_secret = provider_config.get("webhook_secret")
    if not webhook_secret:
        logger.warning("Stripe webhook secret not configured")
        return True, "Webhook secret not configured"
    
    # Get the signature from the headers
    stripe_signature = request.headers.get("stripe-signature")
    if not stripe_signature:
        return False, "No signature provided in headers"
    
    try:
        # Parse the signature header
        timestamp, signatures = None, None
        for item in stripe_signature.split(','):
            key, value = item.split('=', 1)
            if key == 't':
                timestamp = value
            elif key == 'v1':
                signatures = value
        
        if not timestamp or not signatures:
            return False, "Invalid signature format"
        
        # Compute the expected signature
        signed_payload = f"{timestamp}.{payload_bytes.decode('utf-8')}"
        computed_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        if computed_signature != signatures:
            return False, "Invalid signature"
        
        return True, "Signature verified"
    
    except Exception as e:
        logger.error(f"Error verifying Stripe signature: {e}")
        return False, f"Error verifying signature: {str(e)}"

async def _verify_paypal_signature(
    request: Request,
    payload_bytes: bytes,
    provider_config: Dict[str, Any]
) -> Tuple[bool, str]:
    """Verify PayPal webhook signature."""
    # PayPal's verification is complex and requires an API call
    # For simplicity, we'll skip implementation here
    return True, "PayPal signature verification not implemented"

async def _verify_paystack_signature(
    request: Request,
    payload_bytes: bytes,
    provider_config: Dict[str, Any]
) -> Tuple[bool, str]:
    """Verify Paystack webhook signature."""
    webhook_secret = provider_config.get("webhook_secret")
    if not webhook_secret:
        logger.warning("Paystack webhook secret not configured")
        return True, "Webhook secret not configured"
    
    # Get the signature from the headers
    signature = request.headers.get("x-paystack-signature")
    if not signature:
        return False, "No signature provided in headers"
    
    # Compute the expected signature
    computed_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha512
    ).hexdigest()
    
    # Compare signatures
    if computed_signature != signature:
        return False, "Invalid signature"
    
    return True, "Signature verified"

async def _process_webhook_data(
    db: Session,
    provider_id: str,
    webhook_data: Dict[str, Any]
) -> None:
    """Process webhook data from a payment provider."""
    # Extract key information
    event_type = webhook_data.get("event_type")
    provider_reference = webhook_data.get("provider_reference")
    payment_status = webhook_data.get("status")
    amount = webhook_data.get("amount")
    transaction_id = webhook_data.get("transaction_id")
    metadata = webhook_data.get("metadata", {})
    payment_id = metadata.get("payment_id")
    
    # Find the payment in the database
    payment = None
    if payment_id:
        payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    
    if not payment and provider_reference:
        payment = db.query(PaymentDB).filter(PaymentDB.provider_reference == provider_reference).first()
    
    if not payment:
        logger.warning(f"Payment not found for webhook: {webhook_data}")
        return
    
    # Create a transaction record
    transaction = PaymentTransactionDB(
        payment_id=payment.id,
        reference=transaction_id or str(uuid.uuid4()),
        amount=amount or payment.amount,
        status=payment_status or "unknown",
        provider=provider_id,
        provider_reference=provider_reference,
        transaction_type=event_type or "webhook",
        metadata=webhook_data
    )
    
    db.add(transaction)
    
    # Update the payment status
    if payment_status:
        old_status = payment.status
        
        # Map provider status to our status
        if payment_status.lower() in ["success", "successful", "completed", "paid"]:
            payment.status = PaymentStatus.COMPLETED.value
        
        elif payment_status.lower() in ["pending", "processing", "in_progress"]:
            payment.status = PaymentStatus.PROCESSING.value
        
        elif payment_status.lower() in ["failed", "failure", "error"]:
            payment.status = PaymentStatus.FAILED.value
        
        elif payment_status.lower() in ["cancelled", "canceled"]:
            payment.status = PaymentStatus.CANCELLED.value
        
        elif payment_status.lower() in ["refunded"]:
            payment.status = PaymentStatus.REFUNDED.value
        
        payment.updated_at = datetime.utcnow()
        
        # Log status change
        if old_status != payment.status:
            logger.info(f"Payment {payment.id} status changed from {old_status} to {payment.status}")
    
    db.commit()
