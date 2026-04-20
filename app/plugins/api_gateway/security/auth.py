"""
API Key Authentication module for the API Gateway plugin.

Provides robust security mechanisms for API key verification, permission checking,
and rate limiting to protect API endpoints from unauthorized access.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple, Set, Union, Callable
from ipaddress import ip_address, ip_network

from fastapi import Request, HTTPException, Depends, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.api_gateway.models.api_key import ApiKeyDB, ApiPermissionDB
from app.plugins.api_gateway.models.audit import ApiAuditLogDB
from app.plugins.api_gateway.models.rate_limit import RateLimitDB
from app.plugins.api_gateway.config import ApiGatewayConfig

# Setup logging
logger = logging.getLogger(__name__)

# API key security schemes
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

class ApiKeyAuth:
    """API Key authentication handler."""
    
    def __init__(self, db_session: Callable[[], Session], config: Optional[ApiGatewayConfig] = None):
        """
        Initialize the API key authentication handler.
        
        Args:
            db_session: Function that returns a database session
            config: API Gateway configuration
        """
        self.db_session = db_session
        self.config = config or ApiGatewayConfig()
        self._request_id = str(uuid.uuid4())
        self._start_time = datetime.utcnow()
        self._audit_log = None
        self._api_key = None
    
    async def __call__(
        self,
        request: Request,
        api_key_header: Optional[str] = Security(api_key_header),
        api_key_query: Optional[str] = Security(api_key_query),
        required: bool = True,
        permissions: Optional[List[str]] = None
    ) -> Optional[ApiKeyDB]:
        """
        Verify API key and permissions.
        
        Args:
            request: FastAPI request object
            api_key_header: API key from header
            api_key_query: API key from query parameter
            required: Whether an API key is required
            permissions: List of required permissions in format "namespace:resource:action"
            
        Returns:
            ApiKeyDB object if valid
            
        Raises:
            HTTPException: If API key is invalid or missing required permissions
        """
        # Extract request information
        path = request.url.path
        method = request.method
        
        # Get client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent")
        origin = request.headers.get("origin")
        
        # Get API key from header or query parameter
        api_key = api_key_header or api_key_query
        
        # Create initial audit log entry
        self._audit_log = ApiAuditLogDB.log_request(
            request_id=self._request_id,
            path=path,
            method=method,
            endpoint=path,  # Will be replaced with route name later
            api_key_id=None,  # Will be updated if API key is valid
            ip_address=client_ip,
            user_agent=user_agent,
            origin=origin,
            request_headers=dict(request.headers),
            is_authorized=False  # Default to unauthorized
        )
        db = self.db_session()
        db.add(self._audit_log)
        db.flush()
        
        # If API key is not required and not provided, allow the request
        if not required and not api_key:
            self._audit_log.is_authorized = True
            db.add(self._audit_log)
            return None
        
        # Verify the API key
        if not api_key:
            # API key is required but not provided
            self._handle_auth_failure("Missing API key", status.HTTP_401_UNAUTHORIZED)
        
        # Look up the API key
        api_key_obj = self._verify_api_key(api_key)
        if not api_key_obj:
            self._handle_auth_failure("Invalid API key", status.HTTP_401_UNAUTHORIZED)
        
        # Store the API key for later use
        self._api_key = api_key_obj
        self._audit_log.api_key_id = api_key_obj.id
        
        # Check if the API key is still valid
        if not api_key_obj.is_valid():
            self._handle_auth_failure("Expired or inactive API key", status.HTTP_401_UNAUTHORIZED)
        
        # Check if the request is allowed from this IP
        if not self._check_ip_restrictions(api_key_obj, client_ip):
            self._handle_auth_failure("IP address not allowed", status.HTTP_403_FORBIDDEN)
        
        # Check if the request is allowed from this origin
        if not self._check_origin_restrictions(api_key_obj, origin):
            self._handle_auth_failure("Origin not allowed", status.HTTP_403_FORBIDDEN)
        
        # Check rate limits
        allowed, window_limits = RateLimitDB.track_request(db, api_key_obj.id, path)
        if not allowed:
            # Mark as rate limited in the audit log
            self._audit_log.is_rate_limited = True
            db.add(self._audit_log)
            
            # Convert window limits to error message
            exceeded_windows = [w for w, exceeded in window_limits.items() if exceeded]
            
            self._handle_auth_failure(
                f"Rate limit exceeded for window(s): {', '.join(exceeded_windows)}",
                status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Check permissions if required
        if permissions:
            has_permissions = self._check_permissions(api_key_obj, permissions)
            if not has_permissions:
                self._handle_auth_failure("Insufficient permissions", status.HTTP_403_FORBIDDEN)
        
        # Update the audit log
        self._audit_log.is_authorized = True
        db.add(self._audit_log)
        
        # Update the API key usage statistics
        api_key_obj.last_used_at = datetime.utcnow()
        api_key_obj.use_count += 1
        db.add(api_key_obj)
        
        # Commit the changes
        db.commit()
        
        return api_key_obj
    
    def complete_audit_log(self, status_code: int) -> None:
        """
        Complete the audit log entry with response information.
        
        Args:
            status_code: HTTP status code
        """
        if self._audit_log:
            # Calculate response time
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - self._start_time).total_seconds() * 1000)
            
            # Update the audit log
            self._audit_log.complete_log(status_code, response_time_ms)
            db = self.db_session()
            db.add(self._audit_log)
            db.commit()
    
    def _verify_api_key(self, api_key: str) -> Optional[ApiKeyDB]:
        """
        Verify an API key against the database.
        
        Args:
            api_key: API key to verify
            
        Returns:
            ApiKeyDB object if valid, None otherwise
        """
        if not api_key or len(api_key) < 8:
            return None
        
        # Extract the prefix (first 8 characters)
        prefix = api_key[:8]
        
        # Find the API key in the database
        db = self.db_session()
        api_key_obj = db.query(ApiKeyDB).filter(ApiKeyDB.prefix == prefix).first()
        if not api_key_obj:
            return None
        
        # Verify the API key
        if not api_key_obj.verify_key(api_key):
            return None
        
        return api_key_obj
    
    def _check_permissions(self, api_key: ApiKeyDB, required_permissions: List[str]) -> bool:
        """
        Check if the API key has all required permissions.
        
        Args:
            api_key: API key object
            required_permissions: List of required permissions in format "namespace:resource:action"
            
        Returns:
            True if the API key has all required permissions
        """
        # Get all permissions for this API key
        db = self.db_session()
        api_permissions = db.query(ApiPermissionDB).filter(
            ApiPermissionDB.api_key_id == api_key.id
        ).all()
        
        # Convert to a set of "namespace:resource:action" strings
        permission_set = {
            f"{p.namespace}:{p.resource}:{p.action}" for p in api_permissions
        }
        
        # Add wildcard permissions
        wildcard_permissions = self._expand_wildcard_permissions(permission_set)
        permission_set.update(wildcard_permissions)
        
        # Check if all required permissions are present
        for required in required_permissions:
            if required not in permission_set:
                return False
        
        return True
    
    def _expand_wildcard_permissions(self, permissions: Set[str]) -> Set[str]:
        """
        Expand wildcard permissions to include all specific permissions they cover.
        
        Args:
            permissions: Set of permission strings
            
        Returns:
            Set of expanded permission strings
        """
        expanded = set()
        
        # Look for wildcard permissions
        for permission in permissions:
            parts = permission.split(":")
            
            # Skip if not in the correct format
            if len(parts) != 3:
                continue
            
            namespace, resource, action = parts
            
            # Handle wildcards at different levels
            if namespace == "*":
                # Global wildcard
                expanded.add("*:*:*")
            elif resource == "*":
                # Namespace wildcard
                expanded.add(f"{namespace}:*:*")
            elif action == "*":
                # Resource wildcard
                expanded.add(f"{namespace}:{resource}:*")
        
        return expanded
    
    def _check_ip_restrictions(self, api_key: ApiKeyDB, client_ip: str) -> bool:
        """
        Check if the client IP is allowed for this API key.
        
        Args:
            api_key: API key object
            client_ip: Client IP address
            
        Returns:
            True if the IP is allowed
        """
        # If no restrictions, allow all IPs
        if not api_key.allowed_ips:
            return True
        
        try:
            # Convert client IP to an ip_address object
            ip = ip_address(client_ip)
            
            # Check if the client IP is in any of the allowed networks
            for allowed_ip in api_key.allowed_ips:
                # Handle individual IPs and CIDR ranges
                if "/" in allowed_ip:
                    # CIDR range
                    network = ip_network(allowed_ip, strict=False)
                    if ip in network:
                        return True
                else:
                    # Individual IP
                    if client_ip == allowed_ip:
                        return True
            
            # No matching IP found
            return False
        except ValueError:
            # Invalid IP address format
            logger.warning(f"Invalid IP address format in allowed_ips: {api_key.allowed_ips}")
            return False
    
    def _check_origin_restrictions(self, api_key: ApiKeyDB, origin: Optional[str]) -> bool:
        """
        Check if the request origin is allowed for this API key.
        
        Args:
            api_key: API key object
            origin: Request origin
            
        Returns:
            True if the origin is allowed
        """
        # If no restrictions, allow all origins
        if not api_key.allowed_origins:
            return True
        
        # If no origin in the request, reject if restrictions are set
        if not origin:
            return False
        
        # Check if the origin matches any of the allowed origins
        for allowed_origin in api_key.allowed_origins:
            # Allow exact matches and wildcard subdomains
            if allowed_origin.startswith("*."):
                # Wildcard subdomain
                domain = allowed_origin[2:]  # Remove *. prefix
                if origin.endswith(domain) and "." in origin[:-len(domain)]:
                    return True
            else:
                # Exact match
                if origin == allowed_origin:
                    return True
        
        # No matching origin found
        return False
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Get the client IP address from the request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client IP address
        """
        # Check for X-Forwarded-For header
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Get the first IP in the list
            return forwarded_for.split(",")[0].strip()
        
        # Fall back to the direct client IP
        return request.client.host if request.client else "unknown"
    
    def _handle_auth_failure(self, reason: str, status_code: int) -> None:
        """
        Handle authentication/authorization failure.
        
        Args:
            reason: Reason for the failure
            status_code: HTTP status code
            
        Raises:
            HTTPException: Always
        """
        # Update the audit log
        if self._audit_log:
            self._audit_log.auth_failure_reason = reason
            db = self.db_session()
            db.add(self._audit_log)
            db.commit()
        
        # Log the authentication failure
        logger.warning(
            f"API authentication failure: {reason}",
            extra={
                "request_id": self._request_id,
                "api_key_id": self._api_key.id if self._api_key else None,
                "status_code": status_code
            }
        )
        
        # Raise HTTPException with the appropriate status code
        raise HTTPException(
            status_code=status_code,
            detail=reason
        )


