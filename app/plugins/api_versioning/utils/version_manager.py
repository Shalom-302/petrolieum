"""
Utility functions for managing API versions.

This module contains core functionality for managing API versions, including
retrieving active versions, setting the default version, and routing requests
to the correct version handlers.
"""

import logging
from typing import List, Optional, Dict, Any, Callable
from fastapi import FastAPI, APIRouter, Request, Depends, HTTPException, status
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.api_versioning.models import APIVersion, APIEndpoint


logger = logging.getLogger(__name__)


def get_active_versions(db: Session) -> List[APIVersion]:
    """
    Get all active API versions.
    
    Args:
        db: Database session
        
    Returns:
        List of active API versions
    """
    return db.query(APIVersion).filter(APIVersion.is_active == True).order_by(APIVersion.version).all()


def get_deprecated_versions(db: Session) -> List[APIVersion]:
    """
    Get all deprecated API versions.
    
    Args:
        db: Database session
        
    Returns:
        List of deprecated API versions
    """
    return db.query(APIVersion).filter(
        APIVersion.is_deprecated == True,
        APIVersion.is_active == True
    ).order_by(APIVersion.version).all()


def get_default_version(db: Session) -> Optional[APIVersion]:
    """
    Get the default API version (usually the latest non-deprecated version).
    
    Args:
        db: Database session
        
    Returns:
        Default API version or None if no active versions exist
    """
    # Get latest active, non-deprecated version
    return db.query(APIVersion).filter(
        APIVersion.is_active == True,
        APIVersion.is_deprecated == False
    ).order_by(APIVersion.version.desc()).first()


def resolve_version_from_request(request: Request, db: Session) -> str:
    """
    Determine which API version to use based on the request.
    
    The version can be specified in multiple ways (in order of precedence):
    1. URL path prefix (e.g., /api...)
    2. Accept header with version parameter
    3. Custom X-API-Version header
    4. Default to the latest version
    
    Args:
        request: The FastAPI request object
        db: Database session
        
    Returns:
        Version string (e.g., 'v1')
    """
    # Check URL path
    path = request.url.path
    path_parts = path.strip('/').split('/')
    
    if len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1].startswith('v'):
        version = path_parts[1]
        # Verify this version exists and is active
        if db.query(APIVersion).filter(
            APIVersion.version == version,
            APIVersion.is_active == True
        ).first():
            return version
    
    # Check Accept header (e.g., "application/json;version=v1")
    accept_header = request.headers.get('Accept', '')
    if 'version=' in accept_header:
        for part in accept_header.split(';'):
            if part.strip().startswith('version='):
                version = part.strip().split('=')[1].strip()
                # Verify this version exists and is active
                if db.query(APIVersion).filter(
                    APIVersion.version == version,
                    APIVersion.is_active == True
                ).first():
                    return version
    
    # Check custom header
    custom_header = request.headers.get('X-API-Version')
    if custom_header:
        # Verify this version exists and is active
        if db.query(APIVersion).filter(
            APIVersion.version == custom_header,
            APIVersion.is_active == True
        ).first():
            return custom_header
    
    # Default to latest version
    default_version = get_default_version(db)
    if default_version:
        return default_version.version
    
    # Fallback to v1 if no versions exist yet
    return 'v1'


def create_version_router(app: FastAPI, version: str, prefix: str = "/api") -> APIRouter:
    """
    Create a router for a specific API version.
    
    Args:
        app: FastAPI application
        version: Version string (e.g., 'v1')
        prefix: API prefix (default: '/api')
        
    Returns:
        Router for the specified version
    """
    router = APIRouter(prefix=f"{prefix}/{version}")
    return router


def apply_version_dependency(
    routes: List[APIRoute],
    version: str,
    db: Session
) -> None:
    """
    Register routes for a specific API version in the database.
    
    Args:
        routes: List of API routes
        version: Version string (e.g., 'v1')
        db: Database session
    """
    # Find the version record
    version_record = db.query(APIVersion).filter(APIVersion.version == version).first()
    
    if not version_record:
        logger.warning(f"Version {version} not found in database during route registration")
        return
    
    # Register each route as an endpoint
    for route in routes:
        path = route.path
        for method in route.methods:
            # Extract handler information
            handler = route.endpoint
            handler_module = handler.__module__
            handler_function = handler.__name__
            
            # Check if endpoint already exists
            existing_endpoint = db.query(APIEndpoint).filter(
                APIEndpoint.path == path,
                APIEndpoint.method == method,
                APIEndpoint.version_id == version_record.id
            ).first()
            
            if not existing_endpoint:
                # Create new endpoint record
                endpoint = APIEndpoint(
                    path=path,
                    method=method,
                    version_id=version_record.id,
                    handler_module=handler_module,
                    handler_function=handler_function,
                    is_active=True
                )
                db.add(endpoint)
    
    # Commit changes
    db.commit()
    logger.info(f"Registered {len(routes)} routes for API version {version}")


