"""
OpenAPI Documentation Generator for the API Gateway plugin.

Generates OpenAPI documentation for the exposed API endpoints
based on the RouteRegistry information.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI, APIRouter

from ..routes.registry import RouteRegistry, RouteMetadata

# Setup logging
logger = logging.getLogger(__name__)


class OpenAPIGenerator:
    """Generator for OpenAPI documentation from the API Gateway route registry."""
    
    @classmethod
    def generate_openapi_spec(
        cls,
        title: str,
        description: str,
        version: str,
        app: FastAPI = None,
        include_internal_docs: bool = False
    ) -> Dict[str, Any]:
        """
        Generate OpenAPI specification from the registered routes.
        
        Args:
            title: Title of the API
            description: Description of the API
            version: Version of the API (not to be confused with endpoint versions)
            app: FastAPI app instance (if None, only includes routes from registry)
            include_internal_docs: Whether to include internal docs from app.openapi()
            
        Returns:
            OpenAPI specification as a dictionary
        """
        # Get all registered routes
        all_routes = RouteRegistry.get_all_routes()
        
        # Base OpenAPI schema
        openapi_schema = {
            "openapi": "3.0.2",
            "info": {
                "title": title,
                "description": description,
                "version": version,
                "contact": {
                    "name": "API Support"
                },
                "license": {
                    "name": "Private License"
                }
            },
            "paths": {},
            "components": {
                "securitySchemes": {
                    "ApiKeyHeader": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key"
                    },
                    "ApiKeyQuery": {
                        "type": "apiKey",
                        "in": "query",
                        "name": "api_key"
                    }
                },
                "schemas": {}
            },
            "tags": []
        }
        
        # If FastAPI app is provided, merge its OpenAPI schema
        if app and include_internal_docs:
            app_schema = get_openapi(
                title=title,
                version=version,
                description=description,
                routes=app.routes
            )
            # Merge paths and components
            openapi_schema["paths"].update(app_schema.get("paths", {}))
            
            # Merge schemas
            if "components" in app_schema and "schemas" in app_schema["components"]:
                openapi_schema["components"]["schemas"].update(app_schema["components"]["schemas"])
            
            # Merge tags
            if "tags" in app_schema:
                openapi_schema["tags"].extend(app_schema["tags"])
        
        # Process registered routes
        namespaces = RouteRegistry.get_all_namespaces()
        processed_tags = set()
        
        # Add tags for each namespace
        for namespace in namespaces:
            if namespace not in processed_tags:
                openapi_schema["tags"].append(
                    {"name": namespace, "description": f"API endpoints in the {namespace} namespace"}
                )
                processed_tags.add(namespace)
        
        # Add paths from registry
        for route in all_routes:
            cls._add_path_from_route(route, openapi_schema)
        
        return openapi_schema
    
    @classmethod
    def _add_path_from_route(cls, route: RouteMetadata, openapi_schema: Dict[str, Any]) -> None:
        """
        Add a path to the OpenAPI schema from a route metadata object.
        
        Args:
            route: Route metadata
            openapi_schema: OpenAPI schema to update
        """
        # If path doesn't exist in schema, initialize it
        if route.path not in openapi_schema["paths"]:
            openapi_schema["paths"][route.path] = {}
        
        # Security requirements
        security = []
        if route.permissions:
            security.append({"ApiKeyHeader": []})
            security.append({"ApiKeyQuery": []})
        
        # For each HTTP method in the route
        for method in route.methods:
            method_lower = method.lower()
            
            # Skip if method already defined for this path
            if method_lower in openapi_schema["paths"][route.path]:
                logger.warning(f"Duplicate method {method} for path {route.path}, skipping")
                continue
            
            # Create operation object
            operation = {
                "summary": route.summary or f"{method} {route.name}",
                "description": route.description or f"API endpoint for {route.name}",
                "tags": route.tags,
                "responses": {
                    "200": {
                        "description": "Successful Response",
                        "content": {}
                    },
                    "400": {
                        "description": "Bad Request"
                    },
                    "401": {
                        "description": "Unauthorized"
                    },
                    "403": {
                        "description": "Forbidden"
                    },
                    "429": {
                        "description": "Too Many Requests"
                    },
                    "500": {
                        "description": "Internal Server Error"
                    }
                },
                "deprecated": route.deprecated
            }
            
            # Add security if required
            if security:
                operation["security"] = security
            
            # Add response model schema if available
            if route.response_model:
                model_name = cls._get_model_name(route.response_model)
                if model_name:
                    # Add model schema to components
                    cls._add_model_to_components(route.response_model, openapi_schema)
                    
                    # Reference the model in responses
                    operation["responses"]["200"]["content"] = {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{model_name}"}
                        }
                    }
            
            # Add operation to path
            openapi_schema["paths"][route.path][method_lower] = operation
    
    @classmethod
    def _get_model_name(cls, model: Any) -> Optional[str]:
        """
        Get the name of a Pydantic model.
        
        Args:
            model: Pydantic model
            
        Returns:
            Model name or None if not a valid model
        """
        try:
            # Check if the model has a schema method (Pydantic models do)
            if hasattr(model, 'schema') and callable(getattr(model, 'schema')):
                return model.__name__
        except (AttributeError, Exception):
            pass
        return None
    
    @classmethod
    def _add_model_to_components(cls, model: Any, openapi_schema: Dict[str, Any]) -> None:
        """
        Add a Pydantic model schema to the OpenAPI components.
        
        Args:
            model: Pydantic model
            openapi_schema: OpenAPI schema to update
        """
        model_name = cls._get_model_name(model)
        if not model_name or model_name in openapi_schema["components"]["schemas"]:
            return
        
        try:
            # Get model schema
            schema = model.schema()
            # Add to components
            openapi_schema["components"]["schemas"][model_name] = schema
            
            # Process nested models
            for prop_name, prop_schema in schema.get("properties", {}).items():
                if "$ref" in prop_schema:
                    # Extract referenced model name from $ref
                    ref_parts = prop_schema["$ref"].split("/")
                    ref_model_name = ref_parts[-1]
                    
                    # Find the model class and add it
                    for attr_name in dir(model):
                        attr = getattr(model, attr_name)
                        if cls._get_model_name(attr) == ref_model_name:
                            cls._add_model_to_components(attr, openapi_schema)
        except (AttributeError, Exception) as e:
            logger.warning(f"Failed to add model {model_name} to schema: {e}")
    
    @classmethod
    def create_api_docs_router(
        cls, 
        title: str,
        description: str,
        version: str,
        include_swagger_ui: bool = True,
        include_redoc: bool = True
    ) -> APIRouter:
        """
        Create an API router with documentation endpoints.
        
        Args:
            title: API title
            description: API description
            version: API version
            include_swagger_ui: Whether to include SwaggerUI endpoint
            include_redoc: Whether to include ReDoc endpoint
            
        Returns:
            FastAPI router with documentation endpoints
        """
        router = APIRouter()
        
        @router.get("/openapi.json", tags=["Documentation"])
        async def get_openapi_json():
            """Get the OpenAPI specification in JSON format."""
            return cls.generate_openapi_spec(title, description, version)
        
        if include_swagger_ui:
            from fastapi.openapi.docs import get_swagger_ui_html
            
            @router.get("/docs", tags=["Documentation"])
            async def get_swagger_ui():
                """Get the Swagger UI for API documentation."""
                return get_swagger_ui_html(
                    openapi_url="/api/openapi.json",
                    title=f"{title} - Swagger UI"
                )
        
        if include_redoc:
            from fastapi.openapi.docs import get_redoc_html
            
            @router.get("/redoc", tags=["Documentation"])
            async def get_redoc():
                """Get the ReDoc UI for API documentation."""
                return get_redoc_html(
                    openapi_url="/api/openapi.json",
                    title=f"{title} - ReDoc"
                )
        
        return router
