"""
Configuration for the advanced authentication plugin.
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseSettings, validator, AnyHttpUrl, EmailStr, Field, SecretStr
import os
from enum import Enum


class AuthConfig(BaseSettings):
    """
    Authentication configuration settings.
    """
    # JWT token settings
    SECRET_KEY: str = Field(..., env="AUTH_SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(30, env="REFRESH_TOKEN_EXPIRE_DAYS")
    TOKEN_ALGORITHM: str = Field("HS256", env="TOKEN_ALGORITHM")
    
    # Password settings
    PASSWORD_MIN_LENGTH: int = Field(8, env="PASSWORD_MIN_LENGTH")
    PASSWORD_REQUIRE_UPPERCASE: bool = Field(True, env="PASSWORD_REQUIRE_UPPERCASE")
    PASSWORD_REQUIRE_LOWERCASE: bool = Field(True, env="PASSWORD_REQUIRE_LOWERCASE")
    PASSWORD_REQUIRE_DIGIT: bool = Field(True, env="PASSWORD_REQUIRE_DIGIT")
    PASSWORD_REQUIRE_SPECIAL: bool = Field(True, env="PASSWORD_REQUIRE_SPECIAL")
    
    # Account security
    MAX_FAILED_LOGIN_ATTEMPTS: int = Field(5, env="MAX_FAILED_LOGIN_ATTEMPTS")
    ACCOUNT_LOCKOUT_MINUTES: int = Field(15, env="ACCOUNT_LOCKOUT_MINUTES")
    
    # Session settings
    SESSION_EXPIRE_DAYS: int = Field(90, env="SESSION_EXPIRE_DAYS")
    
    # Admin user
    ADMIN_EMAIL: EmailStr = Field("admin@example.com", env="ADMIN_EMAIL")
    ADMIN_PASSWORD: Optional[SecretStr] = Field(None, env="ADMIN_PASSWORD")
    
    # Email verification
    REQUIRE_EMAIL_VERIFICATION: bool = Field(True, env="REQUIRE_EMAIL_VERIFICATION")
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = Field(24, env="EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS")
    
    # Password reset
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = Field(1, env="PASSWORD_RESET_TOKEN_EXPIRE_HOURS")
    
    # User registration
    ALLOW_REGISTRATION: bool = Field(True, env="ALLOW_REGISTRATION")
    DEFAULT_ROLE: str = Field("User", env="DEFAULT_ROLE")
    
    # OAuth providers
    OAUTH_PROVIDERS: Dict[str, Dict[str, str]] = Field(
        default_factory=lambda: {
            "github": {
                "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
                "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
            },
            "google": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            },
            "facebook": {
                "client_id": os.getenv("FACEBOOK_CLIENT_ID", ""),
                "client_secret": os.getenv("FACEBOOK_CLIENT_SECRET", ""),
            },
        }
    )
    
    # MFA settings
    ENABLE_MFA: bool = Field(True, env="ENABLE_MFA")
    
    # Encryption settings for sensitive data
    ENCRYPTION_KEY: Optional[str] = Field(None, env="ENCRYPTION_KEY")
    
    @validator("ENCRYPTION_KEY")
    def validate_encryption_key(cls, v):
        """Validate encryption key length."""
        if v is not None and len(v) < 32:
            raise ValueError("Encryption key must be at least 32 characters")
        return v
    
    class Config:
        """Pydantic configuration."""
        env_prefix = "AUTH_"
        env_file = ".env"
        case_sensitive = True


# Create a global instance
auth_config = AuthConfig()


def get_auth_config() -> AuthConfig:
    """
    Get the authentication configuration.
    
    Returns:
        Authentication configuration
    """
    return auth_config
