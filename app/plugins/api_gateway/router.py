"""
API Gateway Router module.

Provides the main FastAPI router for the API Gateway plugin with
security middleware, rate limiting, and request auditing.
"""

import logging
import time
import uuid
from typing import Callable, Dict, List, Optional, Union, Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.middleware.base import BaseHTTPMiddleware

from sqlalchemy.orm import Session

from .config import ApiGatewayConfig
from .routes.registry import RouteRegistry, RouteMetadata
from .models.api_key import ApiKeyDB
from .models.audit import ApiAuditLogDB
from .models.rate_limit import RateLimitDB
from .security.auth import ApiKeyAuth, get_api_key_auth
from .docs.openapi import OpenAPIGenerator

# Setup logging
logger = logging.getLogger(__name__)


class ApiGatewayMiddleware(BaseHTTPMiddleware):
    """Middleware for the API Gateway to handle auditing, rate limiting, and security."""
    
    def __init__(
        self,
        app: FastAPI,
        api_key_auth: ApiKeyAuth,
        config: ApiGatewayConfig
    ):
        """Initialize the middleware with the API key auth instance."""
        super().__init__(app)
        self.api_key_auth = api_key_auth
        self.config = config
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process the request through the middleware pipeline."""
        # Skip middleware for non-API routes
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        
        # Create audit log entry
        audit_log = None
        if self.config.enable_audit_logging:
            request_id = str(uuid.uuid4())
            audit_log = ApiAuditLogDB.log_request(
                request_id=request_id,
                path=request.url.path,
                method=request.method,
                endpoint=request.url.path,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get('user-agent'),
                origin=request.headers.get('origin')
            )
        
        start_time = time.time()
        status_code = 500  # Default status code for error handling
        exception_message = None
        
        try:
            # Process the request through the rest of the middleware and route handlers
            response = await call_next(request)
            status_code = response.status_code
            return response
            
        except HTTPException as exc:
            # Handle HTTP exceptions from route handlers
            status_code = exc.status_code
            exception_message = str(exc.detail)
            raise
            
        except Exception as exc:
            # Handle unexpected exceptions
            status_code = 500
            exception_message = str(exc)
            logger.exception(f"Unexpected error in API Gateway: {exc}")
            raise
            
        finally:
            # Complete the audit log
            if audit_log and self.config.enable_audit_logging:
                duration = time.time() - start_time
                audit_log.complete_log(
                    status_code=status_code,
                    response_time_ms=int(duration * 1000)
                )


class ApiGatewayRouter:
    """Router for the API Gateway plugin."""
    
    def __init__(
        self,
        app: FastAPI,
        db_session: Callable[[], Session],
        config: ApiGatewayConfig = None
    ):
        """
        Initialize the API Gateway router.
        
        Args:
            app: FastAPI application
            db_session: Function that returns a database session
            config: API Gateway configuration
        """
        self.app = app
        self.db_session = db_session
        self.config = config or ApiGatewayConfig()
        
        # API router for external API endpoints
        self.api_router = APIRouter(prefix="/api")
        
        # API router for API Gateway management
        self.admin_router = APIRouter(prefix=self.config.admin_base_path)
        
        # API key security schemes
        self.api_key_header = APIKeyHeader(
            name=self.config.api_key_header_name,
            auto_error=False
        )
        self.api_key_query = APIKeyQuery(
            name=self.config.api_key_query_param,
            auto_error=False
        )
        
        # Initialize API key authentication handler
        self.api_key_auth = ApiKeyAuth(db_session, self.config)
        
        # Setup middleware
        self._setup_middleware()
        
        # Setup documentation routes
        self._setup_docs_routes()
        
        # Register API Gateway dependencies
        self._register_dependencies()
    
    def _setup_middleware(self) -> None:
        """Setup middleware for CORS, auditing, and rate limiting."""
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_allow_origins,
            allow_credentials=self.config.cors_allow_credentials,
            allow_methods=self.config.cors_allow_methods,
            allow_headers=self.config.cors_allow_headers,
            expose_headers=self.config.cors_expose_headers,
            max_age=self.config.cors_max_age
        )
        
        # Add API Gateway middleware
        self.app.add_middleware(
            ApiGatewayMiddleware,
            api_key_auth=self.api_key_auth,
            config=self.config
        )
        
        # Add custom middlewares
        for middleware_config in self.config.custom_middlewares:
            middleware_class = middleware_config.get("class")
            middleware_args = middleware_config.get("args", {})
            
            if middleware_class:
                try:
                    self.app.add_middleware(middleware_class, **middleware_args)
                    logger.info(f"Added custom middleware: {middleware_class.__name__}")
                except Exception as e:
                    logger.error(f"Failed to add custom middleware {middleware_class.__name__}: {e}")
    
    def _setup_docs_routes(self) -> None:
        """Setup API documentation routes."""
        docs_router = OpenAPIGenerator.create_api_docs_router(
            title=self.config.api_title,
            description=self.config.api_description,
            version=self.config.api_version,
            include_swagger_ui=True,
            include_redoc=True
        )
        
        # Add docs router to main API router
        self.api_router.include_router(docs_router)
    
    def _register_dependencies(self) -> None:
        """Register API Gateway dependencies with the FastAPI app."""
        # Register the API key auth dependency
        self.app.dependency_overrides[get_api_key_auth] = lambda: self.api_key_auth
    
    def include_router(
        self,
        router: APIRouter,
        namespace: str,
        version: str = None,
        requires_api_key: bool = True,
        permissions: List[str] = None,
        tags: List[str] = None
    ) -> None:
        """
        Include a router in the API Gateway.
        
        Args:
            router: FastAPI router to include
            namespace: Namespace for the router
            version: API version (defaults to config.default_version)
            requires_api_key: Whether routes require an API key
            permissions: Required permissions for all routes in the router
            tags: Tags for all routes in the router
        """
        version = version or self.config.default_version
        permissions = permissions or []
        tags = tags or [namespace]
        
        # Process each route in the router
        for route in router.routes:
            # Extract route metadata
            route_path = route.path
            methods = set(route.methods) if route.methods else {"GET"}
            name = route.name or route_path.split("/")[-1]
            
            # Register the route in the registry
            RouteRegistry.register_route(
                path=f"/api/{version}/{namespace}{route_path}",
                methods=methods,
                name=name,
                namespace=namespace,
                version=version,
                handler=route.endpoint,
                summary=route.summary,
                description=route.description,
                permissions=permissions,
                tags=tags,
                deprecated=getattr(route, "deprecated", False),
                response_model=getattr(route.endpoint, "response_model", None)
            )
        
        # Prepare version prefix
        version_prefix = f"/{version}" if self.config.enable_version_in_url else ""
        
        # Include the router in the API router with version prefix
        self.api_router.include_router(
            router,
            prefix=f"{version_prefix}/{namespace}",
            tags=tags
        )
        
        logger.info(f"Registered API namespace: {namespace} (version: {version})")
    
    def register_admin_routes(self) -> None:
        """Register administration routes for the API Gateway plugin."""
        from .admin.routes import get_admin_router
        
        admin_router = get_admin_router(self.config)
        self.app.include_router(
            admin_router,
            prefix=self.config.admin_base_path,
            tags=["API Gateway Admin"]
        )
        
        logger.info(f"Registered API Gateway admin routes at {self.config.admin_base_path}")
    
    def initialize(self) -> None:
        """Initialize the API Gateway and include all routers."""
        # Include API router in the FastAPI app
        self.app.include_router(self.api_router)
        
        # Register admin routes
        self.register_admin_routes()
        
        logger.info("API Gateway initialized successfully")
    
    def require_api_key(
        self,
        permissions: List[str] = None,
        optional: bool = False
    ) -> Callable:
        """
        Dependency for requiring an API key with specific permissions.
        
        Args:
            permissions: List of required permissions (empty list for any valid key)
            optional: Whether the API key is optional
            
        Returns:
            Dependency function for FastAPI
        """
        async def _get_api_key(
            request: Request,
            api_key_header: str = Depends(self.api_key_header),
            api_key_query: str = Depends(self.api_key_query)
        ) -> Optional[ApiKeyDB]:
            """Get and validate the API key from header or query parameter."""
            # Get the API key from header or query parameter
            api_key = api_key_header or api_key_query
            
            if not api_key and not optional:
                raise HTTPException(
                    status_code=401,
                    detail="Missing API key"
                )
            
            if not api_key and optional:
                return None
            
            # Verify the API key and check permissions
            auth_result = await self.api_key_auth.authenticate(
                api_key=api_key,
                permissions=permissions or [],
                request=request
            )
            
            if auth_result.is_authenticated:
                return auth_result.api_key
            
            # If key is optional and invalid, return None
            if optional:
                return None
            
            # Otherwise, raise an appropriate exception
            if auth_result.error_code == "invalid_key":
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API key"
                )
            elif auth_result.error_code == "expired_key":
                raise HTTPException(
                    status_code=401,
                    detail="Expired API key"
                )
            elif auth_result.error_code == "insufficient_permissions":
                raise HTTPException(
                    status_code=403,
                    detail="Insufficient permissions for this operation"
                )
            elif auth_result.error_code == "ip_restricted":
                raise HTTPException(
                    status_code=403,
                    detail="Access denied from this IP address"
                )
            elif auth_result.error_code == "origin_restricted":
                raise HTTPException(
                    status_code=403,
                    detail="Access denied from this origin"
                )
            elif auth_result.error_code == "rate_limited":
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded"
                )
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication failed"
                )
        
        return _get_api_key
