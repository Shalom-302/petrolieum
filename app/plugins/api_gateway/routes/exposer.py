"""
API route exposure functionality for the API Gateway plugin.

Provides decorators and utilities to expose internal functions as API endpoints,
with appropriate security, validation, and documentation.
"""

import functools
import inspect
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Callable, Optional, Type

from fastapi import FastAPI, APIRouter, Depends, Request, Body, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from ..security.auth import ApiKeyAuth, get_api_key_auth
from ..models.api_key import ApiKeyDB
from ..models.api_registry import ApiRegistry, RegisteredEndpoint
from ..models.audit import ApiAuditLogDB
from ..utils.rate_limit import parse_rate_limit

# Setup logging
logger = logging.getLogger(__name__)

def expose(
    namespace: str,
    path: str = None,
    methods: List[str] = ["GET"],
    requires: List[str] = None,
    rate_limit: str = None,
    version: str = "v1",
    deprecated: bool = False,
    audit_level: str = "basic",
    description: str = None,
    tags: List[str] = None,
    response_model: Type[Any] = None,
    request_model: Type[Any] = None,
):
    """
    Decorator to expose a function as an API endpoint.
    
    Args:
        namespace: API namespace (e.g., "payments", "users")
        path: API path (defaults to function name if not specified)
        methods: HTTP methods (GET, POST, PUT, DELETE, etc.)
        requires: Required permission scopes
        rate_limit: Rate limit string (e.g., "100/minute")
        version: API version
        deprecated: Whether the endpoint is deprecated
        audit_level: Audit logging level (none, basic, full)
        description: Endpoint description
        tags: OpenAPI tags
        response_model: Pydantic model for response
        request_model: Pydantic model for request body
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        # Store API metadata in function
        func.__api_exposed__ = True
        func.__api_namespace__ = namespace
        func.__api_path__ = path or f"/{func.__name__}"
        func.__api_methods__ = methods
        func.__api_requires__ = requires or []
        func.__api_rate_limit__ = rate_limit
        func.__api_version__ = version
        func.__api_deprecated__ = deprecated
        func.__api_audit_level__ = audit_level
        func.__api_description__ = description or func.__doc__
        func.__api_tags__ = tags or [namespace]
        func.__api_response_model__ = response_model
        func.__api_request_model__ = request_model
        
        # Parse rate limit if specified
        rate_limit_per_minute = None
        rate_limit_per_hour = None
        rate_limit_per_day = None
        
        if rate_limit:
            try:
                limit, period = rate_limit.split("/")
                limit = int(limit)
                
                if period.lower() in ["minute", "min", "m"]:
                    rate_limit_per_minute = limit
                elif period.lower() in ["hour", "hr", "h"]:
                    rate_limit_per_hour = limit
                elif period.lower() in ["day", "d"]:
                    rate_limit_per_day = limit
                else:
                    logger.warning(f"Unknown rate limit period: {period}, using as per minute")
                    rate_limit_per_minute = limit
            except:
                logger.error(f"Invalid rate limit format: {rate_limit}")
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # The original function is called as is
            # The actual API wrapping happens during registration
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def register_exposed_routes(app: FastAPI, registry: ApiRegistry):
    """
    Register all exposed API routes with the FastAPI application.
    
    Args:
        app: FastAPI application
        registry: API registry
    """
    for endpoint_key, endpoint_info in registry.endpoints.items():
        namespace = endpoint_info.namespace
        function = endpoint_info.function
        api_path = endpoint_info.path
        methods = endpoint_info.methods
        requires = endpoint_info.requires or []
        rate_limit = endpoint_info.rate_limit
        version = endpoint_info.version
        audit_level = endpoint_info.audit_level
        
        # Parse rate limit string into specific limits
        rate_limit_per_minute = 0
        rate_limit_per_hour = 0
        rate_limit_per_day = 0
        
        if rate_limit:
            rate_limits = parse_rate_limit(rate_limit)
            for window, limit in rate_limits.items():
                if window == "minute":
                    rate_limit_per_minute = limit
                elif window == "hour":
                    rate_limit_per_hour = limit
                elif window == "day":
                    rate_limit_per_day = limit
        
        # Go through each registered endpoint
        for endpoint in registry.get_endpoints_for_function(function):
            # Extract metadata
            tags = getattr(endpoint, "__api_tags__", [namespace])
            response_model = getattr(endpoint, "__api_response_model__", None)
            
            # Create an API router for external access
            router = APIRouter()
            
            # Path with version and namespace
            versioned_path = f"/api/{version}/{namespace}{api_path}"
            
            # Get db_session dependency for passing to ApiKeyAuth
            def get_db_session():
                return get_db()
            
            # Create API key authentication dependency using function
            def get_auth_for_endpoint():
                auth = get_api_key_auth(get_db_session)
                # Configure the auth instance with endpoint-specific settings
                auth.config.required_permissions = requires
                # Set rate limits (these would need to be added to the ApiKeyAuth class)
                # You could add these settings to your ApiGatewayConfig class
                return auth
            
            # Wrap the endpoint with authentication and logging
            @functools.wraps(endpoint)
            async def secured_endpoint(
                request: Request,
                response: Response,
                api_key=Depends(get_auth_for_endpoint()),
                **path_params
            ):
                # Extract path parameters
                kwargs = {**path_params}
                
                # Add request body if endpoint expects it
                request_model = getattr(endpoint, "__api_request_model__", None)
                if request_model:
                    body = await request.json()
                    kwargs["body"] = request_model(**body)
                
                # Call the original endpoint
                result = await endpoint(**kwargs)
                return result
            
            # Add the secured endpoint to the router
            for method in methods:
                if method == "GET":
                    router.get(
                        versioned_path,
                        response_model=response_model,
                        summary=getattr(endpoint, "__api_description__", "").split("\n")[0] if getattr(endpoint, "__api_description__", "") else None,
                        description=getattr(endpoint, "__api_description__", ""),
                        tags=tags,
                        deprecated=getattr(endpoint, "__api_deprecated__", False),
                    )(secured_endpoint)
                elif method == "POST":
                    router.post(
                        versioned_path,
                        response_model=response_model,
                        summary=getattr(endpoint, "__api_description__", "").split("\n")[0] if getattr(endpoint, "__api_description__", "") else None,
                        description=getattr(endpoint, "__api_description__", ""),
                        tags=tags,
                        deprecated=getattr(endpoint, "__api_deprecated__", False),
                    )(secured_endpoint)
                elif method == "PUT":
                    router.put(
                        versioned_path,
                        response_model=response_model,
                        summary=getattr(endpoint, "__api_description__", "").split("\n")[0] if getattr(endpoint, "__api_description__", "") else None,
                        description=getattr(endpoint, "__api_description__", ""),
                        tags=tags,
                        deprecated=getattr(endpoint, "__api_deprecated__", False),
                    )(secured_endpoint)
                elif method == "DELETE":
                    router.delete(
                        versioned_path,
                        response_model=response_model,
                        summary=getattr(endpoint, "__api_description__", "").split("\n")[0] if getattr(endpoint, "__api_description__", "") else None,
                        description=getattr(endpoint, "__api_description__", ""),
                        tags=tags,
                        deprecated=getattr(endpoint, "__api_deprecated__", False),
                    )(secured_endpoint)
            
            # Include the router in the app
            app.include_router(router)
            
            # Register the endpoint in the registry
            registry.register_endpoint(
                RegisteredEndpoint(
                    path=versioned_path,
                    method=method,
                    namespace=namespace,
                    function=endpoint,
                    requires=requires,
                    rate_limit=rate_limit,
                    version=version,
                    deprecated=getattr(endpoint, "__api_deprecated__", False),
                    audit_level=audit_level,
                    description=getattr(endpoint, "__api_description__", ""),
                    tags=tags,
                    response_model=response_model
                )
            )
            
            logger.info(f"Exposed API endpoint: {method} {versioned_path}")
    
    logger.info(f"Registered {len(registry.get_all_routes())} exposed API endpoints")
