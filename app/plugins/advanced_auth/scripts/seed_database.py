#!/usr/bin/env python
"""
Seed script for the advanced authentication plugin.

This script populates the database with initial data such as roles, permissions, and a default admin user.
"""
import os
import sys
import logging
import argparse
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).resolve().parents[5]))

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal
from app.plugins.advanced_auth.db_init import (
    init_roles, init_permissions, assign_role_permissions,
    create_default_admin, init_mfa_method_types
)


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def seed_database() -> None:
    """Seed the database with initial data."""
    # Create database session
    db = SessionLocal()
    
    try:
        logger.info("Seeding database with initial data...")
        
        # Initialize roles, permissions, and MFA method types
        roles = init_roles(db)
        permissions = init_permissions(db)
        assign_role_permissions(db, roles, permissions)
        init_mfa_method_types(db)
        
        # Create default admin user
        admin_role = roles.get("Admin")
        if admin_role:
            admin_user = create_default_admin(db, admin_role)
            if admin_user:
                logger.info(f"Created admin user: {admin_user.email}")
            else:
                logger.info("Admin user already exists or could not be created")
        
        logger.info("Database seeding completed successfully")
    
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
    
    finally:
        db.close()


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Seed the database with initial data")
    parser.add_argument("--force", action="store_true", help="Force seeding even if data already exists")
    args = parser.parse_args()
    
    seed_database()


if __name__ == "__main__":
    main()
