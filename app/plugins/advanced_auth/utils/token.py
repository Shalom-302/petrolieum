"""
Token utilities for the advanced authentication plugin.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
import uuid
import logging
from jose import jwt, JWTError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Token type constants
ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"
EMAIL_VERIFICATION_TOKEN = "email_verification"
PASSWORD_RESET_TOKEN = "password_reset"


def create_token(
    subject: Union[str, uuid.UUID],
    token_type: str,
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a JWT token.
    
    Args:
        subject: Subject of the token (user ID)
        token_type: Type of token (access, refresh, etc.)
        expires_delta: Token expiration
        extra_data: Additional data to include in the token
    
    Returns:
        JWT token
    """
    if expires_delta is None:
        if token_type == ACCESS_TOKEN:
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        elif token_type == REFRESH_TOKEN:
            expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        elif token_type == EMAIL_VERIFICATION_TOKEN:
            expires_delta = timedelta(hours=24)
        elif token_type == PASSWORD_RESET_TOKEN:
            expires_delta = timedelta(hours=1)
        else:
            expires_delta = timedelta(minutes=15)
    
    expire = datetime.utcnow() + expires_delta
    
    to_encode = {
        "exp": expire,
        "iat": datetime.utcnow(),
        "sub": str(subject),
        "type": token_type
    }
    
    if extra_data:
        to_encode.update(extra_data)
    
    # Add JWT ID to prevent replay attacks
    to_encode["jti"] = str(uuid.uuid4())
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_access_token(
    subject: Union[str, uuid.UUID],
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create an access token.
    
    Args:
        subject: Subject of the token (user ID)
        expires_delta: Token expiration
        extra_data: Additional data to include in the token
    
    Returns:
        JWT token
    """
    return create_token(subject, ACCESS_TOKEN, expires_delta, extra_data)


def create_refresh_token(
    subject: Union[str, uuid.UUID],
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a refresh token.
    
    Args:
        subject: Subject of the token (user ID)
        expires_delta: Token expiration
        extra_data: Additional data to include in the token
    
    Returns:
        JWT token
    """
    return create_token(subject, REFRESH_TOKEN, expires_delta, extra_data)


def create_email_verification_token(
    subject: Union[str, uuid.UUID],
    email: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create an email verification token.
    
    Args:
        subject: Subject of the token (user ID)
        email: Email to verify
        expires_delta: Token expiration
    
    Returns:
        JWT token
    """
    return create_token(
        subject,
        EMAIL_VERIFICATION_TOKEN,
        expires_delta,
        {"email": email}
    )


def create_password_reset_token(
    subject: Union[str, uuid.UUID],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a password reset token.
    
    Args:
        subject: Subject of the token (user ID)
        expires_delta: Token expiration
    
    Returns:
        JWT token
    """
    return create_token(subject, PASSWORD_RESET_TOKEN, expires_delta)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode a JWT token.
    
    Args:
        token: JWT token
    
    Returns:
        Token payload
    
    Raises:
        JWTError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        return payload
    except JWTError as e:
        logger.error(f"Token decode error: {str(e)}")
        raise


def validate_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate a JWT token.
    
    Args:
        token: JWT token
        expected_type: Expected token type
    
    Returns:
        Token payload if valid
    
    Raises:
        JWTError: If token is invalid
    """
    payload = decode_token(token)
    
    # Check token type if specified
    if expected_type and payload.get("type") != expected_type:
        raise JWTError(f"Invalid token type. Expected {expected_type}, got {payload.get('type')}")
    
    # Check expiration
    if "exp" in payload:
        expiration = datetime.fromtimestamp(payload["exp"])
        if datetime.utcnow() >= expiration:
            raise JWTError("Token has expired")
    
    return payload
