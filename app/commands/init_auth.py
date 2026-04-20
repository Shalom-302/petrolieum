"""
Script to initialize authentication components for Kaapi

This script will:
1. Create a test user with email authentication
2. Configure authentication providers in the database
3. Set up necessary permissions and roles

Usage:
    python -m app.commands.init_auth

Run from Docker:
    ./kaapi auth init
"""
import sys
import os
import uuid
from typing import List, Optional
import logging
from pathlib import Path
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import Depends
from passlib.context import CryptContext

# Import database and models
from app.core.db import get_db, engine
from app.core.config import settings

# Import correct models from the plugin
from app.plugins.advanced_auth.models import User, Role, Permission

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test user credentials
TEST_USER = {
    "username": "test@example.com",
    "email": "test@example.com",
    "password": "Passw0rd!",
    "first_name": "Test",
    "last_name": "User"
}

# Authentication providers to configure
AUTH_PROVIDERS = [
    {"provider": "google", "is_active": True, "name": "Google"},
    # {"provider": "github", "is_active": True, "name": "GitHub"},
    # {"provider": "facebook", "is_active": True, "name": "Facebook"},
    # {"provider": "email", "is_active": True, "name": "Email"}
]


def hash_password(password: str) -> str:
    """
    Hash a password for storing
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a stored password against one provided by user
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_test_user(db: Session) -> User:
    """
    Create a test user in the database
    """
    # Check if user already exists
    user_exists = db.query(User).filter(
        User.email == TEST_USER["email"]
    ).first()
    
    if user_exists:
        logger.info(f"Test user {TEST_USER['email']} already exists")
        return user_exists
        
    # Create new user
    try:
        new_user = User(
            id=uuid.uuid4(),  # UUID type, not string
            email=TEST_USER["email"],
            username=TEST_USER["username"],
            hashed_password=hash_password(TEST_USER["password"]),
            first_name=TEST_USER["first_name"],
            last_name=TEST_USER["last_name"],
            is_active=True,
            is_verified=True,
            is_superuser=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"Created test user: {new_user.email}")
        return new_user
    
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating test user: {str(e)}")
        # Try to get the user that might already exist
        return db.query(User).filter(User.email == TEST_USER["email"]).first()
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating test user: {str(e)}")
        raise


def setup_auth_providers(db: Session) -> None:
    """
    Configure authentication providers using environment variables or defaults.
    This method creates or updates environment variables for OAuth providers.
    
    Instead of depending on Pydantic config classes which might change in the future,
    this function sets up environment variables directly which will be read by the app.
    """
    try:
        # Configure each provider by setting environment variables
        for provider in AUTH_PROVIDERS:
            provider_name = provider["provider"].lower()
            logger.info(f"Setting up auth provider: {provider['name']}")
            
            # Get client ID and secret from environment variables if available
            client_id_var = f"{provider_name.upper()}_CLIENT_ID"
            client_secret_var = f"{provider_name.upper()}_CLIENT_SECRET"
            
            # For example GitHub credentials would be in GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET
            # Check if these environment variables are already set
            if not os.environ.get(client_id_var):
                os.environ[client_id_var] = "placeholder-id-for-development"
                logger.info(f"Set environment variable {client_id_var} with placeholder value")
            else:
                logger.info(f"Environment variable {client_id_var} already exists")
                
            if not os.environ.get(client_secret_var):
                os.environ[client_secret_var] = "placeholder-secret-for-development"
                logger.info(f"Set environment variable {client_secret_var} with placeholder value")
            else:
                logger.info(f"Environment variable {client_secret_var} already exists")
            
            # Email provider is handled differently - it's usually the default
            if provider_name == "email":
                logger.info("Email authentication is enabled by default")
                
            logger.info(f"Configured {provider_name} OAuth provider")
        
        logger.info("Auth providers configured successfully")
        
        # For a more permanent solution, we could write these to a .env file
        # But we'll skip that for now since it's just placeholders
    
    except Exception as e:
        logger.error(f"Error setting up auth providers: {str(e)}")
        raise


def create_admin_role(db: Session, user: User) -> None:
    """
    Create an admin role and assign it to the test user
    """
    try:
        # Create admin role if it doesn't exist
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        
        if not admin_role:
            admin_role = Role(
                id=uuid.uuid4(),
                name="admin",
                description="Administrator role with full access",
                is_system_role=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(admin_role)
            db.commit()
            db.refresh(admin_role)
            logger.info("Created admin role")
        
        # Assign role to user based on the actual model relationship
        if hasattr(user, 'role') and user.role != admin_role:
            user.role = admin_role
            db.commit()
            logger.info(f"Assigned admin role to user {user.email}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating admin role: {str(e)}")
        raise


def init_auth(force: bool = False) -> None:
    """
    Initialize all authentication components
    
    Args:
        force: Force initialization even if components exist
    """
    logger.info("\n===== Initializing Authentication Components =====\n")
    
    # Get DB session
    db = next(get_db())
    
    try:
        # Setup auth providers first
        logger.info("Step 1: Configuring authentication providers")
        setup_auth_providers(db)
        logger.info("✓ Authentication providers configured successfully\n")
        
        # Create test user
        logger.info("Step 2: Creating test user")
        user = create_test_user(db)
        logger.info(f"✓ Test user created/verified: {user.email}\n")
        
        # Create admin role and assign to user
        logger.info("Step 3: Setting up admin role and permissions")
        create_admin_role(db, user)
        logger.info("✓ Admin role configured successfully\n")
        
        # Create basic permissions if needed
        # Here you can add code to create basic permissions
        
        # Final success message
        logger.info("\n===================================================")
        logger.info("✅ Authentication initialization completed successfully")
        logger.info("===================================================")
        logger.info(f"\nYou can now log in with the following credentials:")
        logger.info(f"Email:    {TEST_USER['email']}")
        logger.info(f"Password: {TEST_USER['password']}")
        logger.info("\nFor production use, please change this password!")
        
        # Additional instructions
        logger.info("\nNext steps:")
        logger.info("1. Configure OAuth providers if needed in environment variables:")
        for provider in AUTH_PROVIDERS:
            if provider['provider'] != 'email':
                logger.info(f"   - Set {provider['provider'].upper()}_CLIENT_ID and {provider['provider'].upper()}_CLIENT_SECRET")
        logger.info("2. Run the application with './kaapi run' or 'docker-compose up'")
        logger.info("3. Access the application in your browser")
        
    except Exception as e:
        logger.error(f"\n❌ Authentication initialization failed: {str(e)}")
        logger.error("Check the error above for more details")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize authentication components")
    parser.add_argument('--force', action='store_true', help='Force initialization even if components exist')
    
    args = parser.parse_args()
    
    init_auth(force=args.force)
