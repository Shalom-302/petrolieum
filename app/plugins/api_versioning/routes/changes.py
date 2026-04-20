"""
Routes for managing API changes.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user, get_current_active_admin_user
from app.plugins.api_versioning.models import APIChange, APIVersion
from app.plugins.api_versioning.schemas import (
    APIChangeCreate, 
    APIChangeInDB,
    PaginatedResponse
)


router = APIRouter(prefix="/changes", tags=["API Changes"])


@router.post("/", response_model=APIChangeInDB, status_code=status.HTTP_201_CREATED)
async def create_api_change(
    change: APIChangeCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Record a change between API versions.
    Only accessible by admin users.
    """
    # Check if both versions exist
    prev_version = db.query(APIVersion).filter(APIVersion.id == change.previous_version_id).first()
    if not prev_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Previous API version with ID {change.previous_version_id} not found"
        )
    
    new_version = db.query(APIVersion).filter(APIVersion.id == change.new_version_id).first()
    if not new_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"New API version with ID {change.new_version_id} not found"
        )
    
    # Validate change type
    valid_change_types = ['added', 'modified', 'removed']
    if change.change_type not in valid_change_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid change type: {change.change_type}. Must be one of: {valid_change_types}"
        )
    
    # Create new change record
    db_change = APIChange(**change.dict())
    
    # Save to database
    db.add(db_change)
    db.commit()
    db.refresh(db_change)
    
    return db_change


@router.get("/", response_model=PaginatedResponse)
async def get_api_changes(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    previous_version_id: Optional[int] = Query(None),
    new_version_id: Optional[int] = Query(None),
    change_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get all API changes with pagination and filters.
    """
    # Base query
    query = db.query(APIChange)
    
    # Apply filters
    if previous_version_id is not None:
        query = query.filter(APIChange.previous_version_id == previous_version_id)
    
    if new_version_id is not None:
        query = query.filter(APIChange.new_version_id == new_version_id)
    
    if change_type is not None:
        query = query.filter(APIChange.change_type == change_type)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    query = query.order_by(APIChange.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Get items
    items = query.all()
    
    # Create response
    response = PaginatedResponse(
        items=[APIChangeInDB.from_orm(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
    
    return response


@router.get("/{change_id}", response_model=APIChangeInDB)
async def get_api_change(
    change_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get a specific API change by ID.
    """
    change = db.query(APIChange).filter(APIChange.id == change_id).first()
    
    if not change:
        raise HTTPException(status_code=404, detail="API change record not found")
        
    return change


@router.delete("/{change_id}", response_model=Dict[str, Any])
async def delete_api_change(
    change_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Delete a specific API change record.
    Only accessible by admin users.
    """
    # Get the change record
    db_change = db.query(APIChange).filter(APIChange.id == change_id).first()
    
    if not db_change:
        raise HTTPException(status_code=404, detail="API change record not found")
    
    # Delete the change record
    db.delete(db_change)
    db.commit()
    
    return {"success": True, "message": "API change record deleted successfully"}


@router.get("/between-versions/{from_version}/{to_version}", response_model=List[APIChangeInDB])
async def get_changes_between_versions(
    from_version: str,
    to_version: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get all changes between two API versions.
    """
    # Find the version IDs first
    from_version_obj = db.query(APIVersion).filter(APIVersion.version == from_version).first()
    if not from_version_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API version '{from_version}' not found"
        )
    
    to_version_obj = db.query(APIVersion).filter(APIVersion.version == to_version).first()
    if not to_version_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API version '{to_version}' not found"
        )
    
    # Get all changes between these versions
    changes = db.query(APIChange).filter(
        APIChange.previous_version_id == from_version_obj.id,
        APIChange.new_version_id == to_version_obj.id
    ).all()
    
    return [APIChangeInDB.from_orm(change) for change in changes]
