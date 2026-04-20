"""
CRUD operations for the API versioning plugin.

This module provides functions for creating, reading, updating, and deleting
API versions, endpoints, and changes in the database.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from app.plugins.api_versioning.models import APIVersion, APIEndpoint, APIChange
from app.plugins.api_versioning.utils.database import get_current_version


# --- API Version CRUD operations ---

def create_api_version(
    db: Session,
    version: str,
    description: Optional[str] = None,
    is_current: bool = False
) -> APIVersion:
    """
    Create a new API version.
    
    Args:
        db: Database session
        version: Version number (e.g., '0.1', '0.2')
        description: Optional description of the version
        is_current: Whether this is the current API version
        
    Returns:
        The created API version
    """
    if is_current:
        # If this version is set as current, unset any existing current version
        db.query(APIVersion).filter(APIVersion.is_current == True).update({
            "is_current": False
        })
    
    api_version = APIVersion(
        version=version,
        description=description,
        is_current=is_current
    )
    
    db.add(api_version)
    db.commit()
    db.refresh(api_version)
    
    return api_version


def get_api_version(db: Session, version_id: int) -> Optional[APIVersion]:
    """
    Get an API version by ID.
    
    Args:
        db: Database session
        version_id: ID of the API version
        
    Returns:
        The API version or None if it does not exist
    """
    return db.query(APIVersion).filter(APIVersion.id == version_id).first()


def get_api_versions(db: Session, skip: int = 0, limit: int = 100) -> List[APIVersion]:
    """
    Get all API versions.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of API versions
    """
    return db.query(APIVersion).order_by(APIVersion.release_date.desc()).offset(skip).limit(limit).all()


def update_api_version(
    db: Session, 
    version_id: int, 
    version: Optional[str] = None,
    description: Optional[str] = None,
    is_current: Optional[bool] = None
) -> Optional[APIVersion]:
    """
    Update an API version.
    
    Args:
        db: Database session
        version_id: ID of the API version to update
        version: New version number
        description: New description
        is_current: Whether this is the current API version
        
    Returns:
        The updated API version or None if it does not exist
    """
    api_version = get_api_version(db, version_id)
    if api_version is None:
        return None
    
    if version is not None:
        api_version.version = version
    
    if description is not None:
        api_version.description = description
    
    if is_current is not None and is_current != api_version.is_current:
        if is_current:
            # If this version is being set as current, unset any existing current version
            db.query(APIVersion).filter(APIVersion.is_current == True).update({
                "is_current": False
            })
        api_version.is_current = is_current
    
    db.commit()
    db.refresh(api_version)
    
    return api_version


def delete_api_version(db: Session, version_id: int) -> bool:
    """
    Delete an API version.
    
    Args:
        db: Database session
        version_id: ID of the API version to delete
        
    Returns:
        True if the version was deleted, False if it does not exist
    """
    api_version = get_api_version(db, version_id)
    if api_version is None:
        return False
    
    db.delete(api_version)
    db.commit()
    
    return True


# --- API Endpoint CRUD operations ---

def create_api_endpoint(
    db: Session,
    path: str,
    method: str,
    version_id: int,
    description: Optional[str] = None,
    handler_module: Optional[str] = None,
    handler_function: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    response_model: Optional[Dict[str, Any]] = None
) -> APIEndpoint:
    """
    Create a new API endpoint.
    
    Args:
        db: Database session
        path: URL path of the endpoint
        method: HTTP method (GET, POST, etc.)
        version_id: ID of the API version this endpoint belongs to
        description: Description of the endpoint
        handler_module: Python module containing the handler
        handler_function: Function name of the handler
        parameters: Parameters schema
        response_model: Response model schema
        
    Returns:
        The created API endpoint
    """
    api_endpoint = APIEndpoint(
        path=path,
        method=method,
        version_id=version_id,
        description=description,
        handler_module=handler_module,
        handler_function=handler_function,
        parameters=parameters,
        response_model=response_model
    )
    
    db.add(api_endpoint)
    db.commit()
    db.refresh(api_endpoint)
    
    return api_endpoint


def get_api_endpoint(db: Session, endpoint_id: int) -> Optional[APIEndpoint]:
    """
    Get an API endpoint by ID.
    
    Args:
        db: Database session
        endpoint_id: ID of the API endpoint
        
    Returns:
        The API endpoint or None if it does not exist
    """
    return db.query(APIEndpoint).filter(APIEndpoint.id == endpoint_id).first()


def get_api_endpoints(
    db: Session, 
    version_id: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[APIEndpoint]:
    """
    Get API endpoints.
    
    Args:
        db: Database session
        version_id: Optional ID of the API version to filter by
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of API endpoints
    """
    query = db.query(APIEndpoint)
    
    if version_id is not None:
        query = query.filter(APIEndpoint.version_id == version_id)
    else:
        # If no version ID is specified, get endpoints for the current version
        current_version = get_current_version(db)
        if current_version:
            query = query.filter(APIEndpoint.version_id == current_version.id)
    
    return query.offset(skip).limit(limit).all()


# --- API Change CRUD operations ---

def create_api_change(
    db: Session,
    previous_version_id: int,
    new_version_id: int,
    endpoint_path: str,
    change_type: str,
    description: str,
    details: Optional[Dict[str, Any]] = None
) -> APIChange:
    """
    Create a new API change record.
    
    Args:
        db: Database session
        previous_version_id: ID of the previous API version
        new_version_id: ID of the new API version
        endpoint_path: Path of the affected endpoint
        change_type: Type of change ('added', 'modified', 'removed')
        description: Human-readable description of the change
        details: Detailed information about the change
        
    Returns:
        The created API change
    """
    api_change = APIChange(
        previous_version_id=previous_version_id,
        new_version_id=new_version_id,
        endpoint_path=endpoint_path,
        change_type=change_type,
        description=description,
        details=details
    )
    
    db.add(api_change)
    db.commit()
    db.refresh(api_change)
    
    return api_change


def get_api_change(db: Session, change_id: int) -> Optional[APIChange]:
    """
    Get an API change by ID.
    
    Args:
        db: Database session
        change_id: ID of the API change
        
    Returns:
        The API change or None if it does not exist
    """
    return db.query(APIChange).filter(APIChange.id == change_id).first()


def get_api_changes(
    db: Session, 
    previous_version_id: Optional[int] = None,
    new_version_id: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[APIChange]:
    """
    Get API changes.
    
    Args:
        db: Database session
        previous_version_id: Optional ID of the previous API version to filter by
        new_version_id: Optional ID of the new API version to filter by
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of API changes
    """
    query = db.query(APIChange)
    
    if previous_version_id is not None:
        query = query.filter(APIChange.previous_version_id == previous_version_id)
    
    if new_version_id is not None:
        query = query.filter(APIChange.new_version_id == new_version_id)
    
    return query.offset(skip).limit(limit).all()
