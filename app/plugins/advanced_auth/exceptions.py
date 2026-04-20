"""
Exceptions and error handling for the advanced authentication plugin.
"""
from typing import Dict, Any, Optional, List, Union
import logging
from fastapi import Request, FastAPI, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuthException(Exception):
    """Base exception for authentication errors."""
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the exception.
        
        Args:
            status_code: HTTP status code
            detail: Error message
            error_code: Internal error code
            error_details: Additional error details
        """
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.error_details = error_details or {}


class InvalidCredentialsException(AuthException):
    """Exception for invalid credentials."""
    def __init__(self, detail: str = "Invalid credentials"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="INVALID_CREDENTIALS"
        )


class AccountLockedException(AuthException):
    """Exception for locked accounts."""
    def __init__(self, detail: str, lock_minutes: int = 0):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="ACCOUNT_LOCKED",
            error_details={"lock_minutes": lock_minutes}
        )


class AccountInactiveException(AuthException):
    """Exception for inactive accounts."""
    def __init__(self, detail: str = "Account is inactive"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="ACCOUNT_INACTIVE"
        )


class EmailNotVerifiedException(AuthException):
    """Exception for unverified email."""
    def __init__(self, detail: str = "Email address not verified"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="EMAIL_NOT_VERIFIED"
        )


class InvalidTokenException(AuthException):
    """Exception for invalid tokens."""
    def __init__(self, detail: str = "Invalid token"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="INVALID_TOKEN"
        )


class ExpiredTokenException(AuthException):
    """Exception for expired tokens."""
    def __init__(self, detail: str = "Token has expired"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="EXPIRED_TOKEN"
        )


class PermissionDeniedException(AuthException):
    """Exception for permission denied."""
    def __init__(self, detail: str = "Permission denied"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="PERMISSION_DENIED"
        )


class UserExistsException(AuthException):
    """Exception for existing user."""
    def __init__(self, detail: str = "User already exists"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="USER_EXISTS"
        )


class InvalidPasswordException(AuthException):
    """Exception for invalid passwords."""
    def __init__(self, detail: str = "Invalid password"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="INVALID_PASSWORD"
        )


class MFARequiredException(AuthException):
    """Exception for required MFA."""
    def __init__(self, detail: str = "Multi-factor authentication required", mfa_methods: List[Dict[str, Any]] = None):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="MFA_REQUIRED",
            error_details={"mfa_methods": mfa_methods or []}
        )


class InvalidMFACodeException(AuthException):
    """Exception for invalid MFA codes."""
    def __init__(self, detail: str = "Invalid MFA code"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="INVALID_MFA_CODE"
        )


class OAuthException(AuthException):
    """Exception for OAuth errors."""
    def __init__(self, detail: str, provider: str, error_code: str = "OAUTH_ERROR"):
        """Initialize the exception."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code,
            error_details={"provider": provider}
        )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers for the authentication plugin.
    
    Args:
        app: FastAPI application
    """
    
    @app.exception_handler(AuthException)
    async def auth_exception_handler(request: Request, exc: AuthException):
        """Handle authentication exceptions."""
        logger.warning(f"Authentication error: {exc.detail} (code: {exc.error_code})")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "error_details": exc.error_details
            }
        )
    
    @app.exception_handler(InvalidCredentialsException)
    async def invalid_credentials_exception_handler(request: Request, exc: InvalidCredentialsException):
        """Handle invalid credentials exceptions."""
        logger.warning(f"Invalid credentials attempt: {request.client.host}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "error_details": exc.error_details
            }
        )
    
    @app.exception_handler(AccountLockedException)
    async def account_locked_exception_handler(request: Request, exc: AccountLockedException):
        """Handle account locked exceptions."""
        logger.warning(f"Locked account access attempt: {request.client.host}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "error_details": exc.error_details
            }
        )