def version_middleware(request: Request, db: Session = Depends(get_db)):
    """
    Middleware to handle API versioning.
    
    This middleware enforces the use of an active API version and can add
    deprecation warnings for deprecated versions.
    
    Args:
        request: FastAPI request
        db: Database session
    """
    # Extract version from request
    version = resolve_version_from_request(request, db)
    
    # Check if this version exists and is active
    version_record = db.query(APIVersion).filter(APIVersion.version == version).first()
    
    if not version_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API version '{version}' not found"
        )
    
    if not version_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API version '{version}' is not active"
        )
    
    # Add version to request state for later use
    request.state.api_version = version
    
    # Add deprecation warning header if version is deprecated
    if version_record.is_deprecated:
        # Get the default (latest) version
        default_version = get_default_version(db)
        
        # Return deprecation warning
        warning = f"API version '{version}' is deprecated."
        if default_version and default_version.version != version:
            warning += f" Please use version '{default_version.version}' instead."
        
        # Add headers to request state so they can be added to the response
        request.state.headers = {
            "Warning": f'299 - "{warning}"',
            "X-API-Deprecated": "true",
            "X-API-Recommended-Version": default_version.version if default_version else None
        }
    
    # Continue processing the request
    return None


def register_version_routes(app: FastAPI, db: Session) -> None:
    """
    Register all versioned routes from the database.
    
    This function loads all active API endpoint configurations from the database
    and registers them with the FastAPI application.
    
    Args:
        app: FastAPI application
        db: Database session
    """
    # Get all active versions
    active_versions = get_active_versions(db)
    
    for version in active_versions:
        # Create router for this version
        router = create_version_router(app, version.version)
        
        # Get all active endpoints for this version
        endpoints = db.query(APIEndpoint).filter(
            APIEndpoint.version_id == version.id,
            APIEndpoint.is_active == True
        ).all()
        
        # Register each endpoint
        for endpoint in endpoints:
            try:
                # Import the handler module
                module = __import__(endpoint.handler_module, fromlist=[endpoint.handler_function])
                
                # Get the handler function
                handler = getattr(module, endpoint.handler_function)
                
                # Add route to router
                router.add_api_route(
                    path=endpoint.path,
                    endpoint=handler,
                    methods=[endpoint.method],
                    name=f"{version.version}_{endpoint.path}_{endpoint.method}".replace("/", "_")
                )
                
                logger.info(f"Registered endpoint: {endpoint.method} {endpoint.path} for version {version.version}")
            
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to register endpoint {endpoint.path}: {str(e)}")
        
        # Include the router in the app
        app.include_router(router)
    
    # Log summary
    logger.info(f"Registered routes for {len(active_versions)} API versions")


def setup_versioning(app: FastAPI, db: Session) -> None:
    """
    Set up API versioning for a FastAPI application.
    
    This function initializes the versioning system by setting up middleware
    and registering routes.
    
    Args:
        app: FastAPI application
        db: Database session
    """
    # Check if we need to create a default version
    if db.query(APIVersion).count() == 0:
        # Create v1 as default
        default_version = APIVersion(
            version="v1",
            description="Initial API version",
            is_active=True,
            is_deprecated=False
        )
        db.add(default_version)
        db.commit()
        logger.info("Created default API version (v1)")
    
    # Add middleware for version resolution
    @app.middleware("http")
    async def versioning_middleware(request: Request, call_next):
        # Only apply to API routes
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Get DB session
        db_session = next(get_db())
        
        # Apply version middleware
        result = version_middleware(request, db_session)
        if result is not None:
            return result
        
        # Process request
        response = await call_next(request)
        
        # Add headers from request state if they exist
        if hasattr(request.state, "headers"):
            for header, value in request.state.headers.items():
                if value is not None:
                    response.headers[header] = value
        
        return response
    
    # Register versioned routes
    register_version_routes(app, db)
    
    logger.info("API versioning system initialized")
