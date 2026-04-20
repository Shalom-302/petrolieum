"""
Database utility functions for the API versioning plugin.

This module provides utility functions for interacting with the database
specifically for the API versioning plugin.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from app.plugins.api_versioning.models import APIVersion, APIEndpoint, APIChange


def get_current_version(db: Session) -> Optional[APIVersion]:
    """
    Get the current API version from the database.
    
    Args:
        db: Database session
        
    Returns:
        The current API version or None if no current version exists
    """
    return db.query(APIVersion).filter(APIVersion.is_current == True).first()


def set_current_version(db: Session, version_id: int) -> Optional[APIVersion]:
    """
    Set the specified version as the current API version.
    
    This function sets is_current=False for all versions
    and sets is_current=True for the specified version.
    
    Args:
        db: Database session
        version_id: ID of the version to set as current
        
    Returns:
        The new current version or None if the version does not exist
    """
    # Set all versions to not current
    db.query(APIVersion).update({APIVersion.is_current: False})
    
    # Set the specified version as current
    version = db.query(APIVersion).filter(APIVersion.id == version_id).first()
    if version:
        version.is_current = True
        db.commit()
        db.refresh(version)
    
    return version


def get_api_version_by_number(db: Session, version: str) -> Optional[APIVersion]:
    """
    Get an API version by its version number.
    
    Args:
        db: Database session
        version: Version number string (e.g., "0.1", "0.2")
        
    Returns:
        The API version or None if it does not exist
    """
    return db.query(APIVersion).filter(APIVersion.version == version).first()


def get_endpoints_for_version(db: Session, version_id: int) -> List[APIEndpoint]:
    """
    Get all endpoints for the specified API version.
    
    Args:
        db: Database session
        version_id: ID of the API version
        
    Returns:
        List of API endpoints for the version
    """
    return db.query(APIEndpoint).filter(APIEndpoint.version_id == version_id).all()


def get_changes_between_versions(
    db: Session, 
    previous_version_id: int, 
    new_version_id: int
) -> List[APIChange]:
    """
    Get all changes between two API versions.
    
    Args:
        db: Database session
        previous_version_id: ID of the previous API version
        new_version_id: ID of the new API version
        
    Returns:
        List of API changes between the versions
    """
    return db.query(APIChange).filter(
        APIChange.previous_version_id == previous_version_id,
        APIChange.new_version_id == new_version_id
    ).all()
