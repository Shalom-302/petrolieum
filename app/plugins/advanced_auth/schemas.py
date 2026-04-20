"""
Pydantic schemas for the advanced authentication plugin.
"""
from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid
from app.schemas.petro import OrganizationRead


class TokenType(str, Enum):
    """Token types."""
    ACCESS = "access"
    REFRESH = "refresh"


class AuthProvider(str, Enum):
    """Authentication provider types."""
    EMAIL = "email"
    GOOGLE = "google"
    GITHUB = "github"
    FACEBOOK = "facebook"
    APPLE = "apple"
    MICROSOFT = "microsoft"
    LINKEDIN = "linkedin"


class RoleBase(BaseModel):
    """Base schema for roles."""
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating roles."""
    pass


class RoleUpdate(BaseModel):
    """Schema for updating roles."""
    name: Optional[str] = None
    description: Optional[str] = None


class Role(RoleBase):
    """Schema for role response."""
    id: uuid.UUID
    is_system_role: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    """Base schema for users."""
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_country: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating users."""
    password: str = Field(..., min_length=8)
    role_id: Optional[uuid.UUID] = None
    
    @validator('password')
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(char in "!@#$%^&*()-_=+[]{}|;:,.<>/?" for char in v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str
    remember_me: bool = False


class UserUpdate(BaseModel):
    """Schema for updating users."""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    role_id: Optional[uuid.UUID] = None
    is_verified: Optional[bool] = None
    is_superuser: Optional[bool] = None
    profile_picture: Optional[str] = None


class PasswordUpdate(BaseModel):
    """Schema for updating passwords."""
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(char in "!@#$%^&*()-_=+[]{}|;:,.<>/?" for char in v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @root_validator(skip_on_failure=True)
    def check_passwords_different(cls, values):
        """Validate that the new password is different from the current one."""
        current = values.get('current_password')
        new = values.get('new_password')
        if current and new and current == new:
            raise ValueError('New password must be different from the current password')
        return values


class UserInDB(UserBase):
    """Schema for user in database."""
    id: uuid.UUID
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    role_id: Optional[uuid.UUID] = None
    organization_id: Optional[int] = None
    primary_auth_provider: Optional[str] = "email"
    profile_picture: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    """Schema for user response."""
    role: Optional[Role] = None
    organization: Optional[OrganizationRead] = None # Optionnel


class Token(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class TokenData(BaseModel):
    """Schema for token data."""
    user_id: Union[str, uuid.UUID]
    username: Optional[str] = None
    email: Optional[str] = None
    token_type: TokenType
    exp: Optional[int] = None


class OAuthProviderConfig(BaseModel):
    """Schema for OAuth provider configuration."""
    provider: AuthProvider
    client_id: str
    client_secret: str
    redirect_uri: str
    is_active: bool = True
    scope: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None


class OAuthUserInfo(BaseModel):
    """Schema for OAuth user information."""
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    picture: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class OAuthInitRequest(BaseModel):
    """Schema for initializing OAuth flow."""
    provider: AuthProvider
    redirect_uri: str
    state: Optional[str] = None


class OAuthCallbackRequest(BaseModel):
    """Schema for OAuth callback."""
    provider: AuthProvider
    code: str
    redirect_uri: str
    state: Optional[str] = None


class MFASetupRequest(BaseModel):
    """Schema for setting up MFA."""
    method_type: str  # "totp", "sms", etc.
    phone_number: Optional[str] = None  # For SMS


class MFAVerifyRequest(BaseModel):
    """Schema for verifying MFA."""
    method_id: uuid.UUID
    code: str


class MFAResponse(BaseModel):
    """Schema for MFA response."""
    method_id: uuid.UUID
    method_type: str
    is_primary: bool
    name: Optional[str] = None
    setup_data: Optional[Dict[str, Any]] = None  # For TOTP setup


class AuthResponse(BaseModel):
    """Schema for authentication response."""
    user: UserResponse
    token: Token
    requires_mfa: bool = False
    mfa_methods: Optional[List[MFAResponse]] = None


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    email: EmailStr


class PasswordResetVerify(BaseModel):
    """Schema for verifying password reset."""
    token: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(char in "!@#$%^&*()-_=+[]{}|;:,.<>/?" for char in v):
            raise ValueError('Password must contain at least one special character')
        return v


class EmailVerificationRequest(BaseModel):
    """Schema for email verification request."""
    email: EmailStr


class EmailVerificationVerify(BaseModel):
    """Schema for verifying email verification."""
    token: str
