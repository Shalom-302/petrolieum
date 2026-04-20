"""
Routes for managing API versions.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user, get_current_active_admin_user
from app.plugins.api_versioning.models import APIVersion
from app.plugins.api_versioning.schemas import (
    APIVersionCreate, 
    APIVersionUpdate, 
    APIVersionInDB,
    PaginatedResponse
)


router = APIRouter(prefix="/versions", tags=["API Versions"])


@router.post("/", response_model=APIVersionInDB, status_code=status.HTTP_201_CREATED)
async def create_api_version(
    version: APIVersionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Create a new API version.
    Only accessible by admin users.
    """
    # Check if version already exists
    existing_version = db.query(APIVersion).filter(APIVersion.version == version.version).first()
    if existing_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API version '{version.version}' already exists"
        )
    
    # Create new version
    db_version = APIVersion(**version.dict())
    
    # Save to database
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    
    return db_version


@router.get("/", response_model=PaginatedResponse)
async def get_api_versions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    is_deprecated: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get all API versions with pagination and filters.
    """
    # Base query
    query = db.query(APIVersion)
    
    # Apply filters
    if is_active is not None:
        query = query.filter(APIVersion.is_active == is_active)
        
    if is_deprecated is not None:
        query = query.filter(APIVersion.is_deprecated == is_deprecated)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    query = query.order_by(APIVersion.version.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Get items
    items = query.all()
    
    # Create response
    response = PaginatedResponse(
        items=[APIVersionInDB.from_orm(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
    
    return response


@router.get("/{version_id}", response_model=APIVersionInDB)
async def get_api_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get a specific API version by ID.
    """
    version = db.query(APIVersion).filter(APIVersion.id == version_id).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="API version not found")
        
    return version


@router.get("/by-name/{version_name}", response_model=APIVersionInDB)
async def get_api_version_by_name(
    version_name: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get a specific API version by name (e.g., 'v1', 'v2').
    """
    version = db.query(APIVersion).filter(APIVersion.version == version_name).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="API version not found")
        
    return version


@router.put("/{version_id}", response_model=APIVersionInDB)
async def update_api_version(
    version_id: int,
    version_update: APIVersionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Update a specific API version.
    Only accessible by admin users.
    """
    # Get the version
    db_version = db.query(APIVersion).filter(APIVersion.id == version_id).first()
    
    if not db_version:
        raise HTTPException(status_code=404, detail="API version not found")
    
    # Update fields if they exist in the request
    update_data = version_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_version, key, value)
    
    # Save changes
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    
    return db_version


@router.delete("/{version_id}", response_model=Dict[str, Any])
async def delete_api_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Delete a specific API version.
    Only accessible by admin users.
    """
    # Get the version
    db_version = db.query(APIVersion).filter(APIVersion.id == version_id).first()
    
    if not db_version:
        raise HTTPException(status_code=404, detail="API version not found")
    
    # Delete the version (will cascade to endpoints due to relationship)
    db.delete(db_version)
    db.commit()
    
    return {"success": True, "message": "API version deleted successfully"}


@router.post("/{version_id}/deprecate", response_model=APIVersionInDB)
async def deprecate_api_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Mark an API version as deprecated.
    Only accessible by admin users.
    """
    from datetime import datetime
    
    # Get the version
    db_version = db.query(APIVersion).filter(APIVersion.id == version_id).first()
    
    if not db_version:
        raise HTTPException(status_code=404, detail="API version not found")
    
    # Mark as deprecated
    db_version.is_deprecated = True
    db_version.deprecation_date = datetime.utcnow()
    
    # Save changes
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    
    return db_version


@router.post("/{version_id}/activate", response_model=APIVersionInDB)
async def activate_api_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Activate an API version.
    Only accessible by admin users.
    """
    # Get the version
    db_version = db.query(APIVersion).filter(APIVersion.id == version_id).first()
    
    if not db_version:
        raise HTTPException(status_code=404, detail="API version not found")
    
    # Activate
    db_version.is_active = True
    
    # Save changes
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    
    return db_version


@router.post("/{version_id}/deactivate", response_model=APIVersionInDB)
async def deactivate_api_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Deactivate an API version.
    Only accessible by admin users.
    """
    # Get the version
    db_version = db.query(APIVersion).filter(APIVersion.id == version_id).first()
    
    if not db_version:
        raise HTTPException(status_code=404, detail="API version not found")
    
    # Deactivate
    db_version.is_active = False
    
    # Save changes
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    
    return db_version
