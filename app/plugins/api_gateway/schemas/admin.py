"""
Admin schemas for the API Gateway plugin.

Defines Pydantic models for API requests and responses for the admin interface.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


# API Key schemas

class ApiKeyBase(BaseModel):
    """Base schema for API key data."""
    
    name: str = Field(..., description="Display name for the API key")
    permissions: List[str] = Field(default=[], description="List of permissions in format 'namespace:resource:action'")
    rate_limit: Optional[str] = Field(None, description="Rate limit in format 'number/period' (e.g., '100/minute')")
    ip_whitelist: List[str] = Field(default=[], description="List of allowed IP addresses or CIDR ranges")
    origin_whitelist: List[str] = Field(default=[], description="List of allowed origins for CORS")
    metadata: Dict[str, Any] = Field(default={}, description="Custom metadata for the API key")


class ApiKeyCreate(ApiKeyBase):
    """Schema for creating a new API key."""
    
    expires_in_days: Optional[int] = Field(None, description="Number of days until the key expires")
    expiry_date: Optional[datetime] = Field(None, description="Explicit expiry date for the key")
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        """Validate that name is not empty."""
        if not v or not v.strip():
            raise ValueError('name must not be empty')
        return v.strip()


class ApiKeyUpdate(BaseModel):
    """Schema for updating an existing API key."""
    
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    rate_limit: Optional[str] = None
    is_active: Optional[bool] = None
    expires_in_days: Optional[int] = None
    expiry_date: Optional[datetime] = None
    ip_whitelist: Optional[List[str]] = None
    origin_whitelist: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        """Validate that name is not empty if provided."""
        if v is not None and not v.strip():
            raise ValueError('name must not be empty')
        return v.strip() if v else v


class ApiKeyResponse(ApiKeyBase):
    """Schema for API key response."""
    
    id: str
    key: Optional[str] = Field(None, description="Plain API key (only returned on creation or regeneration)")
    created_at: datetime
    expires_at: Optional[datetime] = None
    created_by: Optional[str] = None
    is_active: bool = True
    
    class Config:
        """Pydantic config."""
        from_attributes = True


class ApiKeyList(BaseModel):
    """Schema for a list of API keys."""
    
    items: List[ApiKeyResponse]
    total: int


# API Audit Log schemas

class ApiAuditLogResponse(BaseModel):
    """Schema for API audit log response."""
    
    id: str
    api_key_id: Optional[str] = None
    method: str
    path: str
    query_params: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_headers: Optional[Dict[str, str]] = None
    request_body: Optional[Any] = None
    status_code: Optional[int] = None
    response_body: Optional[Any] = None
    response_time_ms: Optional[float] = None
    timestamp: datetime
    error: Optional[str] = None
    
    class Config:
        """Pydantic config."""
        from_attributes = True


class ApiAuditLogList(BaseModel):
    """Schema for a list of API audit logs."""
    
    items: List[ApiAuditLogResponse]
    total: int


# Rate Limit schemas

class RateLimitResponse(BaseModel):
    """Schema for rate limit response."""
    
    id: str
    api_key_id: str
    window_key: str
    window_size_seconds: int
    max_requests: int
    current_requests: int
    last_request: datetime
    window_expires: datetime
    
    class Config:
        """Pydantic config."""
        from_attributes = True


class RateLimitList(BaseModel):
    """Schema for a list of rate limits."""
    
    items: List[RateLimitResponse]
    total: int


# API Gateway Configuration schemas

class ApiGatewayConfigUpdate(BaseModel):
    """Schema for updating API Gateway configuration."""
    
    api_title: Optional[str] = None
    api_description: Optional[str] = None
    api_version: Optional[str] = None
    api_key_header_name: Optional[str] = None
    api_key_query_param: Optional[str] = None
    default_key_expiry_days: Optional[int] = None
    enable_rate_limiting: Optional[bool] = None
    default_rate_limit: Optional[str] = None
    global_rate_limit: Optional[str] = None
    enable_audit_logging: Optional[bool] = None
    audit_log_level: Optional[str] = None
    sensitive_headers: Optional[List[str]] = None
    sensitive_body_fields: Optional[List[str]] = None
    cors_allow_origins: Optional[List[str]] = None
    cors_allow_methods: Optional[List[str]] = None
    cors_allow_headers: Optional[List[str]] = None
    cors_allow_credentials: Optional[bool] = None
    cors_expose_headers: Optional[List[str]] = None
    cors_max_age: Optional[int] = None
    add_proxy_headers: Optional[bool] = None
    x_forwarded_prefix: Optional[str] = None
    enable_version_in_url: Optional[bool] = None
    default_version: Optional[str] = None
    
    @validator('audit_log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        if v is not None:
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if v not in valid_levels:
                raise ValueError(f"audit_log_level must be one of {valid_levels}")
        return v


class ApiGatewayInfo(BaseModel):
    """Schema for API Gateway information response."""
    
    version: str
    active_keys: int
    total_requests: int
    routes_count: int
    namespaces: List[str]
    rate_limited_requests: int
    unauthorized_requests: int
