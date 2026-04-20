"""
Email/password authentication provider.
"""
from typing import Dict, Any, Optional, Union
import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..models.user import User
from ..utils.security import verify_password, get_password_hash
from ..utils.token import create_access_token, create_refresh_token
from .base import AuthProvider, AuthResult, UserInfo

logger = logging.getLogger(__name__)


class EmailAuthProvider(AuthProvider):
    """Provider for email/password authentication."""
    
    name = "email"
    friendly_name = "Email & Password"
    icon = "email"
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the email authentication provider."""
        super().__init__(config or {})
    
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """Not applicable for email authentication."""
        raise NotImplementedError("Email provider does not support authorization URLs")
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Not applicable for email authentication."""
        raise NotImplementedError("Email provider does not support code exchange")
    
    async def get_user_info(self, access_token: str) -> UserInfo:
        """Not applicable for email authentication."""
        raise NotImplementedError("Email provider does not support user info retrieval")
    
    async def authenticate(self, email: str, password: str, db: Session) -> AuthResult:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User's email
            password: User's password
            db: Database session
            
        Returns:
            Authentication result
        """
        # Log authentication attempt
        logger.info(f"Authentication attempt for email: {email}")
        
        try:
            # Find user by email
            user = db.query(User).filter(User.email == email).first()
            
            # User not found
            if not user:
                logger.warning(f"Authentication failed: User not found for email {email}")
                return AuthResult(
                    success=False,
                    error="invalid_credentials",
                    error_description="Invalid email or password"
                )
            
            # Check if user is locked out due to too many failed attempts
            if user.locked_until and user.locked_until > datetime.utcnow():
                logger.warning(f"Authentication failed: Account locked for {email}")
                return AuthResult(
                    success=False,
                    error="account_locked",
                    error_description="Account is temporarily locked due to too many failed login attempts"
                )
            
            # Verify password
            if not verify_password(password, user.hashed_password):
                # Increment failed login attempts
                user.failed_login_attempts += 1
                
                # Lock account after too many failed attempts
                if user.failed_login_attempts >= 5:  # Configurable threshold
                    from datetime import timedelta
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)  # Configurable lockout period
                    logger.warning(f"Account locked for {email} after {user.failed_login_attempts} failed attempts")
                
                db.commit()
                
                logger.warning(f"Authentication failed: Invalid password for {email}")
                return AuthResult(
                    success=False,
                    error="invalid_credentials",
                    error_description="Invalid email or password"
                )
            
            # Check if user is active
            if not user.is_active:
                logger.warning(f"Authentication failed: Inactive account for {email}")
                return AuthResult(
                    success=False,
                    error="inactive_account",
                    error_description="Account is inactive"
                )
            
            # Authentication successful
            # Reset failed login attempts
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()
            
            # Generate tokens
            access_token = create_access_token(user.id)
            refresh_token = create_refresh_token(user.id)
            
            # Update user's refresh token
            user.refresh_token = refresh_token
            db.commit()
            
            logger.info(f"Authentication successful for {email}")
            
            # Return authentication result
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
                    "is_superuser": user.is_superuser
                }
            )
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return AuthResult(
                success=False,
                error="server_error",
                error_description="An unexpected error occurred"
            )
    
    async def register(self, user_data: Dict[str, Any], db: Session) -> AuthResult:
        """
        Register a new user with email and password.
        
        Args:
            user_data: User registration data including email, password, etc.
            db: Database session
            
        Returns:
            Registration result
        """
        logger.info(f"Registration attempt for email: {user_data.get('email')}")
        
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(
                (User.email == user_data.get('email')) | 
                (User.username == user_data.get('username'))
            ).first()
            
            if existing_user:
                if existing_user.email == user_data.get('email'):
                    logger.warning(f"Registration failed: Email already exists {user_data.get('email')}")
                    return AuthResult(
                        success=False,
                        error="email_exists",
                        error_description="Email already exists"
                    )
                else:
                    logger.warning(f"Registration failed: Username already exists {user_data.get('username')}")
                    return AuthResult(
                        success=False,
                        error="username_exists",
                        error_description="Username already exists"
                    )
            
            # Hash password
            hashed_password = get_password_hash(user_data.get('password'))
            
            # Create user
            new_user = User(
                email=user_data.get('email'),
                username=user_data.get('username'),
                hashed_password=hashed_password,
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                is_active=True,
                is_verified=False,  # Require email verification
                role_id=user_data.get('role_id'),  # Default role
                primary_auth_provider="email"
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            logger.info(f"Registration successful for {user_data.get('email')}")
            
            # Generate tokens
            access_token = create_access_token(new_user.id)
            refresh_token = create_refresh_token(new_user.id)
            
            # Update user's refresh token
            new_user.refresh_token = refresh_token
            db.commit()
            
            # Return registration result
            return AuthResult(
                success=True,
                user_id=str(new_user.id),
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=3600,  # 1 hour
                user_data={
                    "id": str(new_user.id),
                    "email": new_user.email,
                    "username": new_user.username,
                    "first_name": new_user.first_name,
                    "last_name": new_user.last_name,
                    "is_verified": new_user.is_verified
                }
            )
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return AuthResult(
                success=False,
                error="server_error",
                error_description="An unexpected error occurred during registration"
            )
