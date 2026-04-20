"""
Script simplifié pour initialiser l'authentification pour Kaapi

Ce script:
1. Crée un utilisateur de test directement en SQL
2. Configure les fournisseurs OAuth via les variables d'environnement

Usage:
    python -m app.commands.init_auth_simple

Run from Docker:
    ./kaapi auth init-simple
"""
import sys
import os
import uuid
import logging
import argparse
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Configuration
from app.core.config import settings

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
    {"provider": "github", "is_active": True, "name": "GitHub"},
    {"provider": "facebook", "is_active": True, "name": "Facebook"},
    {"provider": "email", "is_active": True, "name": "Email"}
]


def hash_password(password: str) -> str:
    """
    Hash a password for storing
    """
    return pwd_context.hash(password)


def setup_auth_providers() -> None:
    """
    Configure authentication providers using environment variables
    """
    try:
        # Configure each provider by setting environment variables
        for provider in AUTH_PROVIDERS:
            provider_name = provider["provider"].lower()
            logger.info(f"Setting up auth provider: {provider['name']}")
            
            # Get client ID and secret from environment variables if available
            client_id_var = f"{provider_name.upper()}_CLIENT_ID"
            client_secret_var = f"{provider_name.upper()}_CLIENT_SECRET"
            
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
        
    except Exception as e:
        logger.error(f"Error setting up auth providers: {str(e)}")
        raise


def create_test_user_sql() -> None:
    """
    Create a test user directly via SQL to avoid ORM complications
    """
    try:
        # Create database engine
        engine = create_engine(settings.DB_URL)
        
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # 1. First ensure admin role exists (as user requires a role_id)
        result = db.execute(text("SELECT id FROM auth_role WHERE name = 'admin'"))
        role = result.fetchone()
        
        if role:
            role_id = role[0]
            logger.info(f"Admin role already exists with ID: {role_id}")
        else:
            # Generate UUID for role
            role_id = str(uuid.uuid4())
            
            # Insert role
            db.execute(
                text("""
                INSERT INTO auth_role (
                    id, name, description, is_system_role, created_at, updated_at
                ) VALUES (
                    :id, :name, :description, :is_system_role, :created_at, :updated_at
                )
                """),
                {
                    "id": role_id,
                    "name": "admin",
                    "description": "Administrator role with full access",
                    "is_system_role": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )
            
            # Commit the transaction
            db.commit()
            
            logger.info(f"Created admin role with ID: {role_id}")
        
        # 2. Now check if user already exists
        result = db.execute(text("SELECT id FROM \"user\" WHERE email = :email"), 
                           {"email": TEST_USER["email"]})
        
        user = result.fetchone()
        
        if user:
            user_id = user[0]
            logger.info(f"Test user already exists with ID: {user_id}")
            
            # Update user's role to admin if needed
            db.execute(
                text("UPDATE \"user\" SET role_id = :role_id WHERE id = :user_id"),
                {"role_id": role_id, "user_id": user_id}
            )
            db.commit()
            logger.info(f"Updated user's role to admin")
        else:
            # Generate UUID for user
            user_id = str(uuid.uuid4())
            
            # Hash password
            hashed_password = hash_password(TEST_USER["password"])
            
            # Current timestamp
            now = datetime.utcnow()
            
            # Insert user with role_id
            db.execute(
                text("""
                INSERT INTO "user" (
                    id, username, email, hashed_password, 
                    first_name, last_name, is_active, is_verified,
                    is_superuser, created_at, updated_at, role_id
                ) VALUES (
                    :id, :username, :email, :hashed_password,
                    :first_name, :last_name, :is_active, :is_verified,
                    :is_superuser, :created_at, :updated_at, :role_id
                )
                """),
                {
                    "id": user_id,
                    "username": TEST_USER["username"],
                    "email": TEST_USER["email"],
                    "hashed_password": hashed_password,
                    "first_name": TEST_USER["first_name"],
                    "last_name": TEST_USER["last_name"],
                    "is_active": True,
                    "is_verified": True,
                    "is_superuser": True,
                    "created_at": now,
                    "updated_at": now,
                    "role_id": role_id  # Important: Include the role_id here
                }
            )
            
            # Commit the transaction
            db.commit()
            
            logger.info(f"Created test user with ID: {user_id}")
        
        # Close the session
        db.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating test user: {str(e)}")
        raise


def init_auth_simple(force: bool = False) -> None:
    """
    Initialize authentication with a simplified approach
    
    Args:
        force: Force initialization even if components exist
    """
    logger.info("\n===== Initializing Authentication Components (Simple Mode) =====\n")
    
    try:
        # Setup auth providers first
        logger.info("Step 1: Configuring authentication providers")
        setup_auth_providers()
        logger.info("✓ Authentication providers configured successfully\n")
        
        # Create test user with direct SQL
        logger.info("Step 2: Creating test user")
        create_test_user_sql()
        logger.info(f"✓ Test user created/verified: {TEST_USER['email']}\n")
        
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
    parser = argparse.ArgumentParser(description="Initialize authentication components (simplified)")
    parser.add_argument('--force', action='store_true', help='Force initialization even if components exist')
    
    args = parser.parse_args()
    
    init_auth_simple(force=args.force)
