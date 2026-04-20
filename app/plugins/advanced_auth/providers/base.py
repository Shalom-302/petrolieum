"""
Base class for authentication providers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, List
from pydantic import BaseModel
import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AuthResult(BaseModel):
    """Model for authentication results."""
    success: bool
    user_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    user_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_description: Optional[str] = None


class UserInfo(BaseModel):
    """Model for standardized user information from providers."""
    id: str
    email: Optional[str] = None
    email_verified: Optional[bool] = False
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    picture: Optional[str] = None
    locale: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class AuthProvider(ABC):
    """Base class for all authentication providers."""
    
    name: str = "base"
    friendly_name: str = "Base Provider"
    icon: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with the given configuration.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = logging.getLogger(f"auth.provider.{self.name}")
    
    @abstractmethod
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Get the URL to redirect the user to for authorization.
        
        Args:
            redirect_uri: The URI to redirect to after authorization
            state: Optional state to include in the request
            
        Returns:
            URL to redirect the user to
        """
        pass
    
    @abstractmethod
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange an authorization code for an access token.
        
        Args:
            code: The authorization code
            redirect_uri: The redirect URI used in the authorization request
            
        Returns:
            Token response with access_token, refresh_token, etc.
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, access_token: str) -> UserInfo:
        """
        Get user information from the provider.
        
        Args:
            access_token: The access token to use for the request
            
        Returns:
            Standardized user information
        """
        pass
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New token response
        """
        raise NotImplementedError(f"refresh_token not implemented for {self.name} provider")
    
    async def revoke_token(self, token: str) -> bool:
        """
        Revoke an access or refresh token.
        
        Args:
            token: The token to revoke
            
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError(f"revoke_token not implemented for {self.name} provider")
    
    async def validate_token(self, token: str) -> bool:
        """
        Validate an access token.
        
        Args:
            token: The token to validate
            
        Returns:
            True if valid, False otherwise
        """
        raise NotImplementedError(f"validate_token not implemented for {self.name} provider")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def _log_request(self, method: str, url: str, **kwargs):
        """Log a request for audit purposes."""
        self.logger.info(f"Request: {method} {url}", extra={
            "auth_provider": self.name,
            "request_method": method,
            "request_url": url,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _log_response(self, method: str, url: str, status_code: int, **kwargs):
        """Log a response for audit purposes."""
        self.logger.info(f"Response: {method} {url} -> {status_code}", extra={
            "auth_provider": self.name,
            "request_method": method,
            "request_url": url,
            "response_status": status_code,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """
        Make an HTTP request with logging.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: The URL to request
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            HTTP response
        """
        self._log_request(method, url, **kwargs)
        response = await self.client.request(method, url, **kwargs)
        self._log_response(method, url, response.status_code)
        return response
