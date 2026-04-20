"""
OpenAPI documentation generator for the API Gateway plugin.

Automatically generates comprehensive API documentation from registered endpoints,
including authentication, request/response schemas, and examples.
"""

import inspect
import logging
from typing import Dict, Any, List, Optional, Type
from datetime import datetime

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

from app.core.config import settings
from ..routes.registry import ApiRegistry, ApiEndpointInfo

# Setup logging
logger = logging.getLogger(__name__)

# Store generated documentation
_api_documentation: Dict[str, Any] = {}

def generate_api_documentation(app: FastAPI, registry: ApiRegistry) -> Dict[str, Any]:
    """
    Generate OpenAPI documentation for exposed API endpoints.
    
    Args:
        app: FastAPI application
        registry: API registry
        
    Returns:
        OpenAPI specification as dictionary
    """
    global _api_documentation
    
    # Base OpenAPI schema from FastAPI
    openapi_schema = get_openapi(
        title="Secure API Gateway",
        version="1.0.0",
        description="Secure API for external integrations with robust authentication and authorization",
        routes=app.routes,
    )
    
    # Add API key security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for authentication"
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    
    # Enhance with additional information from registry
    endpoints_by_path = {}
    for endpoint in registry.get_all_routes():
        if endpoint.path not in endpoints_by_path:
            endpoints_by_path[endpoint.path] = []
        endpoints_by_path[endpoint.path].append(endpoint)
    
    # Process paths and operations
    for path, path_item in openapi_schema.get("paths", {}).items():
        # Skip if this path is not in our registry
        registry_endpoints = endpoints_by_path.get(path, [])
        if not registry_endpoints:
            continue
        
        # Process each operation (HTTP method) in this path
        for method in ["get", "post", "put", "delete"]:
            if method not in path_item:
                continue
            
            # Find the matching endpoint in registry
            matching_endpoint = next(
                (e for e in registry_endpoints if e.method.lower() == method),
                None
            )
            
            if not matching_endpoint:
                continue
            
            # Enhance operation with additional information
            operation = path_item[method]
            
            # Add namespace and version information
            if "x-metadata" not in operation:
                operation["x-metadata"] = {}
            
            operation["x-metadata"]["namespace"] = matching_endpoint.namespace
            operation["x-metadata"]["version"] = matching_endpoint.version
            
            # Add required permissions/scopes
            if matching_endpoint.requires:
                if "security" not in operation:
                    operation["security"] = [{"ApiKeyAuth": []}]
                
                operation["x-required-permissions"] = matching_endpoint.requires
                
                # Add description about required permissions
                if operation.get("description"):
                    operation["description"] += "\n\n"
                else:
                    operation["description"] = ""
                
                operation["description"] += f"Required permissions: {', '.join(matching_endpoint.requires)}"
            
            # Add rate limit information if specified
            if matching_endpoint.rate_limit:
                if "x-metadata" not in operation:
                    operation["x-metadata"] = {}
                
                operation["x-metadata"]["rate-limit"] = matching_endpoint.rate_limit
                
                # Add description about rate limits
                if operation.get("description"):
                    operation["description"] += "\n\n"
                
                operation["description"] += f"Rate limit: {matching_endpoint.rate_limit}"
            
            # Add response headers for rate limiting
            for status_code in operation.get("responses", {}):
                response = operation["responses"][status_code]
                
                if "headers" not in response:
                    response["headers"] = {}
                
                # Add rate limit headers
                response["headers"]["X-RateLimit-Limit"] = {
                    "schema": {"type": "integer"},
                    "description": "Rate limit ceiling for the endpoint"
                }
                
                response["headers"]["X-RateLimit-Remaining"] = {
                    "schema": {"type": "integer"},
                    "description": "Number of requests left for the time window"
                }
                
                response["headers"]["X-RateLimit-Reset"] = {
                    "schema": {"type": "integer"},
                    "description": "Time in seconds until the rate limit resets"
                }
            
            # Add response examples if possible
            response_model = matching_endpoint.response_model
            if response_model and hasattr(response_model, "__annotations__"):
                try:
                    # Create a sample response based on the model
                    sample = generate_sample_from_model(response_model)
                    
                    # Add to the "200" response content
                    if "200" in operation.get("responses", {}):
                        if "content" not in operation["responses"]["200"]:
                            operation["responses"]["200"]["content"] = {
                                "application/json": {"example": {}}
                            }
                        
                        operation["responses"]["200"]["content"]["application/json"]["example"] = sample
                except Exception as e:
                    logger.warning(f"Failed to generate sample response for {path}.{method}: {str(e)}")
    
    # Add general information
    openapi_schema["info"]["contact"] = {
        "name": "API Support",
        "email": settings.EMAILS_FROM_EMAIL if hasattr(settings, "EMAILS_FROM_EMAIL") else "support@example.com",
        "url": settings.SERVER_HOST if hasattr(settings, "SERVER_HOST") else "https://example.com"
    }
    
    openapi_schema["info"]["termsOfService"] = f"{settings.SERVER_HOST}/terms" if hasattr(settings, "SERVER_HOST") else "https://example.com/terms"
    
    openapi_schema["info"]["x-generated-at"] = datetime.utcnow().isoformat()
    openapi_schema["info"]["x-endpoints-count"] = len(registry.get_all_routes())
    
    # Store documentation for later access
    _api_documentation = openapi_schema
    
    logger.info(f"Generated API documentation with {len(registry.get_all_routes())} endpoints")
    
    return openapi_schema


def get_api_documentation() -> Dict[str, Any]:
    """
    Get the generated API documentation.
    
    Returns:
        OpenAPI specification as dictionary
    """
    global _api_documentation
    return _api_documentation


def generate_sample_from_model(model: Type[BaseModel]) -> Dict[str, Any]:
    """
    Generate a sample instance from a Pydantic model.
    
    Args:
        model: Pydantic model class
        
    Returns:
        Sample data as dictionary
    """
    # This is a simplified implementation
    # A complete implementation would recursively handle nested models,
    # unions, lists, and other complex types
    
    sample = {}
    
    for field_name, field in model.__annotations__.items():
        # Skip private fields
        if field_name.startswith("_"):
            continue
        
        # Generate sample value based on type
        if field == str:
            sample[field_name] = f"example_{field_name}"
        elif field == int:
            sample[field_name] = 42
        elif field == float:
            sample[field_name] = 3.14
        elif field == bool:
            sample[field_name] = True
        elif field == dict:
            sample[field_name] = {"key": "value"}
        elif field == list:
            sample[field_name] = ["example"]
        elif hasattr(field, "__origin__") and field.__origin__ == list:
            # List with type parameter, e.g., List[str]
            item_type = field.__args__[0] if hasattr(field, "__args__") else str
            
            if item_type == str:
                sample[field_name] = ["example1", "example2"]
            elif item_type == int:
                sample[field_name] = [1, 2, 3]
            elif item_type == float:
                sample[field_name] = [1.0, 2.0, 3.0]
            elif item_type == bool:
                sample[field_name] = [True, False]
            elif hasattr(item_type, "__annotations__"):
                # Nested model in list
                try:
                    nested_sample = generate_sample_from_model(item_type)
                    sample[field_name] = [nested_sample]
                except:
                    sample[field_name] = [{"example": "nested_item"}]
            else:
                sample[field_name] = ["example1", "example2"]
        elif hasattr(field, "__annotations__"):
            # Nested model
            try:
                sample[field_name] = generate_sample_from_model(field)
            except:
                sample[field_name] = {"example": "nested_object"}
        else:
            # Default fallback
            sample[field_name] = "example"
    
    return sample
