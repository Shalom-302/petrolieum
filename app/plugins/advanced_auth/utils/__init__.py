"""
Utility functions for the advanced authentication plugin.
"""
from .security import (
    verify_password, get_password_hash, is_password_secure,
    DataEncryptor, create_hmac_signature, verify_hmac_signature,
    get_current_user, get_current_active_user, require_role, require_superuser
)
from .token import (
    create_token, create_access_token, create_refresh_token,
    create_email_verification_token, create_password_reset_token,
    decode_token, validate_token,
    ACCESS_TOKEN, REFRESH_TOKEN, EMAIL_VERIFICATION_TOKEN, PASSWORD_RESET_TOKEN
)

__all__ = [
    "verify_password", "get_password_hash", "is_password_secure",
    "DataEncryptor", "create_hmac_signature", "verify_hmac_signature",
    "get_current_user", "get_current_active_user", "require_role", "require_superuser",
    "create_token", "create_access_token", "create_refresh_token",
    "create_email_verification_token", "create_password_reset_token",
    "decode_token", "validate_token",
    "ACCESS_TOKEN", "REFRESH_TOKEN", "EMAIL_VERIFICATION_TOKEN", "PASSWORD_RESET_TOKEN"
]
