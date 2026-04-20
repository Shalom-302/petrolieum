"""
Authentication providers for the advanced authentication plugin.
"""
from typing import Dict, Type, Any, Optional, List
import logging

from .base import AuthProvider, AuthResult, UserInfo
from .email import EmailAuthProvider
from .github import GitHubAuthProvider
from .google import GoogleAuthProvider
from .facebook import FacebookAuthProvider

logger = logging.getLogger(__name__)

# Register all providers
PROVIDERS = {
    "email": EmailAuthProvider,
    "github": GitHubAuthProvider,
    "google": GoogleAuthProvider,
    "facebook": FacebookAuthProvider,
}

def get_provider(provider_name: str, config: Optional[Dict[str, Any]] = None) -> AuthProvider:
    """
    Get an instance of the requested authentication provider.
    
    Args:
        provider_name: Name of the provider to instantiate
        config: Provider-specific configuration
        
    Returns:
        Provider instance
        
    Raises:
        ValueError: If provider is not supported
    """
    if provider_name not in PROVIDERS:
        raise ValueError(f"Provider '{provider_name}' is not supported")
    
    provider_class = PROVIDERS[provider_name]
    return provider_class(config or {})


def list_providers() -> List[Dict[str, str]]:
    """
    List all available authentication providers with their metadata.
    
    Returns:
        List of provider information dictionaries
    """
    result = []
    
    for name, provider_class in PROVIDERS.items():
        # Create a temporary instance to get metadata
        try:
            provider = provider_class({})
            provider_info = {
                "name": name,
                "friendly_name": getattr(provider, "friendly_name", name.capitalize()),
                "icon": getattr(provider, "icon", name),
            }
            result.append(provider_info)
        except Exception as e:
            # Skip providers that require configuration for instantiation
            logger.debug(f"Could not instantiate provider {name} without config: {str(e)}")
            provider_info = {
                "name": name,
                "friendly_name": name.capitalize(),
                "icon": name,
            }
            result.append(provider_info)
    
    return result