def get_api_key_auth(db_session: Callable[[], Session] = Depends(get_db)) -> ApiKeyAuth:
    """
    Dependency for getting an ApiKeyAuth instance.
    
    Args:
        db_session: Function that returns a database session
        
    Returns:
        ApiKeyAuth instance
    """
    return ApiKeyAuth(db_session)


def requires_api_key(permissions: Optional[List[str]] = None):
    """
    Dependency for requiring an API key with optional permissions.
    
    Args:
        permissions: List of required permissions in format "namespace:resource:action"
        
    Returns:
        Function that requires an API key
    """
    async def _requires_api_key(
        request: Request,
        auth: ApiKeyAuth = Depends(get_api_key_auth)
    ) -> ApiKeyDB:
        """
        Require an API key with the specified permissions.
        
        Args:
            request: FastAPI request
            auth: ApiKeyAuth instance
            
        Returns:
            ApiKeyDB if valid
            
        Raises:
            HTTPException: If API key is invalid or missing required permissions
        """
        return await auth(request, required=True, permissions=permissions)
    
    return _requires_api_key


def optional_api_key(permissions: Optional[List[str]] = None):
    """
    Dependency for optional API key with optional permissions.
    
    Args:
        permissions: List of required permissions in format "namespace:resource:action"
        
    Returns:
        Function that accepts an optional API key
    """
    async def _optional_api_key(
        request: Request,
        auth: ApiKeyAuth = Depends(get_api_key_auth)
    ) -> Optional[ApiKeyDB]:
        """
        Accept an optional API key with the specified permissions.
        
        Args:
            request: FastAPI request
            auth: ApiKeyAuth instance
            
        Returns:
            ApiKeyDB if provided and valid, None otherwise
            
        Raises:
            HTTPException: If API key is provided but invalid or missing required permissions
        """
        return await auth(request, required=False, permissions=permissions)
    
    return _optional_api_key
