"""
Facebook OAuth authentication provider.
"""
from typing import Dict, Any, Optional, List, Union
import logging
from urllib.parse import urlencode
import json
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.user import User
from ..utils.token import create_access_token, create_refresh_token
from .base import AuthProvider, AuthResult, UserInfo


logger = logging.getLogger(__name__)


class FacebookAuthProvider(AuthProvider):
    """Facebook OAuth authentication provider."""
    
    name = "facebook"
    friendly_name = "Facebook"
    icon = "facebook"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Facebook authentication provider.
        
        Args:
            config: Provider configuration including client_id and client_secret
        """
        super().__init__(config)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Facebook provider requires client_id and client_secret")
        
        self.auth_url = "https://www.facebook.com/v16.0/dialog/oauth"
        self.token_url = "https://graph.facebook.com/v16.0/oauth/access_token"
        self.api_base_url = "https://graph.facebook.com/v16.0"
    
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Get the Facebook authorization URL.
        
        Args:
            redirect_uri: The URI to redirect to after authorization
            state: Optional state to include in the request
            
        Returns:
            Facebook authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "email,public_profile",
        }
        
        if state:
            params["state"] = state
            
        return f"{self.auth_url}?{urlencode(params)}"
    
    async def get_access_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange an authorization code for an access token.
        
        Args:
            code: Authorization code received from Facebook
            redirect_uri: Redirect URI used in the authorization request
            
        Returns:
            Access token response
            
        Raises:
            Exception: If token exchange fails
        """
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        
        try:
            async with self.client.post(self.token_url, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Facebook token exchange error: {error_text}")
                    raise Exception(f"Failed to exchange code for token: {error_text}")
                
                return await response.json()
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            raise
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Implémentation de la méthode abstraite requise par la classe AuthProvider.
        
        Args:
            code: Authorization code received from Facebook
            redirect_uri: Redirect URI used in the authorization request
            
        Returns:
            Token response with access_token, refresh_token, etc.
        """
        return await self.get_access_token(code, redirect_uri)
    
    async def get_user_info(self, access_token: str) -> UserInfo:
        """
        Get user information from Facebook.
        
        Args:
            access_token: Access token for the Facebook API
            
        Returns:
            User information
            
        Raises:
            Exception: If user info request fails
        """
        params = {
            "access_token": access_token,
            "fields": "id,email,first_name,last_name,picture"
        }
        
        try:
            async with self.client.get(f"{self.api_base_url}/me", params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Facebook user info error: {error_text}")
                    raise Exception(f"Failed to get user info: {error_text}")
                
                data = await response.json()
                
                return UserInfo(
                    provider=self.name,
                    provider_user_id=data.get("id"),
                    email=data.get("email"),
                    username=data.get("email"),
                    first_name=data.get("first_name"),
                    last_name=data.get("last_name"),
                    picture=data.get("picture", {}).get("data", {}).get("url") if "picture" in data else None,
                    raw_data=data
                )
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            raise
    
    async def authenticate(self, code: str, redirect_uri: str, state: Optional[str] = None) -> AuthResult:
        """
        Authenticate a user with Facebook.
        
        Args:
            code: Authorization code received from Facebook
            redirect_uri: Redirect URI used in the authorization request
            state: Optional state from the request
            
        Returns:
            Authentication result
            
        Raises:
            Exception: If authentication fails
        """
        try:
            # Exchange code for token
            token_data = await self.get_access_token(code, redirect_uri)
            access_token = token_data.get("access_token")
            
            if not access_token:
                raise Exception("No access token in response")
            
            # Get user info
            user_info = await self.get_user_info(access_token)
            
            return AuthResult(
                success=True,
                user_info=user_info,
                provider=self.name
            )
        except Exception as e:
            logger.error(f"Facebook authentication error: {str(e)}")
            return AuthResult(
                success=False,
                error=str(e),
                provider=self.name
            )
    
    async def create_or_update_user(self, db: Session, user_info: UserInfo) -> User:
        """
        Create or update a user based on Facebook authentication.
        
        Args:
            db: Database session
            user_info: User information from Facebook
            
        Returns:
            User object
            
        Raises:
            Exception: If user creation fails
        """
        try:
            # Try to find user by provider ID
            user = db.query(User).filter(
                User.provider == self.name,
                User.provider_user_id == user_info.provider_user_id
            ).first()
            
            if not user and user_info.email:
                # Try to find user by email
                user = db.query(User).filter(User.email == user_info.email).first()
            
            if user:
                # Update existing user
                user.last_login = datetime.utcnow()
                user.provider = self.name
                user.provider_user_id = user_info.provider_user_id
                
                # Only update these fields if they aren't already set
                if not user.first_name and user_info.first_name:
                    user.first_name = user_info.first_name
                if not user.last_name and user_info.last_name:
                    user.last_name = user_info.last_name
                if not user.image_url and user_info.picture:
                    user.image_url = user_info.picture
                
                db.commit()
                return user
            
            # Create new user
            new_user = User(
                id=uuid.uuid4(),
                email=user_info.email,
                username=user_info.username or user_info.email,
                is_active=True,
                provider=self.name,
                provider_user_id=user_info.provider_user_id,
                first_name=user_info.first_name,
                last_name=user_info.last_name,
                image_url=user_info.picture,
                last_login=datetime.utcnow(),
                is_verified=True  # We trust Facebook verified the email
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            return new_user
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating/updating user: {str(e)}")
            raise
