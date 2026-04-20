from datetime import datetime, timedelta
from typing import Any, Union, Optional, Protocol
import hmac
import hashlib
import base64
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.plugins.advanced_auth.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/auth/login")


# Schéma OAuth2 qui ne lève pas d'exception si aucun token n'est fourni
class OAuth2PasswordBearerOptional(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        try:
            return await super().__call__(request)
        except HTTPException:
            return None


oauth2_scheme_optional = OAuth2PasswordBearerOptional(tokenUrl=f"/auth/login")


class EncryptionHandler(Protocol):
    """Protocol defining the interface for encryption handlers."""
    
    def encrypt(self, data: str) -> str:
        """Encrypt data."""
        pass
        
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        pass


def create_encryption_handler(secret_key: Optional[str] = None) -> EncryptionHandler:
    """
    Create an encryption handler for sensitive data with an optional custom secret key.
    
    Args:
        secret_key: Optional custom secret key for encryption. If not provided,
                   the application's default secret key will be used.
    
    Returns:
        An encryption handler object with encrypt/decrypt methods.
    """
    class DefaultEncryptionHandler:
        def __init__(self, secret_key: str):
            self.secret_key = secret_key or settings.SECRET_KEY
            self.algorithm = 'AES-256-CBC'  # Example algorithm
            
        def encrypt(self, data: str) -> str:
            """Encrypt sensitive data using the secret key."""
            if not data:
                return data
            # Simple encryption for demonstration 
            # In production, use a proper encryption library
            signature = create_hmac_signature(data, self.secret_key)
            return f"{base64.b64encode(data.encode()).decode()}:{signature}"
            
        def decrypt(self, encrypted_data: str) -> str:
            """Decrypt data that was encrypted with this handler."""
            if not encrypted_data or ":" not in encrypted_data:
                return encrypted_data
                
            data_b64, signature = encrypted_data.split(":", 1)
            data = base64.b64decode(data_b64.encode()).decode()
            
            # Verify signature
            if not verify_hmac_signature(data, signature, self.secret_key):
                raise ValueError("Signature verification failed")
                
            return data
    
    return DefaultEncryptionHandler(secret_key)


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_default_encryption() -> EncryptionHandler:
    """
    Create a default encryption handler for sensitive data.
    
    This function returns a callable that can be used to encrypt and decrypt 
    sensitive data throughout the application. The encryption is based on
    the application's SECRET_KEY setting.
    
    Returns:
        An encryption handler object with encrypt/decrypt methods.
    """
    return create_encryption_handler(settings.SECRET_KEY)

async def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Direct database query to get user by ID
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    return user

def get_current_user_optional(
    db: Session = Depends(get_db), token: Optional[str] = Depends(oauth2_scheme_optional)
) -> Optional[User]:
    """
    Similar to get_current_user but returns None instead of raising an exception
    if authentication fails. This is useful for endpoints that can work with or
    without authentication.
    
    Args:
        db: Database session
        token: JWT token from Authorization header (optional)
        
    Returns:
        User object if authenticated, None otherwise
    """
    if token is None:
        return None
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_active_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="The user doesn't have enough privileges"
        )
    return current_user

def require_role(*allowed_roles: str):
    """
    Use as a dependency to ensure the current user has one of the allowed roles.
    e.g. @router.get("/admin-only", dependencies=[Depends(require_role("Admin"))])
    """
    def wrapper(current_user: User = Depends(get_current_user)):
        if current_user.role.name not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden: insufficient role")
        return current_user
    return wrapper

def verify_admin_token(user_id: str) -> bool:
    """
    Verifies if the user ID belongs to an administrator.
    
    Args:
        user_id: The ID of the user to check
        
    Returns:
        bool: True if user is an admin, raises HTTPException otherwise
        
    Raises:
        HTTPException: If the user is not an admin
    """
    # Use the database session to query the user
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        if not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="The user doesn't have enough privileges"
            )
            
        return True
    finally:
        db.close()
        
def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Extract the user ID from a JWT token without querying the database.
    
    Args:
        token: JWT token
        
    Returns:
        str: User ID from the token
        
    Raises:
        HTTPException: If the token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception

def create_hmac_signature(data: str, secret: str) -> str:
    """
    Create an HMAC signature for data integrity verification.
    
    Args:
        data: Data to sign
        secret: Secret key for signing
        
    Returns:
        Base64-encoded signature
    """
    signature = hmac.new(
        key=secret.encode(),
        msg=data.encode(),
        digestmod=hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(signature).decode()

def verify_hmac_signature(data: str, signature: str, secret: str) -> bool:
    """
    Verify an HMAC signature to ensure data integrity.
    
    Args:
        data: Original data that was signed
        signature: Signature to verify
        secret: Secret key used for signing
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        expected_signature = create_hmac_signature(data, secret)
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False