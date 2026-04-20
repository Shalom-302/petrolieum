"""
Middleware for handling API versioning.

This module provides middleware functionality to route API requests to the
appropriate version handlers based on various version specification methods.
"""

import logging
from typing import Callable, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.api_versioning.utils.version_manager import resolve_version_from_request


logger = logging.getLogger(__name__)


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API version routing.
    
    This middleware intercepts API requests, determines the appropriate version,
    and either routes to the correct handler or rejects the request if the version
    is invalid or inactive.
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize the middleware.
        
        Args:
            app: The ASGI application
        """
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request through the middleware.
        
        Args:
            request: The incoming request
            call_next: Function to call the next middleware
            
        Returns:
            The response
        """
        # Only apply to API requests
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Get a database session
        db_session = next(get_db())
        
        try:
            # Determine the API version to use
            version = resolve_version_from_request(request, db_session)
            
            # Store the resolved version in the request state
            request.state.api_version = version
            
            # Process the request
            response = await call_next(request)
            
            # Add version header to response
            response.headers["X-API-Version"] = version
            
            # Add deprecation header if applicable
            from app.plugins.api_versioning.models import APIVersion
            version_record = db_session.query(APIVersion).filter(APIVersion.version == version).first()
            
            if version_record and version_record.is_deprecated:
                # Add deprecation warning header
                warning = f"API version '{version}' is deprecated."
                
                # Find the recommended version
                from app.plugins.api_versioning.utils.version_manager import get_default_version
                default_version = get_default_version(db_session)
                
                if default_version and default_version.version != version:
                    warning += f" Please use version '{default_version.version}' instead."
                    response.headers["X-API-Recommended-Version"] = default_version.version
                
                response.headers["Warning"] = f'299 - "{warning}"'
                response.headers["X-API-Deprecated"] = "true"
            
            return response
            
        except Exception as e:
            logger.exception(f"Error in API version middleware: {str(e)}")
            return await call_next(request)
        finally:
            # Close the database session
            db_session.close()


class APIVersionHeaderMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add version headers to all API responses.
    
    This simpler middleware just adds version information to responses
    without affecting routing.
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize the middleware.
        
        Args:
            app: The ASGI application
        """
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request through the middleware.
        
        Args:
            request: The incoming request
            call_next: Function to call the next middleware
            
        Returns:
            The response
        """
        # Process the request
        response = await call_next(request)
        
        # Only apply to API responses
        if not request.url.path.startswith("/api/"):
            return response
        
        # Add available versions header
        db_session = next(get_db())
        
        try:
            from app.plugins.api_versioning.utils.version_manager import get_active_versions
            versions = get_active_versions(db_session)
            
            if versions:
                # Add available versions header
                versions_str = ",".join([v.version for v in versions])
                response.headers["X-API-Versions-Available"] = versions_str
            
            return response
            
        except Exception as e:
            logger.exception(f"Error in API version header middleware: {str(e)}")
            return response
        finally:
            # Close the database session
            db_session.close()
