"""
Security utilities for the advanced authentication plugin.
"""
import os
import hmac
import hashlib
import base64
from typing import Any, Union, Optional, Dict
from datetime import datetime, timedelta
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings
from app.core.db import get_db
from ..models.user import User

# Configure password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configure OAuth2 password bearer for token auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/auth/login")

logger = logging.getLogger(__name__)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
    
    Returns:
        True if password matches hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def is_password_secure(password: str) -> bool:
    """
    Check if a password meets security requirements.
    
    Args:
        password: Password to check
    
    Returns:
        True if password meets security requirements
    """
    # At least 8 characters
    if len(password) < 8:
        return False
    
    # At least one uppercase letter
    if not any(c.isupper() for c in password):
        return False
    
    # At least one lowercase letter
    if not any(c.islower() for c in password):
        return False
    
    # At least one digit
    if not any(c.isdigit() for c in password):
        return False
    
    # At least one special character
    special_chars = "!@#$%^&*()-_=+[]{}|;:,.<>/?"
    if not any(c in special_chars for c in password):
        return False
    
    return True


def create_encryption_key(password: str, salt: Optional[bytes] = None) -> bytes:
    """
    Create an encryption key from a password using PBKDF2.
    
    Args:
        password: Password to derive key from
        salt: Optional salt (if not provided, a new one will be generated)
    
    Returns:
        (key, salt) tuple
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


class DataEncryptor:
    """Utility for encrypting and decrypting sensitive data."""
    
    def __init__(self, key: Optional[str] = None):
        """
        Initialize encryptor with key.
        
        Args:
            key: Encryption key (uses settings.SECRET_KEY if not provided)
        """
        if key is None:
            key = settings.SECRET_KEY
        
        # Ensure key is valid for Fernet (32 bytes, URL-safe base64 encoded)
        derived_key, _ = create_encryption_key(key)
        self.fernet = Fernet(derived_key)
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt
        
        Returns:
            Encrypted data as base64 string
        """
        if not data:
            return data
        
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Encrypted data (base64 string)
        
        Returns:
            Decrypted data
        """
        if not encrypted_data:
            return encrypted_data
        
        return self.fernet.decrypt(encrypted_data.encode()).decode()


def create_hmac_signature(data: str, secret: str) -> str:
    """
    Create an HMAC signature for data.
    
    Args:
        data: Data to sign
        secret: Secret key
    
    Returns:
        Signature as hex string
    """
    key = secret.encode()
    message = data.encode()
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return signature


def verify_hmac_signature(data: str, signature: str, secret: str) -> bool:
    """
    Verify an HMAC signature.
    
    Args:
        data: Original data
        signature: Signature to verify
        secret: Secret key
    
    Returns:
        True if signature is valid
    """
    expected_signature = create_hmac_signature(data, secret)
    return hmac.compare_digest(signature, expected_signature)


async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get the current user from a JWT token.
    
    Args:
        db: Database session
        token: JWT token
    
    Returns:
        Current user
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    from .token import decode_token
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token_data = decode_token(token)
        user_id = token_data.get("sub")
        
        if not user_id:
            raise credentials_exception
        
        # Check token type
        if token_data.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Must use access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
    except Exception:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the current user is active.
    
    Args:
        current_user: Current user
    
    Returns:
        Current user if active
    
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    return current_user


def require_role(*allowed_roles: str):
    """
    Dependency for requiring specific roles.
    
    Args:
        *allowed_roles: Roles to allow
    
    Returns:
        Dependency function
    """
    async def check_role(current_user: User = Depends(get_current_active_user)):
        if not current_user.role or current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have required role. Must be one of: {', '.join(allowed_roles)}",
            )
        
        return current_user
    
    return check_role


def require_superuser(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency for requiring superuser status.
    
    Args:
        current_user: Current user
    
    Returns:
        Current user if superuser
    
    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    
    return current_user


def throttle_attempts(key: str, max_attempts: int, window_seconds: int, db: Session) -> None:
    """
    Throttle attempts to prevent brute force.
    
    Args:
        key: Key to throttle on (e.g. "login:{ip}")
        max_attempts: Maximum number of attempts
        window_seconds: Time window in seconds
        db: Database session
    
    Raises:
        HTTPException: If too many attempts
    """
    # This would be implemented with Redis for production
    # For now, we'll stub it
    pass
