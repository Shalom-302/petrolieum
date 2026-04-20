"""
Provider factory for payment providers.

This module provides a factory for creating payment provider instances.
"""
import logging
import importlib
from typing import Dict, Any, Type, List, Optional

from ..models.provider import ProviderResponse
from .base_provider import BasePaymentProvider
from ..security import payment_security

# Do not import providers here, they will be imported in the register_all method
# to avoid circular imports

logger = logging.getLogger("kaapi.payment.factory")


class PaymentProviderFactory:
    """
    Factory for creating payment provider instances.
    
    This factory maintains a registry of payment provider classes and
    can create instances of them based on provider name.
    """
    
    _providers: Dict[str, Type[BasePaymentProvider]] = {}
    
    @classmethod
    def register(cls, provider_class: Type[BasePaymentProvider]) -> Type[BasePaymentProvider]:
        """
        Register a payment provider class with the factory.
        
        Args:
            provider_class: Provider class to register
            
        Returns:
            The provider class (for decorator use)
        """
        provider_name = provider_class.provider_name
        cls._providers[provider_name] = provider_class
        logger.info(f"Registered payment provider: {provider_name}")
        return provider_class
    
    @classmethod
    def create_provider(cls, provider_name: str, config: Dict[str, Any]) -> Optional[BasePaymentProvider]:
        """
        Create a payment provider instance.
        
        Args:
            provider_name: Name of the provider to create
            config: Provider configuration
            
        Returns:
            Provider instance, or None if provider not found
        """
        # Apply security best practices to the configuration
        secure_config = cls._apply_security_to_config(provider_name, config)
        
        # Create provider instance
        provider_class = cls._providers.get(provider_name)
        if provider_class:
            try:
                provider = provider_class(secure_config)
                logger.info(f"Created payment provider: {provider_name}")
                return provider
            except Exception as e:
                logger.error(f"Failed to create payment provider {provider_name}: {str(e)}")
                return None
        else:
            logger.error(f"Payment provider not found: {provider_name}")
            return None
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get a list of available provider names.
        
        Returns:
            List of provider names
        """
        return list(cls._providers.keys())
    
    @classmethod
    def get_provider_names(cls) -> List[str]:
        """
        Get a list of all registered provider names.
        
        Returns:
            List of provider names
        """
        return list(cls._providers.keys())

    @classmethod
    def register_all(cls):
        """
        Register all available payment providers.
        
        Import all provider modules and register their provider classes.
        """
        try:
            # Import provider modules here to avoid circular imports
            from . import cinetpay
            from . import paystack
            from . import flutterwave
            from . import mpesa
            from . import hub2
            from . import paydunya
            from . import wave
            
            for provider_module in [cinetpay, paystack, flutterwave, mpesa, hub2, paydunya, wave]:
                for attr_name in dir(provider_module):
                    attr = getattr(provider_module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BasePaymentProvider) and attr != BasePaymentProvider:
                        logger.debug(f"Found provider class: {attr_name}")
                        cls.register(attr)
        except ImportError as e:
            logger.error(f"Error importing payment providers: {str(e)}")
            # Continue even if some providers cannot be imported

    @classmethod
    def _apply_security_to_config(cls, provider_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply security measures to provider configuration.
        
        This method attempts to retrieve stored credentials from the vault and
        combines them with the provided configuration.
        
        Args:
            provider_name: Name of the provider
            config: Original provider configuration
            
        Returns:
            Secure provider configuration
        """
        try:
            # Try to get credentials from vault
            stored_credentials = payment_security.get_provider_credentials(provider_name)
            
            if stored_credentials:
                # Merge stored credentials with provided config
                # Config takes precedence over stored credentials
                secure_config = {**stored_credentials, **config}
                logger.info(f"Retrieved secure credentials for provider: {provider_name}")
                return secure_config
            else:
                # No stored credentials, use provided config
                logger.info(f"No stored credentials found for provider: {provider_name}")
                return config
                
        except Exception as e:
            logger.warning(f"Error retrieving secure credentials for {provider_name}: {str(e)}")
            return config

    @classmethod
    def initialize_provider_from_config(cls, provider_name: str, config: Dict[str, Any]) -> Optional[BasePaymentProvider]:
        """
        Initialize a payment provider from configuration.
        
        This is a convenience method that creates a provider instance and
        applies any necessary setup.
        
        Args:
            provider_name: Name of the provider to initialize
            config: Provider configuration
            
        Returns:
            Initialized provider instance, or None if provider not found or initialization failed
        """
        try:
            provider = cls.create_provider(provider_name, config)
            if provider:
                logger.info(f"Successfully initialized provider: {provider_name}")
                return provider
            else:
                logger.error(f"Failed to create provider instance: {provider_name}")
                return None
        except Exception as e:
            logger.error(f"Error initializing provider {provider_name}: {str(e)}")
            return None


# Register all providers
PaymentProviderFactory.register_all()
