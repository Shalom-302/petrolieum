"""
Authentication service for the advanced authentication plugin.
"""
from typing import Dict, Any, Optional, List, Tuple, Union
import logging
from datetime import datetime, timedelta
import uuid
import jwt
import traceback
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.db import get_db
from .models import User, Role, Session as UserSession, MFAMethod, MFAMethodType, VerificationCode, Permission, Group
from .utils import (
    verify_password, get_password_hash, is_password_secure,
    create_access_token, create_refresh_token, ACCESS_TOKEN, REFRESH_TOKEN
)
from .providers import get_provider, list_providers
from .schemas import UserCreate, UserUpdate, PasswordUpdate, AuthResponse, Token, UserResponse

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service."""
    
    def __init__(self, db: Session):
        """
        Initialize the authentication service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def register_user(self, user_data: UserCreate) -> User:
        """
        Register a new user.
        
        Args:
            user_data: User registration data
            
        Returns:
            Created user
            
        Raises:
            HTTPException: If user already exists or other error
        """
        # Check if user already exists
        existing_user = self.db.query(User).filter(
            (User.email == user_data.email) | 
            (User.username == user_data.username)
        ).first()
        
        if existing_user:
            if existing_user.email == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # Get default role if not specified
        role_id = user_data.role_id
        if role_id is None:
            default_role = self.db.query(Role).filter(Role.name == "admin").first()
            if default_role:
                role_id = default_role.id
            else:
                # Create default role if it doesn't exist
                default_role = Role(name="User", description="Default user role")
                self.db.add(default_role)
                self.db.commit()
                self.db.refresh(default_role)
                role_id = default_role.id
        
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Create new user
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            is_active=True,
            is_verified=False,  # Require email verification
            role_id=role_id,
            primary_auth_provider="email"
        )
        
        try:
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            
            # Log successful registration
            logger.info(f"User registered: {new_user.email} (ID: {new_user.id})")
            
            return new_user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Registration error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during registration"
            )
    
    async def authenticate_user(self, email: str, password: str) -> User:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User's email
            password: User's password
            
        Returns:
            Authenticated user
            
        Raises:
            HTTPException: If authentication fails
        """
        logger.info(f"Authenticating user with email: {email}")
        
        # Find user by email
        user = self.db.query(User).filter(User.email == email).first()
        
        # Log user lookup result
        if user:
            logger.info(f"User found: {user.email} (ID: {user.id})")
        else:
            logger.warning(f"User not found with email: {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if user exists and password is correct
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Invalid password for user: {user.email}")
            # If user exists, increment failed login attempts
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            
            # Lock account after too many failed attempts
            if user.failed_login_attempts >= 5:  # Configurable threshold
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)  # Configurable lockout period
                logger.warning(f"Account locked for {email} after {user.failed_login_attempts} failed attempts")
            
            self.db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if user is locked out
        if user.locked_until and user.locked_until > datetime.utcnow():
            lock_time_remaining = (user.locked_until - datetime.utcnow()).total_seconds() // 60
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Account is locked due to too many failed login attempts. Try again in {int(lock_time_remaining)} minutes."
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive"
            )
        
        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"User authenticated: {user.email} (ID: {user.id})")
        
        return user
    
    async def create_tokens(self, user: User, remember_me: bool = False) -> Dict[str, str]:
        """
        Create authentication tokens for a user.
        
        Args:
            user: User to create tokens for
            remember_me: Whether to create long-lived tokens
            
        Returns:
            Dictionary with access_token and refresh_token
        """
        try:
            logger.info(f"Creating tokens for user: {user.email} (ID: {user.id})")
            
            # Create tokens
            access_token_expires = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES * (10 if remember_me else 1)
            )
            refresh_token_expires = timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS * (10 if remember_me else 1)
            )
            
            logger.info(f"Token expiration: access={access_token_expires}, refresh={refresh_token_expires}")
            
            access_token = create_access_token(
                user.id,
                expires_delta=access_token_expires,
                extra_data={
                    "username": user.username,
                    "email": user.email,
                    "role_id": str(user.role_id) if user.role_id else None
                }
            )
            
            refresh_token = create_refresh_token(
                user.id,
                expires_delta=refresh_token_expires
            )
            
            # Update user's refresh token
            user.refresh_token = refresh_token
            user.refresh_token_expires_at = datetime.utcnow() + refresh_token_expires
            user.last_login = datetime.utcnow()
            user.failed_login_attempts = 0  # Reset failed login attempts
            
            self.db.commit()
            
            logger.info(f"Tokens created successfully for user: {user.email}")
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": int(access_token_expires.total_seconds())
            }
        except Exception as e:
            logger.error(f"Error creating tokens for user {user.email}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating tokens: {str(e)}"
            )
    
    async def refresh_access_token(self, refresh_token: str) -> Tuple[User, Dict[str, Any]]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            Tuple of (User, new tokens dict)
            
        Raises:
            HTTPException: If refresh token is invalid or expired
        """
        try:
            logger.info(f"Refreshing access token, token length: {len(refresh_token)}")
            # Decode refresh token
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            user_id: str = payload.get("sub")
            token_type: str = payload.get("type")
            
            # Validate token type and user_id
            if user_id is None or token_type != "refresh":
                logger.error(f"Invalid refresh token: user_id={user_id}, token_type={token_type}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )
                
            # Get user from database
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User not found for refresh token: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                )
                
            # Check if user is active
            if not user.is_active:
                logger.error(f"Inactive user tried to refresh token: {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Inactive user",
                )
                
            # Create new tokens with the same remember_me setting
            remember_me = payload.get("remember_me", False)
            new_tokens = await self.create_tokens(user, remember_me)
            
            logger.info(f"Token refreshed for user: {user.email}")
            return user, new_tokens
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error refreshing token: {str(e)}",
            )
    
    async def logout(self, user: User, all_devices: bool = False) -> bool:
        """
        Log out a user by invalidating their tokens.
        
        Args:
            user: User to log out
            all_devices: Whether to log out from all devices
            
        Returns:
            True if successful
        """
        try:
            if all_devices:
                # Invalidate all sessions
                self.db.query(UserSession).filter(UserSession.user_id == user.id).update({
                    "is_active": False
                })
            
            # Clear refresh token
            user.refresh_token = None
            user.refresh_token_expires_at = None
            self.db.commit()
            
            logger.info(f"User logged out: {user.email} (ID: {user.id}), all_devices={all_devices}")
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Logout error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during logout"
            )
    
    async def update_user(self, user_id: uuid.UUID, user_data: UserUpdate) -> User:
        """
        Update a user.
        
        Args:
            user_id: ID of user to update
            user_data: User update data
            
        Returns:
            Updated user
            
        Raises:
            HTTPException: If user not found or other error
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if username or email is being changed and if they're already taken
        if user_data.username and user_data.username != user.username:
            existing_user = self.db.query(User).filter(User.username == user_data.username).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            user.username = user_data.username
        
        if user_data.email and user_data.email != user.email:
            existing_user = self.db.query(User).filter(User.email == user_data.email).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            user.email = user_data.email
            user.is_verified = False  # Require verification for new email
        
        # Update other fields
        if user_data.first_name is not None:
            user.first_name = user_data.first_name
        if user_data.last_name is not None:
            user.last_name = user_data.last_name
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
        if user_data.role_id is not None:
            user.role_id = user_data.role_id
        if user_data.is_verified is not None:
            user.is_verified = user_data.is_verified
        if user_data.is_superuser is not None:
            user.is_superuser = user_data.is_superuser
        if user_data.profile_picture is not None:
            user.profile_picture = user_data.profile_picture
        
        user.updated_at = datetime.utcnow()
        
        try:
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"User updated: {user.email} (ID: {user.id})")
            
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"User update error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating user"
            )
    
    async def change_password(self, user: User, current_password: str, new_password: str) -> bool:
        """
        Change a user's password.
        
        Args:
            user: User to change password for
            current_password: Current password
            new_password: New password
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If current password is incorrect or other error
        """
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )
        
        # Check if new password is secure
        if not is_password_secure(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password does not meet security requirements"
            )
        
        # Update password
        user.hashed_password = get_password_hash(new_password)
        user.password_changed_at = datetime.utcnow()
        
        try:
            self.db.commit()
            
            # Log password change but not the actual password
            logger.info(f"Password changed for user: {user.email} (ID: {user.id})")
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Password change error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while changing password"
            )
    
    async def get_available_providers(self) -> Dict[str, Dict[str, str]]:
        """
        Get all available authentication providers.
        
        Returns:
            Dictionary of provider information
        """
        return list_providers()
    
    async def init_oauth_flow(self, provider_name: str, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Initialize OAuth flow for a provider.
        
        Args:
            provider_name: Name of the provider
            redirect_uri: Redirect URI for OAuth callback
            state: Optional state to include in the request
            
        Returns:
            Authorization URL
            
        Raises:
            HTTPException: If provider is not supported or other error
        """
        try:
            # Get provider configuration from database or settings
            provider_config = {
                "client_id": settings.OAUTH_PROVIDERS.get(provider_name, {}).get("client_id"),
                "client_secret": settings.OAUTH_PROVIDERS.get(provider_name, {}).get("client_secret"),
            }
            
            if not provider_config["client_id"] or not provider_config["client_secret"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Provider {provider_name} is not configured"
                )
            
            # Initialize provider
            provider = get_provider(provider_name, provider_config)
            
            # Get authorization URL
            auth_url = await provider.get_authorization_url(redirect_uri, state)
            
            # Close provider client
            await provider.close()
            
            return auth_url
            
        except ValueError as e:
            logger.error(f"OAuth initialization error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"OAuth initialization error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred during OAuth initialization: {str(e)}"
            )
    
    async def handle_oauth_callback(
        self, provider_name: str, code: str, redirect_uri: str, state: Optional[str] = None
    ) -> Tuple[User, Dict[str, str]]:
        """
        Handle OAuth callback.
        
        Args:
            provider_name: Name of the provider
            code: Authorization code
            redirect_uri: Redirect URI
            state: Optional state from the request
            
        Returns:
            Tuple of (user, tokens)
            
        Raises:
            HTTPException: If callback fails
        """
        try:
            # Get provider configuration from database or settings
            provider_config = {
                "client_id": settings.OAUTH_PROVIDERS.get(provider_name, {}).get("client_id"),
                "client_secret": settings.OAUTH_PROVIDERS.get(provider_name, {}).get("client_secret"),
            }
            
            if not provider_config["client_id"] or not provider_config["client_secret"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Provider {provider_name} is not configured"
                )
            
            # Initialize provider
            provider = get_provider(provider_name, provider_config)
            
            # Exchange code for token
            token_data = await provider.exchange_code_for_token(code, redirect_uri)
            
            if not token_data.get("access_token"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to obtain access token"
                )
            
            # Get user info from provider
            user_info = await provider.get_user_info(token_data["access_token"])
            
            # Check if user exists using email only (évite l'erreur avec l'opérateur JSON)
            user = self.db.query(User).filter(User.email == user_info.email).first()
            
            # Si l'utilisateur n'est pas trouvé par email, essayons de chercher par provider_id
            # en utilisant des requêtes JSON spécifiques à PostgreSQL
            if not user and user_info.id:
                # Créer un chemin JSON pour vérifier si le provider_id existe pour ce provider
                json_path = f"$.{provider_name}.id"
                try:
                    # Utiliser une requête SQL brute pour éviter les problèmes d'opérateurs
                    # Remarque : ceci est spécifique à PostgreSQL
                    from sqlalchemy import text
                    query = text(f"""
                        SELECT * FROM "user" 
                        WHERE auth_provider_data->'{provider_name}'->>'id' = :provider_id
                    """)
                    result = self.db.execute(query, {"provider_id": user_info.id})
                    user_record = result.fetchone()
                    if user_record:
                        user = self.db.query(User).filter(User.id == user_record[0]).first()
                except Exception as e:
                    logger.error(f"Error querying by provider ID: {str(e)}")
            
            if user:
                # Update user data
                user.auth_provider_data = {
                    **(user.auth_provider_data or {}),
                    provider_name: {
                        "id": user_info.id,
                        "updated_at": datetime.utcnow().isoformat()
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
                    user.primary_auth_provider = provider_name
                
                self.db.commit()
                self.db.refresh(user)
            else:
                # Create new user
                # Generate a username
                username = f"{provider_name}_{user_info.id}"
                if user_info.username:
                    username = user_info.username
                elif user_info.email:
                    username = user_info.email.split('@')[0]
                
                # Ensure username is unique
                existing_username = self.db.query(User).filter(User.username == username).first()
                if existing_username:
                    username = f"{username}_{uuid.uuid4().hex[:6]}"
                
                # Get default role
                default_role = self.db.query(Role).filter(Role.name == "User").first()
                if not default_role:
                    # Create default role if it doesn't exist
                    default_role = Role(name="User", description="Default user role")
                    self.db.add(default_role)
                    self.db.commit()
                    self.db.refresh(default_role)
                
                # Create new user
                try:
                    new_user = User(
                        email=user_info.email,
                        username=username,
                        first_name=user_info.first_name or "",
                        last_name=user_info.last_name or "",
                        is_active=True,
                        is_verified=user_info.email_verified if hasattr(user_info, 'email_verified') else True,
                        role_id=default_role.id,
                        primary_auth_provider=provider_name,
                        auth_provider_data={
                            provider_name: {
                                "id": user_info.id,
                                "updated_at": datetime.utcnow().isoformat()
                            }
                        },
                        profile_picture=user_info.picture if hasattr(user_info, 'picture') else None
                    )
                    
                    self.db.add(new_user)
                    self.db.commit()
                    self.db.refresh(new_user)
                    
                    user = new_user
                    logger.info(f"Created new user via OAuth: {user.email} using {provider_name}")
                except Exception as e:
                    logger.error(f"Error creating user: {str(e)}")
                    self.db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create user account: {str(e)}"
                    )
            
            # Generate tokens
            tokens = await self.create_tokens(user)
            
            # Close provider client
            await provider.close()
            
            logger.info(f"OAuth login successful for {user.email} using {provider_name}")
            
            return user, tokens
            
        except Exception as e:
            logger.error(f"OAuth callback error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred during OAuth callback: {str(e)}"
            )
