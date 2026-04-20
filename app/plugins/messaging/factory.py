"""
Factory class for creating messaging providers.
"""

from typing import Dict, Type, Optional
from . import MessagingProvider, MessageType
from .email_providers import GmailProvider, SendGridProvider
from .sms_providers import TwilioProvider, InfoBipProvider
from .push_providers import OneSignalProvider

class MessagingProviderFactory:
    _providers: Dict[str, Type[MessagingProvider]] = {
        # Email providers
        "gmail": GmailProvider,
        "sendgrid": SendGridProvider,
        
        # SMS providers
        "twilio": TwilioProvider,
        "infobip": InfoBipProvider,
        
        # Push notification providers
        "onesignal": OneSignalProvider
    }

    @classmethod
    def create_provider(cls, provider_name: str, **kwargs) -> Optional[MessagingProvider]:
        """
        Create a messaging provider instance.
        
        Args:
            provider_name: Name of the provider to create
            **kwargs: Configuration parameters for the provider
            
        Returns:
            MessagingProvider instance or None if provider not found
        """
        provider_class = cls._providers.get(provider_name.lower())
        if provider_class:
            return provider_class(**kwargs)
        return None

    @classmethod
    def get_available_providers(cls) -> Dict[str, MessageType]:
        """Get a dictionary of available providers and their message types."""
        return {
            name: provider_class().message_type
            for name, provider_class in cls._providers.items()
        }

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[MessagingProvider]):
        """Register a new provider class."""
        cls._providers[name.lower()] = provider_class
