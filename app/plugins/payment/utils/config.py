"""
Configuration for the payment plugin.

This module provides configuration management for the payment plugin.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from ..models.provider import PaymentProviderConfig

logger = logging.getLogger("kaapi.payment.config")

class PaymentSettings(BaseSettings):
    """Settings for the payment plugin."""
    
    # General settings
    base_url: str = Field("http://localhost:8000", env="PAYMENT_BASE_URL")
    is_test_mode: bool = Field(True, env="PAYMENT_TEST_MODE")
    
    # Provider configurations
    mpesa_api_key: Optional[str] = Field(None, env="PAYMENT_MPESA_API_KEY")
    mpesa_api_secret: Optional[str] = Field(None, env="PAYMENT_MPESA_API_SECRET")
    mpesa_business_shortcode: Optional[str] = Field(None, env="PAYMENT_MPESA_BUSINESS_SHORTCODE")
    mpesa_passkey: Optional[str] = Field(None, env="PAYMENT_MPESA_PASSKEY")
    
    flutterwave_api_key: Optional[str] = Field(None, env="PAYMENT_FLUTTERWAVE_API_KEY")
    flutterwave_api_secret: Optional[str] = Field(None, env="PAYMENT_FLUTTERWAVE_API_SECRET")
    flutterwave_merchant_id: Optional[str] = Field(None, env="PAYMENT_FLUTTERWAVE_MERCHANT_ID")
    flutterwave_webhook_secret: Optional[str] = Field(None, env="PAYMENT_FLUTTERWAVE_WEBHOOK_SECRET")
    
    stripe_api_key: Optional[str] = Field(None, env="PAYMENT_STRIPE_API_KEY")
    stripe_webhook_secret: Optional[str] = Field(None, env="PAYMENT_STRIPE_WEBHOOK_SECRET")
    
    paypal_client_id: Optional[str] = Field(None, env="PAYMENT_PAYPAL_CLIENT_ID")
    paypal_client_secret: Optional[str] = Field(None, env="PAYMENT_PAYPAL_CLIENT_SECRET")
    
    paystack_api_key: Optional[str] = Field(None, env="PAYMENT_PAYSTACK_API_KEY")
    paystack_webhook_secret: Optional[str] = Field(None, env="PAYMENT_PAYSTACK_WEBHOOK_SECRET")
    
    # URLs
    return_url_template: str = Field("/apipayments/{payment_id}/return", env="PAYMENT_RETURN_URL_TEMPLATE")
    cancel_url_template: str = Field("/apipayments/{payment_id}/cancel", env="PAYMENT_CANCEL_URL_TEMPLATE")
    webhook_url_template: str = Field("/apipayments/webhook/{provider}", env="PAYMENT_WEBHOOK_URL_TEMPLATE")
    
    # Approval workflow settings
    default_approval_workflow: str = Field("standard_payment_approval", env="PAYMENT_DEFAULT_APPROVAL_WORKFLOW")
    require_approval_threshold: float = Field(1000.0, env="PAYMENT_REQUIRE_APPROVAL_THRESHOLD")
    
    # Extra settings from config file
    _extra_config: Dict[str, Any] = {}
    
    # Additional environment variables that were previously accepted automatically by Pydantic v1
    # but need to be explicitly defined in v2
    db_url: Optional[str] = None
    secret_key: Optional[str] = None
    access_token_expire_minutes: Optional[str] = None
    algorithm: Optional[str] = None
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    rabbitmq_username: Optional[str] = None
    rabbitmq_password: Optional[str] = None
    rabbitmq_host: Optional[str] = None
    rabbitmq_port: Optional[str] = None
    loki_url: Optional[str] = None
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow"  # Permettre les champs supplémentaires
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_config_file()
    
    def _load_config_file(self):
        """Load additional configuration from a JSON file."""
        config_path = Path(__file__).parent.parent / "config.json"
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    self._extra_config = json.load(f)
                logger.info("Loaded payment plugin configuration from config.json")
            except Exception as e:
                logger.error(f"Error loading payment plugin configuration: {e}")
    
    def get_provider_config(self, provider_id: str) -> PaymentProviderConfig:
        """Get configuration for a specific provider."""
        if provider_id == "mpesa":
            return PaymentProviderConfig(
                api_key=self.mpesa_api_key,
                api_secret=self.mpesa_api_secret,
                environment="test" if self.is_test_mode else "production",
                extra_config={
                    "business_short_code": self.mpesa_business_shortcode,
                    "passkey": self.mpesa_passkey,
                    **self._get_extra_provider_config(provider_id)
                }
            )
        
        elif provider_id == "flutterwave":
            return PaymentProviderConfig(
                api_key=self.flutterwave_api_key,
                api_secret=self.flutterwave_api_secret,
                merchant_id=self.flutterwave_merchant_id,
                webhook_secret=self.flutterwave_webhook_secret,
                environment="test" if self.is_test_mode else "production",
                extra_config=self._get_extra_provider_config(provider_id)
            )
        
        elif provider_id == "stripe":
            return PaymentProviderConfig(
                api_key=self.stripe_api_key,
                webhook_secret=self.stripe_webhook_secret,
                environment="test" if self.is_test_mode else "production",
                extra_config=self._get_extra_provider_config(provider_id)
            )
        
        elif provider_id == "paypal":
            return PaymentProviderConfig(
                api_key=self.paypal_client_id,
                api_secret=self.paypal_client_secret,
                environment="test" if self.is_test_mode else "production",
                extra_config=self._get_extra_provider_config(provider_id)
            )
        
        elif provider_id == "paystack":
            return PaymentProviderConfig(
                api_key=self.paystack_api_key,
                webhook_secret=self.paystack_webhook_secret,
                environment="test" if self.is_test_mode else "production",
                extra_config=self._get_extra_provider_config(provider_id)
            )
        
        # Generic configuration for other providers
        return PaymentProviderConfig(
            environment="test" if self.is_test_mode else "production",
            extra_config=self._get_extra_provider_config(provider_id)
        )
    
    def _get_extra_provider_config(self, provider_id: str) -> Dict[str, Any]:
        """Get extra configuration for a provider from the config file."""
        providers = self._extra_config.get("providers", {})
        return providers.get(provider_id, {})
    
    def is_provider_enabled(self, provider_id: str) -> bool:
        """Check if a provider is enabled."""
        # Check if provider has required configuration
        if provider_id == "mpesa":
            if not self.mpesa_api_key or not self.mpesa_api_secret:
                return False
        
        elif provider_id == "flutterwave":
            if not self.flutterwave_api_key or not self.flutterwave_api_secret:
                return False
        
        elif provider_id == "stripe":
            if not self.stripe_api_key:
                return False
        
        elif provider_id == "paypal":
            if not self.paypal_client_id or not self.paypal_client_secret:
                return False
        
        elif provider_id == "paystack":
            if not self.paystack_api_key:
                return False
        
        # Check if provider is explicitly disabled in config file
        providers = self._extra_config.get("providers", {})
        provider_config = providers.get(provider_id, {})
        return provider_config.get("enabled", True)
    
    def get_return_url(self, payment_id: int) -> str:
        """Get the return URL for a payment."""
        relative_url = self.return_url_template.format(payment_id=payment_id)
        return f"{self.base_url}{relative_url}"
    
    def get_cancel_url(self, payment_id: int) -> str:
        """Get the cancel URL for a payment."""
        relative_url = self.cancel_url_template.format(payment_id=payment_id)
        return f"{self.base_url}{relative_url}"
    
    def get_webhook_url(self, provider: str) -> str:
        """Get the webhook URL for a provider."""
        relative_url = self.webhook_url_template.format(provider=provider)
        return f"{self.base_url}{relative_url}"
    
    def should_require_approval(self, amount: float, currency: str) -> bool:
        """Determine if a payment requires approval based on amount and currency."""
        # Simple implementation based on a threshold
        # In a real app, you'd have currency conversion and more complex rules
        return amount >= self.require_approval_threshold

# Create a global instance
payment_settings = PaymentSettings()

def load_payment_config() -> Dict[str, Any]:
    """
    Load payment configuration from environment variables and config file.
    
    Returns:
        Dict containing all payment configuration settings
    """
    # Force load config file
    payment_settings._load_config_file()
    
    # Convert to dict for easier access in other modules
    config_dict = {
        "base_url": payment_settings.base_url,
        "is_test_mode": payment_settings.is_test_mode,
        "mpesa": payment_settings.get_provider_config("mpesa"),
        "flutterwave": payment_settings.get_provider_config("flutterwave"),
        "stripe": payment_settings.get_provider_config("stripe"),
        "paypal": payment_settings.get_provider_config("paypal"),
        "paystack": payment_settings.get_provider_config("paystack"),
        "approval": {
            "default_workflow": payment_settings.default_approval_workflow,
            "threshold": payment_settings.require_approval_threshold
        }
    }
    
    logger.info(f"Loaded payment config with {len(config_dict)} providers")
    return config_dict

def init_payment_settings():
    """
    Initialize payment settings and validate configuration.
    
    This function should be called during application startup to ensure
    that all payment providers have valid configurations.
    """
    logger.info("Initializing payment settings")
    
    # Validate provider configurations
    providers = ["mpesa", "flutterwave", "stripe", "paypal", "paystack"]
    enabled_providers = []
    
    for provider in providers:
        if payment_settings.is_provider_enabled(provider):
            enabled_providers.append(provider)
    
    logger.info(f"Enabled payment providers: {', '.join(enabled_providers)}")
    
    return payment_settings
