"""
API Key model for the API Gateway plugin.

Provides the database structure and utilities for creating, storing, and
verifying API keys with robust security mechanisms.
"""

import logging
import secrets
import hashlib
import uuid
from typing import List, Optional, Dict, Any, Tuple, Set
from datetime import datetime, timedelta

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field, validator

from app.core.db import Base
from app.core.security import get_password_hash

# Setup logging
logger = logging.getLogger(__name__)

class ApiKeyDB(Base):
    """API key database model."""
    
    __tablename__ = "api_gateway_keys"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    prefix = Column(String(8), unique=True, index=True, nullable=False)
    hashed_key = Column(String(255), nullable=False)
    
    owner_id = Column(String(36), nullable=False, index=True)
    owner_type = Column(String(50), nullable=False, default="user")
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    rate_limit_per_minute = Column(Integer, nullable=True)
    rate_limit_per_hour = Column(Integer, nullable=True)
    rate_limit_per_day = Column(Integer, nullable=True)
    
    allowed_ips = Column(JSON, nullable=True)
    allowed_origins = Column(JSON, nullable=True)
    
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, nullable=False, default=0)
    
    # Relationships
    permissions = relationship("ApiPermissionDB", back_populates="api_key", cascade="all, delete-orphan")
    audit_logs = relationship("ApiAuditLogDB", back_populates="api_key", cascade="all, delete-orphan")
    rate_limits = relationship("RateLimitDB", back_populates="api_key", cascade="all, delete-orphan")
    
    @classmethod
    def create_key(
        cls,
        name: str,
        owner_id: str,
        owner_type: str = "user",
        expires_days: int = 365,
        rate_limit_per_minute: Optional[int] = None,
        rate_limit_per_hour: Optional[int] = None,
        rate_limit_per_day: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None
    ) -> Tuple["ApiKeyDB", str]:
        """
        Create a new API key.
        
        Args:
            name: Name/description of the API key
            owner_id: ID of the owner
            owner_type: Type of owner (user, service, etc.)
            expires_days: Days until expiration (0 for no expiration)
            rate_limit_per_minute: Requests per minute limit
            rate_limit_per_hour: Requests per hour limit
            rate_limit_per_day: Requests per day limit
            allowed_ips: List of allowed IP addresses
            allowed_origins: List of allowed origins
            
        Returns:
            Tuple of (ApiKeyDB, plain_text_key)
        """
        # Generate a unique ID
        api_key_id = str(uuid.uuid4())
        
        # Generate a secure random key
        plain_key = secrets.token_urlsafe(32)
        
        # Get the prefix and hash for storage
        prefix = plain_key[:8]
        hashed_key = hashlib.sha256(plain_key.encode()).hexdigest()
        
        # Calculate expiration date
        expires_at = None
        if expires_days > 0:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        # Create the API key record
        api_key = cls(
            id=api_key_id,
            name=name,
            prefix=prefix,
            hashed_key=hashed_key,
            owner_id=owner_id,
            owner_type=owner_type,
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_hour=rate_limit_per_hour,
            rate_limit_per_day=rate_limit_per_day,
            allowed_ips=allowed_ips,
            allowed_origins=allowed_origins,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        # Log key creation (without exposing the key)
        logger.info(f"Created API key '{name}' for {owner_type} {owner_id} with prefix {prefix}")
        
        return api_key, plain_key
    
    @staticmethod
    def get_prefix_and_hash(key: str) -> Tuple[str, str]:
        """
        Extract the prefix and compute the hash from a plain text key.
        
        Args:
            key: Plain text API key
            
        Returns:
            Tuple of (prefix, hashed_key)
        """
        prefix = key[:8]
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        return prefix, hashed_key
    
    def verify_key(self, key: str) -> bool:
        """
        Verify if a plain text key matches this API key.
        
        Args:
            key: Plain text API key to verify
            
        Returns:
            True if the key is valid
        """
        if len(key) < 8 or key[:8] != self.prefix:
            return False
        
        _, hashed_key = self.get_prefix_and_hash(key)
        return secrets.compare_digest(hashed_key, self.hashed_key)
    
    def is_valid(self) -> bool:
        """
        Check if the API key is valid (active and not expired).
        
        Returns:
            True if the key is valid
        """
        if not self.is_active:
            return False
        
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        
        return True


class ApiPermissionDB(Base):
    """API permission database model."""
    
    __tablename__ = "api_gateway_permissions"
    
    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), ForeignKey("api_gateway_keys.id", ondelete="CASCADE"), nullable=False)
    
    namespace = Column(String(50), nullable=False)
    resource = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    api_key = relationship("ApiKeyDB", back_populates="permissions")
    
    @classmethod
    def create_permission(
        cls,
        api_key_id: str,
        namespace: str,
        resource: str,
        action: str
    ) -> "ApiPermissionDB":
        """
        Create a new API permission.
        
        Args:
            api_key_id: API key ID
            namespace: Permission namespace (e.g., 'payments')
            resource: Permission resource (e.g., 'transactions')
            action: Permission action (e.g., 'read', 'write')
            
        Returns:
            ApiPermissionDB
        """
        return cls(
            api_key_id=api_key_id,
            namespace=namespace,
            resource=resource,
            action=action
        )


# Pydantic models for API requests/responses
class ApiPermission(BaseModel):
    """API permission model for requests and responses."""
    
    namespace: str
    resource: str
    action: str
    
    class Config:
        from_attributes = True


class ApiKeyCreate(BaseModel):
    """API key creation request model."""
    
    name: str
    owner_id: str
    owner_type: str = "user"
    expires_days: int = 365
    permissions: List[Dict[str, str]] = []
    rate_limit_per_minute: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None
    allowed_ips: Optional[List[str]] = None
    allowed_origins: Optional[List[str]] = None
    
    @validator('permissions')
    def validate_permissions(cls, v):
        for perm in v:
            if not perm.get("namespace"):
                raise ValueError("Permission namespace is required")
            if not perm.get("resource"):
                raise ValueError("Permission resource is required")
            if not perm.get("action"):
                raise ValueError("Permission action is required")
        return v
    
    @validator('expires_days')
    def validate_expires_days(cls, v):
        if v < 0:
            raise ValueError("expires_days must be >= 0")
        return v


class ApiKeyResponse(BaseModel):
    """API key response model."""
    
    id: str
    name: str
    prefix: str
    owner_id: str
    owner_type: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    rate_limit_per_minute: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None
    allowed_ips: Optional[List[str]] = None
    allowed_origins: Optional[List[str]] = None
    last_used_at: Optional[datetime] = None
    use_count: int
    
    class Config:
        from_attributes = True


class ApiKeyWithSecret(ApiKeyResponse):
    """API key response model with the plain text key (only for creation)."""
    
    key: str
