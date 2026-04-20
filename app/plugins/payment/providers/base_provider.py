"""
Base payment provider.

This module defines the base interface for payment providers.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from ..models.provider import (
    PaymentProviderConfig,
    PaymentRequest,
    ProviderResponse,
    RefundRequest
)
from ..models.payment import PaymentStatus, RefundStatus
from ..models.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate, SubscriptionCancelRequest
from ..security import payment_security

logger = logging.getLogger("kaapi.payment.provider")

class BasePaymentProvider(ABC):
    """Base payment provider interface."""
    
    def __init__(self, config: PaymentProviderConfig):
        """Initialize the provider with configuration."""
        self.config = config
        self.security = payment_security
        
        # Initialize security settings
        self._init_security()
    
    def _init_security(self):
        """Initialize security settings for the provider."""
        # Store credentials securely if needed
        if not hasattr(self.config, 'credentials_stored') or not self.config.credentials_stored:
            try:
                provider_id = self.id
                credentials = {
                    key: value for key, value in self.config.__dict__.items()
                    if key.endswith('_key') or key.endswith('_secret') or key.endswith('_token')
                }
                
                if credentials:
                    self.security.store_provider_credentials(provider_id, credentials)
                    setattr(self.config, 'credentials_stored', True)
                    logger.info(f"Stored credentials for provider: {provider_id}")
            except Exception as e:
                logger.warning(f"Failed to store credentials: {str(e)}")
    
    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive data before storing or processing.
        
        Args:
            data: Dictionary containing potentially sensitive data
            
        Returns:
            Dictionary with sensitive fields encrypted
        """
        return self.security.encrypt_sensitive_data(data)
    
    def decrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive data.
        
        Args:
            data: Dictionary containing encrypted sensitive data
            
        Returns:
            Dictionary with sensitive fields decrypted
        """
        return self.security.decrypt_sensitive_data(data)
    
    def log_payment_transaction(self, transaction_id: str, payment_data: Dict[str, Any], status: str):
        """
        Log a payment transaction securely.
        
        Args:
            transaction_id: Unique transaction identifier
            payment_data: Payment data to log
            status: Status of the transaction
        """
        try:
            # Encrypt sensitive data before logging
            encrypted_data = self.encrypt_sensitive_data(payment_data)
            
            self.security.log_payment_transaction(
                provider_id=self.id,
                transaction_id=transaction_id,
                payment_data=encrypted_data,
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to log payment transaction: {str(e)}")
    
    def log_refund_transaction(self, transaction_id: str, refund_data: Dict[str, Any], status: str):
        """
        Log a refund transaction securely.
        
        Args:
            transaction_id: Unique transaction identifier
            refund_data: Refund data to log
            status: Status of the transaction
        """
        try:
            # Encrypt sensitive data before logging
            encrypted_data = self.encrypt_sensitive_data(refund_data)
            
            self.security.log_refund_transaction(
                provider_id=self.id,
                transaction_id=transaction_id,
                refund_data=encrypted_data,
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to log refund transaction: {str(e)}")
    
    def validate_payment_request(self, payment_request: PaymentRequest) -> bool:
        """
        Validate a payment request for PCI compliance and security.
        
        Args:
            payment_request: Payment request to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Convert to dict if needed
            payment_data = payment_request.dict() if hasattr(payment_request, 'dict') else payment_request
            return self.security.validate_payment_data(payment_data)
        except Exception as e:
            logger.error(f"Payment validation error: {str(e)}")
            return False
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Get provider ID."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get provider name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get provider description."""
        pass
    
    @property
    def is_enabled(self) -> bool:
        """Check if provider is enabled."""
        return True
    
    @property
    @abstractmethod
    def supported_methods(self) -> List[str]:
        """Get supported payment methods."""
        pass
    
    @property
    @abstractmethod
    def supported_currencies(self) -> List[str]:
        """Get supported currencies."""
        pass
    
    @property
    def supports_refunds(self) -> bool:
        """Check if provider supports refunds."""
        return True
    
    @property
    def supports_partial_refunds(self) -> bool:
        """Check if provider supports partial refunds."""
        return True
    
    @abstractmethod
    async def process_payment(self, payment_request: PaymentRequest) -> ProviderResponse:
        """
        Process a payment through this provider.
        
        Args:
            payment_request: Payment request details
            
        Returns:
            Provider response with payment details
        """
        pass
    
    @abstractmethod
    async def verify_payment(self, reference: str) -> ProviderResponse:
        """
        Verify a payment with the provider.
        
        Args:
            reference: Provider reference to verify
            
        Returns:
            Provider response with payment status
        """
        pass
    
    @abstractmethod
    async def cancel_payment(self, reference: str) -> ProviderResponse:
        """
        Cancel a payment with the provider.
        
        Args:
            reference: Provider reference to cancel
            
        Returns:
            Provider response with cancellation result
        """
        pass
    
    async def process_refund(self, refund_request: RefundRequest) -> ProviderResponse:
        """
        Process a refund through this provider.
        
        Args:
            refund_request: Refund request details
            
        Returns:
            Provider response with refund details
        """
        if not self.supports_refunds:
            return ProviderResponse(
                success=False,
                status=RefundStatus.FAILED,
                provider_reference="",
                message=f"Provider {self.id} does not support refunds",
                raw_response={"error": "refunds_not_supported"}
            )
        
        if not self.supports_partial_refunds and refund_request.is_partial:
            return ProviderResponse(
                success=False,
                status=RefundStatus.FAILED,
                provider_reference="",
                message=f"Provider {self.id} does not support partial refunds",
                raw_response={"error": "partial_refunds_not_supported"}
            )
        
        # Default implementation that should be overridden
        logger.warning(f"Using default refund implementation for provider {self.id}")
        return ProviderResponse(
            success=False,
            status=RefundStatus.FAILED,
            provider_reference="",
            message="Refund not implemented",
            raw_response={"error": "not_implemented"}
        )
    
    async def verify_refund(self, reference: str) -> ProviderResponse:
        """
        Verify a refund with the provider.
        
        Args:
            reference: Provider reference to verify
            
        Returns:
            Provider response with refund status
        """
        if not self.supports_refunds:
            return ProviderResponse(
                success=False,
                status=RefundStatus.FAILED,
                provider_reference=reference,
                message=f"Provider {self.id} does not support refunds",
                raw_response={"error": "refunds_not_supported"}
            )
        
        # Default implementation that should be overridden
        logger.warning(f"Using default refund verification implementation for provider {self.id}")
        return ProviderResponse(
            success=False,
            status=RefundStatus.FAILED,
            provider_reference=reference,
            message="Refund verification not implemented",
            raw_response={"error": "not_implemented"}
        )
    
    @abstractmethod
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Handle webhook data from the provider.
        
        Args:
            payload: Webhook payload
            headers: Webhook headers
            
        Returns:
            Processed webhook data or None if not applicable
        """
        pass
    
    @abstractmethod
    async def create_subscription(self, subscription: SubscriptionCreate) -> SubscriptionResponse:
        """Create a new subscription with the provider."""
        pass

    @abstractmethod
    async def update_subscription(self, subscription_id: str, update_data: SubscriptionUpdate) -> SubscriptionResponse:
        """Update an existing subscription with the provider."""
        pass

    @abstractmethod
    async def cancel_subscription(self, request: SubscriptionCancelRequest) -> SubscriptionResponse:
        """Cancel a subscription with the provider."""
        pass
    
    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> SubscriptionResponse:
        """Get information about a subscription from the provider."""
        pass
