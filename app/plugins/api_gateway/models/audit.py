"""
API Audit Log model for the API Gateway plugin.

Provides functionality to log and audit all API requests and activities
for security monitoring and compliance purposes.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Boolean, Integer
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

from app.core.db import Base

# Setup logging
logger = logging.getLogger(__name__)

class ApiAuditLogDB(Base):
    """API audit log database model."""
    
    __tablename__ = "api_gateway_audit_logs"
    
    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), ForeignKey("api_gateway_keys.id", ondelete="CASCADE"), nullable=True)
    
    # Request information
    request_id = Column(String(36), nullable=False, index=True)
    path = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    endpoint = Column(String(255), nullable=False)
    
    # Source information
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    origin = Column(String(255), nullable=True)
    
    # Response information
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    
    # Request details
    request_data = Column(JSON, nullable=True)
    request_headers = Column(JSON, nullable=True)
    
    # Security related flags
    is_authorized = Column(Boolean, nullable=False, default=False)
    auth_failure_reason = Column(String(255), nullable=True)
    is_rate_limited = Column(Boolean, nullable=False, default=False)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    api_key = relationship("ApiKeyDB", back_populates="audit_logs")
    
    @classmethod
    def log_request(
        cls,
        request_id: str,
        path: str,
        method: str,
        endpoint: str,
        api_key_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        origin: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
        request_headers: Optional[Dict[str, str]] = None,
        is_authorized: bool = False,
        auth_failure_reason: Optional[str] = None,
        is_rate_limited: bool = False
    ) -> "ApiAuditLogDB":
        """
        Log an API request to the audit log.
        
        Args:
            request_id: Unique ID for the request
            path: Request path
            method: HTTP method
            endpoint: Endpoint name/path
            api_key_id: API key ID (if available)
            ip_address: Client IP address
            user_agent: Client user agent
            origin: Request origin
            request_data: Request body data (sanitized)
            request_headers: Request headers (sanitized)
            is_authorized: Whether the request was authorized
            auth_failure_reason: Reason for authorization failure
            is_rate_limited: Whether the request was rate limited
            
        Returns:
            ApiAuditLogDB entry
        """
        # Sanitize sensitive data
        safe_request_data = cls._sanitize_request_data(request_data) if request_data else None
        safe_headers = cls._sanitize_headers(request_headers) if request_headers else None
        
        # Create the audit log entry
        log_entry = cls(
            request_id=request_id,
            path=path,
            method=method,
            endpoint=endpoint,
            api_key_id=api_key_id,
            ip_address=ip_address,
            user_agent=user_agent,
            origin=origin,
            request_data=safe_request_data,
            request_headers=safe_headers,
            is_authorized=is_authorized,
            auth_failure_reason=auth_failure_reason,
            is_rate_limited=is_rate_limited
        )
        
        # Log suspicious activity
        if not is_authorized or is_rate_limited:
            log_level = logging.WARNING
            message = f"Security event: "
            if not is_authorized:
                message += f"Unauthorized access attempt to {method} {path}"
                if auth_failure_reason:
                    message += f" - Reason: {auth_failure_reason}"
            if is_rate_limited:
                message += f"Rate limited request to {method} {path}"
            
            logger.log(log_level, message, extra={
                "request_id": request_id,
                "api_key_id": api_key_id,
                "ip_address": ip_address,
                "path": path
            })
        
        return log_entry
    
    def complete_log(self, status_code: int, response_time_ms: int) -> None:
        """
        Complete the audit log entry with response information.
        
        Args:
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
        """
        self.status_code = status_code
        self.response_time_ms = response_time_ms
        
        # Log slow responses
        if response_time_ms > 1000:  # More than 1 second
            logger.warning(f"Slow API response: {self.method} {self.path} took {response_time_ms}ms",
                         extra={
                             "request_id": self.request_id,
                             "api_key_id": self.api_key_id,
                             "response_time_ms": response_time_ms
                         })
    
    @staticmethod
    def _sanitize_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize request data by removing sensitive fields.
        
        Args:
            data: Request data dictionary
            
        Returns:
            Sanitized data dictionary
        """
        if not data:
            return {}
        
        # Deep copy to avoid modifying original
        sanitized = dict(data)
        
        # List of sensitive field names to redact
        sensitive_fields = [
            "password", "secret", "token", "key", "auth", "credential", 
            "cardnumber", "card_number", "cvv", "pin", "ssn", "social"
        ]
        
        # Recursively search and redact sensitive data
        def redact_sensitive(obj):
            if isinstance(obj, dict):
                for key in list(obj.keys()):
                    # Check if the key name contains sensitive information
                    if any(field in key.lower() for field in sensitive_fields):
                        obj[key] = "[REDACTED]"
                    else:
                        # Recursively check nested values
                        obj[key] = redact_sensitive(obj[key])
                return obj
            elif isinstance(obj, list):
                return [redact_sensitive(item) for item in obj]
            return obj
        
        return redact_sensitive(sanitized)
    
    @staticmethod
    def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """
        Sanitize request headers by removing sensitive headers.
        
        Args:
            headers: Request headers dictionary
            
        Returns:
            Sanitized headers dictionary
        """
        if not headers:
            return {}
        
        # Create a copy to avoid modifying the original
        sanitized = dict(headers)
        
        # List of sensitive header names to redact
        sensitive_headers = [
            "authorization", "cookie", "x-api-key", "api-key",
            "x-auth-token", "token", "secret", "password"
        ]
        
        # Redact sensitive headers
        for header in list(sanitized.keys()):
            if header.lower() in sensitive_headers:
                sanitized[header] = "[REDACTED]"
        
        return sanitized


# Pydantic models for API responses
class ApiAuditLogResponse(BaseModel):
    """API audit log response model."""
    
    id: str
    request_id: str
    path: str
    method: str
    endpoint: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    origin: Optional[str] = None
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    is_authorized: bool
    auth_failure_reason: Optional[str] = None
    is_rate_limited: bool
    created_at: datetime
    api_key_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class ApiAuditLogFilterParams(BaseModel):
    """Filter parameters for audit log queries."""
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    api_key_ids: Optional[List[str]] = None
    paths: Optional[List[str]] = None
    methods: Optional[List[str]] = None
    endpoints: Optional[List[str]] = None
    status_codes: Optional[List[int]] = None
    is_authorized: Optional[bool] = None
    is_rate_limited: Optional[bool] = None
    ip_address: Optional[str] = None
    
    class Config:
        from_attributes = True
