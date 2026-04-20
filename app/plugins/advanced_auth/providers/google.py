"""
Google OAuth authentication provider.
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


class GoogleAuthProvider(AuthProvider):
    """Google OAuth authentication provider."""
    
    name = "google"
    friendly_name = "Google"
    icon = "google"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Google authentication provider.
        
        Args:
            config: Provider configuration including client_id and client_secret
        """
        super().__init__(config)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Google provider requires client_id and client_secret")
        
        self.auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Get the Google authorization URL.
        
        Args:
            redirect_uri: The URI to redirect to after authorization
            state: Optional state to include in the request
            
        Returns:
            Google authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",  # For refresh token
            "prompt": "consent",  # Force consent screen
        }
        
        if state:
            params["state"] = state
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        return auth_url
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange an authorization code for a Google access token.
        
        Args:
            code: The authorization code from Google
            redirect_uri: The redirect URI used in the authorization request
            
        Returns:
            Token information
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        response = await self._make_request(
            "POST", 
            self.token_url,
            data=data
        )
        
        if response.status_code != 200:
            logger.error(f"Google token exchange failed: {response.status_code} {response.text}")
            raise Exception(f"Google token exchange failed: {response.status_code}")
        
        token_data = response.json()
        return token_data
    
    async def get_user_info(self, access_token: str) -> UserInfo:
        """
        Get Google user information.
        
        Args:
            access_token: Google access token
            
        Returns:
            Standardized user information
        """
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        response = await self._make_request(
            "GET",
            self.userinfo_url,
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"Google user info request failed: {response.status_code} {response.text}")
            raise Exception(f"Google user info request failed: {response.status_code}")
        
        user_data = response.json()
        
        # Create standardized user info
        user_info = UserInfo(
            id=user_data.get("sub"),
            email=user_data.get("email"),
            email_verified=user_data.get("email_verified", False),
            name=user_data.get("name"),
            first_name=user_data.get("given_name"),
            last_name=user_data.get("family_name"),
            picture=user_data.get("picture"),
            locale=user_data.get("locale"),
            raw_data=user_data
        )
        
        return user_info
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh a Google access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New token data
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        response = await self._make_request(
            "POST",
            self.token_url,
            data=data
        )
        
        if response.status_code != 200:
            logger.error(f"Google token refresh failed: {response.status_code} {response.text}")
            raise Exception(f"Google token refresh failed: {response.status_code}")
        
        return response.json()
    
    async def authenticate_or_create_user(self, access_token: str, refresh_token: Optional[str], db: Session) -> AuthResult:
        """
        Authenticate with Google and create a user if needed.
        
        Args:
            access_token: Google access token
            refresh_token: Google refresh token (optional)
            db: Database session
            
        Returns:
            Authentication result
        """
        try:
            # Get user info from Google
            user_info = await self.get_user_info(access_token)
            
            if not user_info.email:
                logger.error(f"Google authentication failed: No email found for user {user_info.id}")
                return AuthResult(
                    success=False,
                    error="email_required",
                    error_description="No email address found in your Google account"
                )
            
            # Check if user exists
            user = db.query(User).filter(
                (User.email == user_info.email) | 
                (User.auth_provider_data.contains({"google": {"id": user_info.id}}))
            ).first()
            
            if user:
                # Update user data if needed
                user.auth_provider_data = {
                    **(user.auth_provider_data or {}),
                    "google": {
                        "id": user_info.id,
                        "updated_at": datetime.utcnow().isoformat(),
                        "refresh_token": refresh_token
                    }
                }
                
                # Update profile if empty
                if not user.first_name and user_info.first_name:
                    user.first_name = user_info.first_name
                if not user.last_name and user_info.last_name:
                    user.last_name = user_info.last_name
                if not user.profile_picture and user_info.picture:
                    user.profile_picture = user_info.picture
                
                # Update login information
                user.last_login = datetime.utcnow()
                
                # Set primary auth provider if not set
                if not user.primary_auth_provider:
                    user.primary_auth_provider = "google"
                
                db.commit()
                db.refresh(user)
            else:
                # Generate a username
                username = f"google_{user_info.id}"
                if user_info.email:
                    username = user_info.email.split('@')[0]
                
                # Ensure username is unique
                existing_username = db.query(User).filter(User.username == username).first()
                if existing_username:
                    username = f"{username}_{uuid.uuid4().hex[:6]}"
                
                # Create new user
                new_user = User(
                    email=user_info.email,
                    username=username,
                    first_name=user_info.first_name,
                    last_name=user_info.last_name,
                    is_active=True,
                    is_verified=user_info.email_verified,
                    role_id=None,  # Will need to be assigned
                    primary_auth_provider="google",
                    auth_provider_data={
                        "google": {
                            "id": user_info.id,
                            "updated_at": datetime.utcnow().isoformat(),
                            "refresh_token": refresh_token
                        }
                    },
                    profile_picture=user_info.picture
                )
                
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                
                user = new_user
            
            # Generate tokens
            access_token = create_access_token(user.id)
            refresh_token = create_refresh_token(user.id)
            
            # Update user's refresh token
            user.refresh_token = refresh_token
            db.commit()
            
            logger.info(f"Google authentication successful for {user.email}")
            
            # Return success result
            return AuthResult(
                success=True,
                user_id=str(user.id),
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=3600,  # 1 hour
                user_data={
                    "id": str(user.id),
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_verified": user.is_verified,
                    "is_superuser": user.is_superuser,
                    "picture": user.profile_picture
                }
            )
            
        except Exception as e:
            logger.error(f"Google authentication error: {str(e)}")
            return AuthResult(
                success=False,
                error="server_error",
                error_description=f"An error occurred during Google authentication: {str(e)}"
            )
