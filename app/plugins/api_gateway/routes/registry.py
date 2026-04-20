"""
Route Registry module for the API Gateway plugin.

Provides a centralized registry for all exposed API endpoints, their versions,
and metadata to facilitate API discovery and documentation.
"""

import logging
from typing import Dict, List, Optional, Any, Set, Callable
from pydantic import BaseModel, Field

# Setup logging
logger = logging.getLogger(__name__)

class RouteMetadata(BaseModel):
    """Metadata for an API route."""
    
    path: str
    methods: Set[str]
    name: str
    namespace: str
    version: str
    summary: Optional[str] = None
    description: Optional[str] = None
    permissions: List[str] = []
    tags: List[str] = []
    deprecated: bool = False
    response_model: Optional[Any] = None
    handler: Callable


class RouteRegistry:
    """Registry of all exposed API routes."""
    
    _routes: Dict[str, Dict[str, RouteMetadata]] = {}  # {namespace: {route_name: metadata}}
    _versions: Dict[str, Set[str]] = {}  # {namespace: {versions}}
    
    @classmethod
    def register_route(
        cls,
        path: str,
        methods: Set[str],
        name: str,
        namespace: str,
        version: str,
        handler: Callable,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        permissions: List[str] = None,
        tags: List[str] = None,
        deprecated: bool = False,
        response_model: Optional[Any] = None
    ) -> None:
        """
        Register an API route.
        
        Args:
            path: URL path for the route
            methods: HTTP methods supported by the route
            name: Unique name for the route
            namespace: Namespace for the route (e.g., 'payments', 'users')
            version: API version (e.g., 'v1', 'v2')
            handler: Function that handles the route
            summary: Short summary of what the route does
            description: Detailed description of the route
            permissions: List of required permissions in format "namespace:resource:action"
            tags: Tags for grouping in documentation
            deprecated: Whether the route is deprecated
            response_model: Pydantic model for the response
        """
        # Initialize namespace if not exists
        if namespace not in cls._routes:
            cls._routes[namespace] = {}
            cls._versions[namespace] = set()
        
        # Add version to the set of versions for this namespace
        cls._versions[namespace].add(version)
        
        # Create the route metadata
        route_id = f"{namespace}.{name}.{version}"
        metadata = RouteMetadata(
            path=path,
            methods=methods,
            name=name,
            namespace=namespace,
            version=version,
            summary=summary,
            description=description,
            permissions=permissions or [],
            tags=tags or [namespace],
            deprecated=deprecated,
            response_model=response_model,
            handler=handler
        )
        
        # Register the route
        cls._routes[namespace][route_id] = metadata
        
        logger.info(f"Registered API route: {route_id} at {path} [{', '.join(methods)}]")
    
    @classmethod
    def get_route(cls, namespace: str, name: str, version: str) -> Optional[RouteMetadata]:
        """
        Get a route by its identifier.
        
        Args:
            namespace: Namespace for the route
            name: Name of the route
            version: API version
            
        Returns:
            RouteMetadata if found, None otherwise
        """
        route_id = f"{namespace}.{name}.{version}"
        return cls._routes.get(namespace, {}).get(route_id)
    
    @classmethod
    def get_routes_by_namespace(cls, namespace: str) -> List[RouteMetadata]:
        """
        Get all routes for a namespace.
        
        Args:
            namespace: Namespace to get routes for
            
        Returns:
            List of RouteMetadata
        """
        return list(cls._routes.get(namespace, {}).values())
    
    @classmethod
    def get_all_routes(cls) -> List[RouteMetadata]:
        """
        Get all registered routes.
        
        Returns:
            List of RouteMetadata
        """
        all_routes = []
        for namespace_routes in cls._routes.values():
            all_routes.extend(namespace_routes.values())
        return all_routes
    
    @classmethod
    def get_versions(cls, namespace: str) -> List[str]:
        """
        Get all versions for a namespace.
        
        Args:
            namespace: Namespace to get versions for
            
        Returns:
            List of versions
        """
        return sorted(cls._versions.get(namespace, set()))
    
    @classmethod
    def get_all_namespaces(cls) -> List[str]:
        """
        Get all registered namespaces.
        
        Returns:
            List of namespace names
        """
        return list(cls._routes.keys())
    
    @classmethod
    def get_latest_version(cls, namespace: str) -> Optional[str]:
        """
        Get the latest version for a namespace.
        
        Args:
            namespace: Namespace to get latest version for
            
        Returns:
            Latest version string or None if namespace not found
        """
        versions = cls.get_versions(namespace)
        return versions[-1] if versions else None
    
    @classmethod
    def get_routes_by_path_pattern(cls, path_pattern: str) -> List[RouteMetadata]:
        """
        Get routes that match a path pattern.
        
        Args:
            path_pattern: Path pattern to match
            
        Returns:
            List of RouteMetadata
        """
        matching_routes = []
        
        for namespace_routes in cls._routes.values():
            for route in namespace_routes.values():
                # Simple pattern matching (can be enhanced with regex)
                if path_pattern in route.path or route.path == path_pattern:
                    matching_routes.append(route)
        
        return matching_routes
    
    @classmethod
    def unregister_route(cls, namespace: str, name: str, version: str) -> bool:
        """
        Unregister a route.
        
        Args:
            namespace: Namespace for the route
            name: Name of the route
            version: API version
            
        Returns:
            True if route was unregistered, False if not found
        """
        route_id = f"{namespace}.{name}.{version}"
        
        if namespace in cls._routes and route_id in cls._routes[namespace]:
            # Remove the route
            removed = cls._routes[namespace].pop(route_id)
            
            # Remove the version if no more routes use it
            version_in_use = False
            for route in cls._routes[namespace].values():
                if route.version == version:
                    version_in_use = True
                    break
            
            if not version_in_use:
                cls._versions[namespace].discard(version)
            
            # Remove the namespace if empty
            if not cls._routes[namespace]:
                cls._routes.pop(namespace)
                cls._versions.pop(namespace)
            
            logger.info(f"Unregistered API route: {route_id}")
            return True
        
        return False
