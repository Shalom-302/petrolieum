"""
Configuration module for the API Gateway plugin.

Defines all configurable parameters and settings for the API Gateway plugin.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ApiGatewayConfig(BaseModel):
    """Configuration for the API Gateway plugin."""
    
    # API Documentation settings
    api_title: str = "API Gateway"
    api_description: str = "Secure API Gateway for accessing application services"
    api_version: str = "1.0.0"
    
    # Security settings
    api_key_header_name: str = "X-API-Key"
    api_key_query_param: str = "api_key"
    default_key_expiry_days: int = 365
    hash_algorithm: str = "bcrypt"  # Options: bcrypt, sha256, etc.
    
    # Rate limiting settings
    enable_rate_limiting: bool = True
    default_rate_limit: str = "100/minute"  # Default rate limit for API keys
    global_rate_limit: str = "1000/minute"  # Overall API Gateway rate limit
    rate_limit_window_seconds: int = 60  # Default window for rate limits
    
    # Audit logging settings
    enable_audit_logging: bool = True
    audit_log_level: str = "INFO"  # Logging level for API audit logs
    sensitive_headers: List[str] = Field(
        default=["Authorization", "Cookie", "X-API-Key"],
        description="Headers to sanitize in audit logs"
    )
    sensitive_body_fields: List[str] = Field(
        default=["password", "token", "secret", "key", "credit_card", "ssn"],
        description="Request body fields to sanitize in audit logs"
    )
    
    # CORS settings
    cors_allow_origins: List[str] = ["*"]
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    cors_allow_headers: List[str] = ["*"]
    cors_allow_credentials: bool = False
    cors_expose_headers: List[str] = []
    cors_max_age: int = 600  # 10 minutes
    
    # Proxy settings
    add_proxy_headers: bool = True
    x_forwarded_prefix: Optional[str] = None
    
    # API Versioning
    enable_version_in_url: bool = True
    default_version: str = "v1"
    
    # Cache settings
    enable_response_caching: bool = False
    default_cache_ttl_seconds: int = 300  # 5 minutes
    
    # Throttling settings
    enable_throttling: bool = False
    throttle_burst_size: int = 20
    throttle_replenish_rate: float = 10.0  # Per second
    
    # Custom middlewares
    custom_middlewares: List[Dict[str, Any]] = []
    
    # Plugin routes base path
    admin_base_path: str = "/admin/api-gateway"
    
    # Default permissions
    admin_permissions: List[str] = ["admin:api_gateway:manage"]
    
    class Config:
        """Pydantic config."""
        env_prefix = "API_GATEWAY_"  # Environment variable prefix
