"""
Utility functions for generating OpenAPI documentation for versioned APIs.

This module provides functions to generate OpenAPI schema documents for 
specific API versions based on the registered endpoints.
"""

import logging
import importlib
import inspect
from typing import Dict, Any, List
from fastapi import FastAPI, APIRouter
from fastapi.openapi.utils import get_openapi
from sqlalchemy.orm import Session

from app.plugins.api_versioning.models import APIVersion, APIEndpoint


logger = logging.getLogger(__name__)


def generate_openapi_schema(version: str, db: Session) -> Dict[str, Any]:
    """
    Generate an OpenAPI schema document for a specific API version.
    
    Args:
        version: Version string (e.g., 'v1')
        db: Database session
        
    Returns:
        OpenAPI schema document as a dictionary
    """
    # Create a temporary FastAPI app for schema generation
    temp_app = FastAPI(title=f"Kaapi API {version}", version=version)
    
    # Get version info
    version_info = db.query(APIVersion).filter(APIVersion.version == version).first()
    if not version_info:
        logger.error(f"API version '{version}' not found")
        return {}
    
    # Get all endpoints for this version
    endpoints = db.query(APIEndpoint).filter(
        APIEndpoint.version_id == version_info.id,
        APIEndpoint.is_active == True
    ).all()
    
    # Create a router for this version
    router = APIRouter()
    
    # Add endpoints to the router
    for endpoint in endpoints:
        try:
            # Import the handler module
            module = importlib.import_module(endpoint.handler_module)
            
            # Get the handler function
            handler_func = getattr(module, endpoint.handler_function, None)
            
            if handler_func:
                # Extract path parameters
                path_params = extract_path_parameters(endpoint.path)
                
                # Add route to router
                router.add_api_route(
                    path=endpoint.path,
                    endpoint=handler_func,
                    methods=[endpoint.method],
                    name=f"{endpoint.path}_{endpoint.method}".replace("/", "_")
                )
                logger.debug(f"Added route {endpoint.method} {endpoint.path} to schema generator")
            else:
                logger.warning(f"Handler function {endpoint.handler_function} not found in module {endpoint.handler_module}")
        
        except Exception as e:
            logger.error(f"Error adding endpoint {endpoint.method} {endpoint.path} to schema: {str(e)}")
    
    # Include router in the app
    temp_app.include_router(router)
    
    # Generate OpenAPI schema
    openapi_schema = get_openapi(
        title=f"Kaapi API {version}",
        version=version,
        description=version_info.description or f"API {version} for Kaapi application",
        routes=temp_app.routes,
    )
    
    # Add API version info
    openapi_schema["info"]["x-api-version"] = version
    if version_info.is_deprecated:
        openapi_schema["info"]["x-deprecated"] = True
        if version_info.deprecation_date:
            openapi_schema["info"]["x-deprecation-date"] = version_info.deprecation_date.isoformat()
        if version_info.sunset_date:
            openapi_schema["info"]["x-sunset-date"] = version_info.sunset_date.isoformat()
    
    # Add servers section
    openapi_schema["servers"] = [
        {"url": f"/api/{version}", "description": f"API {version}"}
    ]
    
    # Add security schemes if needed
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for authentication"
        },
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token for authentication"
        }
    }
    
    return openapi_schema


def extract_path_parameters(path: str) -> List[str]:
    """
    Extract parameter names from a path string.
    
    Args:
        path: API path (e.g., '/users/{user_id}/posts/{post_id}')
        
    Returns:
        List of parameter names
    """
    params = []
    parts = path.split('/')
    
    for part in parts:
        if part.startswith('{') and part.endswith('}'):
            # Extract parameter name
            param_name = part[1:-1]
            params.append(param_name)
    
    return params


def extract_endpoint_info(handler_func) -> Dict[str, Any]:
    """
    Extract information about an endpoint from its handler function.
    
    Args:
        handler_func: The handler function for the endpoint
        
    Returns:
        Dictionary containing information about the endpoint
    """
    # Initialize result dictionary
    result = {
        "description": "",
        "parameters": [],
        "responses": {},
        "tags": []
    }
    
    # Extract docstring
    if handler_func.__doc__:
        result["description"] = handler_func.__doc__.strip()
    
    # Extract annotations
    annotations = getattr(handler_func, "__annotations__", {})
    
    # Extract response model
    if "return" in annotations:
        response_model = annotations["return"]
        # TODO: Convert response model to schema
    
    # Extract dependencies
    # This is a simplified implementation and might need more work
    signature = inspect.signature(handler_func)
    
    for param_name, param in signature.parameters.items():
        if param_name in ["request", "response"]:
            continue
            
        # Handle path parameters
        if param_name in annotations:
            param_type = annotations[param_name]
            param_info = {
                "name": param_name,
                "in": "path",  # Assume path for now
                "required": True,
                "schema": {"type": "string"}  # Default to string
            }
            result["parameters"].append(param_info)
    
    return result
