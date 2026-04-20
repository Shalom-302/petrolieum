"""
Example usage of the advanced authentication plugin.

This script demonstrates how to interact with the authentication system
programmatically in your application.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.plugins.advanced_auth.service import AuthService
from app.plugins.advanced_auth.schemas import UserCreate, UserLogin, UserUpdate
from app.plugins.advanced_auth.models import User
from app.plugins.advanced_auth.exceptions import AuthException


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def register_user_example() -> Optional[User]:
    """Example of user registration."""
    db = SessionLocal()
    service = AuthService(db)
    
    try:
        # Create a user registration schema
        user_data = UserCreate(
            email="example@example.com",
            username="example_user",
            password="SecurePassword123!",
            first_name="Example",
            last_name="User"
        )
        
        # Register the user
        user = service.register_user(user_data)
        logger.info(f"User registered: {user.email}")
        
        return user
    
    except AuthException as e:
        logger.error(f"Registration error: {e.detail}")
        return None
    
    finally:
        db.close()


async def login_user_example(email: str, password: str) -> Dict[str, Any]:
    """Example of user login."""
    db = SessionLocal()
    service = AuthService(db)
    
    try:
        # Authenticate the user
        user = service.authenticate_user(email, password)
        
        if user:
            # Create tokens
            tokens = service.create_tokens(user)
            logger.info(f"User logged in: {user.email}")
            
            return {
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "username": user.username
                },
                "tokens": tokens
            }
        
        return {"error": "Authentication failed"}
    
    except AuthException as e:
        logger.error(f"Login error: {e.detail}")
        return {"error": e.detail}
    
    finally:
        db.close()


async def update_user_example(user_id: str, data: Dict[str, Any]) -> Optional[User]:
    """Example of user update."""
    db = SessionLocal()
    service = AuthService(db)
    
    try:
        # Create an update schema
        update_data = UserUpdate(**data)
        
        # Update the user
        updated_user = service.update_user(user_id, update_data)
        logger.info(f"User updated: {updated_user.email}")
        
        return updated_user
    
    except AuthException as e:
        logger.error(f"Update error: {e.detail}")
        return None
    
    finally:
        db.close()


async def get_user_by_token_example(token: str) -> Optional[User]:
    """Example of getting a user by token."""
    db = SessionLocal()
    service = AuthService(db)
    
    try:
        # Get user by token
        user = service.get_user_by_token(token)
        logger.info(f"Retrieved user: {user.email}")
        
        return user
    
    except AuthException as e:
        logger.error(f"Token validation error: {e.detail}")
        return None
    
    finally:
        db.close()


async def oauth_flow_example(provider: str, code: str, redirect_uri: str) -> Dict[str, Any]:
    """Example of OAuth flow."""
    db = SessionLocal()
    service = AuthService(db)
    
    try:
        # Handle OAuth callback
        result = await service.handle_oauth_callback(provider, code, redirect_uri)
        logger.info(f"OAuth flow completed for provider: {provider}")
        
        return result
    
    except AuthException as e:
        logger.error(f"OAuth error: {e.detail}")
        return {"error": e.detail}
    
    finally:
        db.close()


async def mfa_setup_example(user_id: str, mfa_type: str) -> Dict[str, Any]:
    """Example of MFA setup."""
    db = SessionLocal()
    service = AuthService(db)
    
    try:
        # Set up MFA
        setup_data = await service.setup_mfa(user_id, mfa_type)
        logger.info(f"MFA setup initiated for user: {user_id}, type: {mfa_type}")
        
        return setup_data
    
    except AuthException as e:
        logger.error(f"MFA setup error: {e.detail}")
        return {"error": e.detail}
    
    finally:
        db.close()


async def main():
    """Run the examples."""
    # Register a user
    user = await register_user_example()
    
    if user:
        # Login the user
        login_result = await login_user_example("example@example.com", "SecurePassword123!")
        
        if "error" not in login_result:
            # Update the user
            update_data = {
                "first_name": "Updated",
                "last_name": "Name"
            }
            updated_user = await update_user_example(str(user.id), update_data)
            
            # Get user by token
            token = login_result["tokens"]["access_token"]
            user_from_token = await get_user_by_token_example(token)
            
            # Set up MFA
            mfa_setup = await mfa_setup_example(str(user.id), "totp")
            logger.info(f"MFA setup result: {mfa_setup}")


if __name__ == "__main__":
    asyncio.run(main())
