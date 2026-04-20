"""
Middleware for the advanced authentication plugin.
"""
import logging
import time
from typing import Callable, Optional, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.db import SessionLocal
from app.plugins.advanced_auth.utils import decode_token
from app.plugins.advanced_auth.models import User, Session
from app.plugins.advanced_auth.exceptions import InvalidTokenException, ExpiredTokenException

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for authentication tracking and session management."""
    
    def __init__(self, app: ASGIApp):
        """Initialize the middleware."""
        super().__init__(app)
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request through middleware.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response
        """
        start_time = time.time()
        
        # Skip authentication for WebSocket connections and ws-direct routes
        if request.url.path.startswith("/ws-"):
            logger.info(f"AuthMiddleware: Bypassing auth checks for WebSocket connection to {request.url.path}")
            return await call_next(request)
        
        # Skip authentication tracking for static files and other non-API routes
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        
        # Extract the auth header
        auth_header = request.headers.get("Authorization")
        request.state.user = None
        request.state.session = None
        
        # Process the token if it exists
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            
            try:
                # Try to decode the token
                token_data = decode_token(token)
                user_id = token_data.get("sub")
                session_id = token_data.get("session_id")
                
                # If we have a user_id, try to get the user
                if user_id:
                    db = SessionLocal()
                    try:
                        # Get the user
                        user = db.query(User).filter(User.id == user_id).first()
                        
                        if user:
                            # Store the user in request state
                            request.state.user = user
                            
                            # If we have a session_id, get the session
                            if session_id:
                                session = db.query(Session).filter(
                                    Session.id == session_id,
                                    Session.user_id == user_id,
                                    Session.is_active == True
                                ).first()
                                
                                if session:
                                    # Store the session in request state
                                    request.state.session = session
                                    
                                    # Update session last activity
                                    session.last_activity = time.time()
                                    db.commit()
                    finally:
                        db.close()
            except Exception as e:
                # Just log the error, we don't want to interrupt the request flow
                logger.warning(f"Error processing authentication: {str(e)}")
        
        # Continue with the request
        response = await call_next(request)
        
        # Add some response headers
        response.headers["X-Process-Time"] = str(time.time() - start_time)
        
        return response

    async def __call__(self, scope, receive, send):
        # Skip authentication for WebSocket connections and ws-direct routes
        if scope["type"] == "websocket" or (scope["type"] == "http" and scope.get("path", "").startswith("/ws-")):
            print(f"AuthenticationMiddleware: Bypassing auth for {scope['type']} request to {scope.get('path')}")
            await self.app(scope, receive, send)
            return
        
        # Call the next middleware or route handler
        await self.dispatch(Request(scope), lambda request: self.app(scope, receive, send))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting authentication attempts."""
    
    def __init__(
        self,
        app: ASGIApp,
        rate_limit: int = 5,
        rate_limit_window: int = 60
    ):
        """
        Initialize the middleware.
        
        Args:
            app: The ASGI application
            rate_limit: Maximum number of requests per window
            rate_limit_window: Window size in seconds
        """
        super().__init__(app)
        self.rate_limit = rate_limit
        self.rate_limit_window = rate_limit_window
        self.ip_requests: Dict[str, Dict[str, Any]] = {}
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request through middleware.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response
        """
        # Only rate limit authentication endpoints
        if not self._is_auth_endpoint(request.url.path):
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host
        current_time = time.time()
        
        # Check if IP is in rate limit dictionary
        if client_ip in self.ip_requests:
            ip_data = self.ip_requests[client_ip]
            
            # Clean up old requests
            if current_time - ip_data["start_time"] > self.rate_limit_window:
                # Reset if window has expired
                self.ip_requests[client_ip] = {
                    "count": 1,
                    "start_time": current_time
                }
            else:
                # Increment request count
                ip_data["count"] += 1
                
                # Check if rate limit exceeded
                if ip_data["count"] > self.rate_limit:
                    # Return a rate limit exceeded response
                    return Response(
                        content="Rate limit exceeded. Please try again later.",
                        status_code=429,
                        headers={"Retry-After": str(self.rate_limit_window)}
                    )
        else:
            # First request from this IP
            self.ip_requests[client_ip] = {
                "count": 1,
                "start_time": current_time
            }
        
        # Continue with the request
        return await call_next(request)
    
    def _is_auth_endpoint(self, path: str) -> bool:
        """
        Check if the path is an authentication endpoint.
        
        Args:
            path: URL path
            
        Returns:
            True if the path is an authentication endpoint
        """
        auth_endpoints = [
            "/auth/login",
            "/auth/register",
            "/auth/reset-password",
        ]
        
        return any(path.startswith(endpoint) for endpoint in auth_endpoints)
