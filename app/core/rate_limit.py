"""
Rate limiting functionality.

This module provides rate limiting capabilities to protect API endpoints
from excessive usage, implementing consistent rate limiting across the application.
"""

import logging
import time
from typing import Dict, Tuple, Callable, Any, Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Dictionary to store request counts for rate limiting
# Key: Client identifier, Value: (request_count, window_start_time)
_request_counts: Dict[str, Tuple[int, float]] = {}


def rate_limit(limit_per_minute: int = 60):
    """
    Apply rate limiting to an endpoint.
    
    This decorator can be applied to API endpoints to limit the number of 
    requests a user can make within a minute, preventing abuse.
    
    Args:
        limit_per_minute: Maximum number of requests allowed per minute
        
    Returns:
        Callable: Decorator function
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Get request object from kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
                    
            if not request:
                for _, value in kwargs.items():
                    if isinstance(value, Request):
                        request = value
                        break
            
            if not request:
                # If we can't get the request object, skip rate limiting
                logger.debug("Skipping rate limit check: request object not found")
                return await func(*args, **kwargs)
                
            # Get client identifier (IP address or user ID if available)
            client_id = request.client.host
            if "current_user_id" in kwargs:
                client_id = f"{client_id}:{kwargs['current_user_id']}"
                
            # Check rate limit
            now = time.time()
            
            if client_id in _request_counts:
                count, window_start = _request_counts[client_id]
                
                # Reset counter if window has expired
                if now - window_start > 60:
                    _request_counts[client_id] = (1, now)
                    logger.debug(f"Rate limit window reset for {client_id}")
                else:
                    # Increment counter
                    count += 1
                    if count > limit_per_minute:
                        logger.warning(f"Rate limit exceeded for {client_id}: {count} requests in under a minute")
                        raise HTTPException(
                            status_code=429, 
                            detail="Too many requests. Please try again later."
                        )
                    _request_counts[client_id] = (count, window_start)
                    logger.debug(f"Request count for {client_id}: {count}/{limit_per_minute}")
            else:
                # First request from this client
                _request_counts[client_id] = (1, now)
                logger.debug(f"First request in new rate limit window for {client_id}")
                
            # Execute the endpoint function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for global rate limiting.
    
    This middleware can be applied globally to limit requests across all
    endpoints based on client IP or user ID.
    """
    
    def __init__(
        self, 
        app, 
        limit_per_minute: int = 120,
        exclude_paths: Optional[list] = None
    ):
        """
        Initialize the rate limit middleware.
        
        Args:
            app: FastAPI application
            limit_per_minute: Maximum requests per minute
            exclude_paths: List of path prefixes to exclude from rate limiting
        """
        super().__init__(app)
        self.limit_per_minute = limit_per_minute
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/static"]
        logger.info(f"Rate limit middleware initialized: {limit_per_minute} requests/minute")
    
    async def dispatch(self, request: Request, call_next):
        """
        Process each request and apply rate limiting.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: FastAPI response
        """
        # Skip rate limiting for excluded paths
        path = request.url.path
        for excluded_path in self.exclude_paths:
            if path.startswith(excluded_path):
                return await call_next(request)
            
        # Get client identifier
        client_id = request.client.host
        
        # Extract user ID from auth header if available
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # We're not decoding the token here for performance reasons
            # Just using it as part of the client identifier
            token = auth_header.replace("Bearer ", "")
            client_id = f"{client_id}:{token[:16]}"  # Use part of token as identifier
            
        # Check rate limit
        now = time.time()
        
        if client_id in _request_counts:
            count, window_start = _request_counts[client_id]
            
            # Reset counter if window has expired
            if now - window_start > 60:
                _request_counts[client_id] = (1, now)
            else:
                # Increment counter
                count += 1
                if count > self.limit_per_minute:
                    logger.warning(f"Global rate limit exceeded for {client_id}: {count} requests in under a minute")
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests. Please try again later."}
                    )
                _request_counts[client_id] = (count, window_start)
        else:
            # First request from this client
            _request_counts[client_id] = (1, now)
            
        # Process the request
        return await call_next(request)


def configure_rate_limiting(app, global_limit: int = 120):
    """
    Configure rate limiting for the entire application.
    
    Args:
        app: FastAPI application
        global_limit: Global rate limit (requests per minute)
        
    Returns:
        The configured app
    """
    # Add rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        limit_per_minute=global_limit
    )
    
    logger.info(f"Global rate limiting configured: {global_limit} requests/minute")
    return app
