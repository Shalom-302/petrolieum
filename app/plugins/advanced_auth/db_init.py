"""
Database initialization script for the advanced authentication plugin.

This script sets up the database with the initial roles, permissions, and a default admin user.
"""
from typing import Dict, Any, Optional, List
import logging
import uuid
from datetime import datetime
import secrets
import string

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import Depends

from app.core.config import settings
from app.core.db import get_db
from .models import User, Role, Permission, Group, MFAMethodType
from .utils import get_password_hash, is_password_secure

logger = logging.getLogger(__name__)


def generate_strong_password(length: int = 12) -> str:
    """
    Generate a strong random password.
    
    Args:
        length: Length of the password to generate
        
    Returns:
        A random password with mixed case, digits, and special characters
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}|;:,.<>/?"
    
    # Ensure at least one of each character type
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*()-_=+[]{}|;:,.<>/?")
    ]
    
    # Fill the rest with random characters
    password.extend(secrets.choice(alphabet) for _ in range(length - 4))
    
    # Shuffle the password
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def init_roles(db: Session) -> Dict[str, Role]:
    """
    Initialize default roles in the database.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary of created roles
    """
    # Define default roles
    default_roles = [
        {"name": "Admin", "description": "Full system access", "is_system_role": True},
        {"name": "User", "description": "Standard user access", "is_system_role": True},
        {"name": "Guest", "description": "Limited access", "is_system_role": True}
    ]
    
    roles = {}
    
    # Create roles if they don't exist
    for role_data in default_roles:
        role = db.query(Role).filter(Role.name == role_data["name"]).first()
        if not role:
            role = Role(**role_data)
            db.add(role)
            try:
                db.commit()
                db.refresh(role)
                logger.info(f"Created role: {role.name}")
            except IntegrityError:
                db.rollback()
                # Role might have been created in a race condition
                role = db.query(Role).filter(Role.name == role_data["name"]).first()
                if not role:
                    logger.error(f"Failed to create role: {role_data['name']}")
                    continue
        
        roles[role.name] = role
    
    return roles


def init_permissions(db: Session) -> Dict[str, Permission]:
    """
    Initialize default permissions in the database.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary of created permissions
    """
    # Define default permissions
    default_permissions = [
        {"name": "user:read", "description": "Can read user data"},
        {"name": "user:write", "description": "Can modify user data"},
        {"name": "user:delete", "description": "Can delete users"},
        {"name": "role:read", "description": "Can read role data"},
        {"name": "role:write", "description": "Can modify role data"},
        {"name": "role:delete", "description": "Can delete roles"},
        {"name": "group:read", "description": "Can read group data"},
        {"name": "group:write", "description": "Can modify group data"},
        {"name": "group:delete", "description": "Can delete groups"}
    ]
    
    permissions = {}
    
    # Create permissions if they don't exist
    for perm_data in default_permissions:
        perm = db.query(Permission).filter(Permission.name == perm_data["name"]).first()
        if not perm:
            perm = Permission(**perm_data)
            db.add(perm)
            try:
                db.commit()
                db.refresh(perm)
                logger.info(f"Created permission: {perm.name}")
            except IntegrityError:
                db.rollback()
                # Permission might have been created in a race condition
                perm = db.query(Permission).filter(Permission.name == perm_data["name"]).first()
                if not perm:
                    logger.error(f"Failed to create permission: {perm_data['name']}")
                    continue
        
        permissions[perm.name] = perm
    
    return permissions


def assign_role_permissions(db: Session, roles: Dict[str, Role], permissions: Dict[str, Permission]) -> None:
    """
    Assign permissions to roles.
    
    Args:
        db: Database session
        roles: Dictionary of roles
        permissions: Dictionary of permissions
    """
    # Admin role gets all permissions
    admin_role = roles.get("Admin")
    if admin_role:
        for perm in permissions.values():
            if perm not in admin_role.permissions:
                admin_role.permissions.append(perm)
        
        db.commit()
        logger.info("Assigned all permissions to Admin role")
    
    # User role gets read permissions
    user_role = roles.get("User")
    if user_role:
        read_perms = [p for name, p in permissions.items() if name.endswith(":read")]
        for perm in read_perms:
            if perm not in user_role.permissions:
                user_role.permissions.append(perm)
        
        db.commit()
        logger.info("Assigned read permissions to User role")


def create_default_admin(db: Session, admin_role: Role) -> Optional[User]:
    """
    Create a default admin user if one doesn't exist.
    
    Args:
        db: Database session
        admin_role: Admin role
        
    Returns:
        Created admin user or None if already exists
    """
    # Check if admin user already exists
    admin_user = db.query(User).filter(User.is_superuser == True).first()
    if admin_user:
        logger.info("Admin user already exists")
        return None
    
    # Admin user settings from environment or config
    admin_email = getattr(settings, "ADMIN_EMAIL", "admin@example.com")
    admin_password = getattr(settings, "ADMIN_PASSWORD", None)
    
    # Generate a strong password if not provided
    if not admin_password or not is_password_secure(admin_password):
        admin_password = generate_strong_password(16)
        logger.warning(f"Generated random admin password: {admin_password}")
        logger.warning("Please change this password after first login!")
    
    # Create admin user
    admin_user = User(
        email=admin_email,
        username="admin",
        hashed_password=get_password_hash(admin_password),
        first_name="Admin",
        last_name="User",
        is_active=True,
        is_verified=True,
        is_superuser=True,
        role_id=admin_role.id,
        primary_auth_provider="email"
    )
    
    db.add(admin_user)
    
    try:
        db.commit()
        db.refresh(admin_user)
        logger.info(f"Created admin user: {admin_user.email}")
        return admin_user
    except IntegrityError:
        db.rollback()
        logger.error("Failed to create admin user")
        return None


def init_mfa_method_types(db: Session) -> None:
    """
    Initialize MFA method types.
    
    Args:
        db: Database session
    """
    # Define default MFA method types
    default_types = [
        {"name": "totp", "description": "Time-based One-time Password"},
        {"name": "sms", "description": "SMS verification code"},
        {"name": "email", "description": "Email verification code"},
        {"name": "recovery_codes", "description": "Recovery codes"}
    ]
    
    # Create types if they don't exist
    for type_data in default_types:
        mfa_type = db.query(MFAMethodType).filter(MFAMethodType.name == type_data["name"]).first()
        if not mfa_type:
            mfa_type = MFAMethodType(**type_data)
            db.add(mfa_type)
            try:
                db.commit()
                logger.info(f"Created MFA method type: {mfa_type.name}")
            except IntegrityError:
                db.rollback()
                logger.error(f"Failed to create MFA method type: {type_data['name']}")


def init_database(db: Session = None) -> None:
    """
    Initialize the database with default data.
    
    Args:
        db: Database session (optional)
    """
    close_db = False
    if db is None:
        # Create a new session if not provided
        from app.core.db import SessionLocal
        db = SessionLocal()
        close_db = True
    
    try:
        logger.info("Initializing advanced authentication database...")
        
        # Initialize roles, permissions and MFA method types
        roles = init_roles(db)
        permissions = init_permissions(db)
        assign_role_permissions(db, roles, permissions)
        init_mfa_method_types(db)
        
        # Create default admin user
        admin_role = roles.get("Admin")
        if admin_role:
            create_default_admin(db, admin_role)
        
        logger.info("Database initialization completed successfully")
    
    finally:
        if close_db:
            db.close()


# To initialize the database when the plugin is loaded
def init_on_startup(db: Session = Depends(get_db)) -> None:
    """
    Initialize the database on application startup.
    This can be used as a dependency in a FastAPI startup event.
    
    Args:
        db: Database session
    """
    init_database(db)
