"""
GitHub OAuth authentication provider.
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


class GitHubAuthProvider(AuthProvider):
    """GitHub OAuth authentication provider."""
    
    name = "github"
    friendly_name = "GitHub"
    icon = "github"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize GitHub authentication provider.
        
        Args:
            config: Provider configuration including client_id and client_secret
        """
        super().__init__(config)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("GitHub provider requires client_id and client_secret")
        
        self.auth_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.api_base_url = "https://api.github.com"
    
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Get the GitHub authorization URL.
        
        Args:
            redirect_uri: The URI to redirect to after authorization
            state: Optional state to include in the request
            
        Returns:
            GitHub authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:email",  # Minimum required scope
        }
        
        if state:
            params["state"] = state
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        return auth_url
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange an authorization code for a GitHub access token.
        
        Args:
            code: The authorization code from GitHub
            redirect_uri: The redirect URI used in the authorization request
            
        Returns:
            Token information
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri
        }
        
        headers = {
            "Accept": "application/json"
        }
        
        response = await self._make_request(
            "POST", 
            self.token_url,
            data=data,
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"GitHub token exchange failed: {response.status_code} {response.text}")
            raise Exception(f"GitHub token exchange failed: {response.status_code}")
        
        token_data = response.json()
        return token_data
    
    async def get_user_info(self, access_token: str) -> UserInfo:
        """
        Get GitHub user information.
        
        Args:
            access_token: GitHub access token
            
        Returns:
            Standardized user information
        """
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Get user profile
        profile_response = await self._make_request(
            "GET",
            f"{self.api_base_url}/user",
            headers=headers
        )
        
        if profile_response.status_code != 200:
            logger.error(f"GitHub user profile request failed: {profile_response.status_code} {profile_response.text}")
            raise Exception(f"GitHub user profile request failed: {profile_response.status_code}")
        
        profile_data = profile_response.json()
        
        # Get user emails if not present in profile
        email = profile_data.get("email")
        email_verified = True if email else False
        
        if not email:
            emails_response = await self._make_request(
                "GET",
                f"{self.api_base_url}/user/emails",
                headers=headers
            )
            
            if emails_response.status_code == 200:
                emails_data = emails_response.json()
                
                # Find primary email
                primary_email = next(
                    (e for e in emails_data if e.get("primary") and e.get("verified")),
                    None
                )
                
                if primary_email:
                    email = primary_email.get("email")
                    email_verified = primary_email.get("verified", False)
                elif emails_data:
                    # Use first verified email if no primary
                    verified_email = next(
                        (e for e in emails_data if e.get("verified")),
                        None
                    )
                    
                    if verified_email:
                        email = verified_email.get("email")
                        email_verified = True
                    else:
                        # Use first email as fallback
                        email = emails_data[0].get("email")
                        email_verified = emails_data[0].get("verified", False)
        
        # Parse name into first and last name
        name = profile_data.get("name", "")
        name_parts = name.split() if name else []
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
        # Create standardized user info
        user_info = UserInfo(
            id=str(profile_data.get("id")),
            email=email,
            email_verified=email_verified,
            name=name,
            first_name=first_name,
            last_name=last_name,
            username=profile_data.get("login"),
            picture=profile_data.get("avatar_url"),
            raw_data=profile_data
        )
        
        return user_info
    
    async def authenticate_or_create_user(self, access_token: str, db: Session) -> AuthResult:
        """
        Authenticate with GitHub and create a user if needed.
        
        Args:
            access_token: GitHub access token
            db: Database session
            
        Returns:
            Authentication result
        """
        try:
            # Get user info from GitHub
            user_info = await self.get_user_info(access_token)
            
            if not user_info.email:
                logger.error(f"GitHub authentication failed: No email found for user {user_info.id}")
                return AuthResult(
                    success=False,
                    error="email_required",
                    error_description="No email address found in your GitHub account"
                )
            
            # Check if user exists
            user = db.query(User).filter(
                (User.email == user_info.email) | 
                (User.auth_provider_data.contains({"github": {"id": user_info.id}}))
            ).first()
            
            if user:
                # Update user data if needed
                user.auth_provider_data = {
                    **(user.auth_provider_data or {}),
                    "github": {
                        "id": user_info.id,
                        "username": user_info.username,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
                
                # Update profile if empty
                if not user.first_name and user_info.first_name:
                    user.first_name = user_info.first_name
                if not user.last_name and user_info.last_name:
                    user.last_name = user_info.last_name
                
                # Update login information
                user.last_login = datetime.utcnow()
                
                # Set primary auth provider if not set
                if not user.primary_auth_provider:
                    user.primary_auth_provider = "github"
                
                db.commit()
                db.refresh(user)
            else:
                # Create new user
                new_user = User(
                    email=user_info.email,
                    username=user_info.username or f"github_{user_info.id}",
                    first_name=user_info.first_name,
                    last_name=user_info.last_name,
                    is_active=True,
                    is_verified=user_info.email_verified,
                    role_id=None,  # Will need to be assigned
                    primary_auth_provider="github",
                    auth_provider_data={
                        "github": {
                            "id": user_info.id,
                            "username": user_info.username,
                            "updated_at": datetime.utcnow().isoformat()
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
            
            logger.info(f"GitHub authentication successful for {user.email}")
            
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
            logger.error(f"GitHub authentication error: {str(e)}")
            return AuthResult(
                success=False,
                error="server_error",
                error_description=f"An error occurred during GitHub authentication: {str(e)}"
            )
