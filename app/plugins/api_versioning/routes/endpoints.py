"""
Routes for managing API endpoints.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user, get_current_active_admin_user
from app.plugins.api_versioning.models import APIEndpoint, APIVersion
from app.plugins.api_versioning.schemas import (
    APIEndpointCreate, 
    APIEndpointUpdate, 
    APIEndpointInDB,
    PaginatedResponse
)


router = APIRouter(prefix="/endpoints", tags=["API Endpoints"])


@router.post("/", response_model=APIEndpointInDB, status_code=status.HTTP_201_CREATED)
async def create_api_endpoint(
    endpoint: APIEndpointCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Register a new API endpoint for a specific version.
    Only accessible by admin users.
    """
    # Check if version exists
    version = db.query(APIVersion).filter(APIVersion.id == endpoint.version_id).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API version with ID {endpoint.version_id} not found"
        )
    
    # Check if endpoint already exists for this version
    existing_endpoint = db.query(APIEndpoint).filter(
        APIEndpoint.path == endpoint.path,
        APIEndpoint.method == endpoint.method,
        APIEndpoint.version_id == endpoint.version_id
    ).first()
    
    if existing_endpoint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Endpoint {endpoint.method} {endpoint.path} already exists for version {version.version}"
        )
    
    # Create new endpoint
    db_endpoint = APIEndpoint(**endpoint.dict())
    
    # Save to database
    db.add(db_endpoint)
    db.commit()
    db.refresh(db_endpoint)
    
    return db_endpoint


@router.get("/", response_model=PaginatedResponse)
async def get_api_endpoints(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    version_id: Optional[int] = Query(None),
    path: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get all API endpoints with pagination and filters.
    """
    # Base query
    query = db.query(APIEndpoint)
    
    # Apply filters
    if version_id is not None:
        query = query.filter(APIEndpoint.version_id == version_id)
        
    if path is not None:
        query = query.filter(APIEndpoint.path.contains(path))
    
    if method is not None:
        query = query.filter(APIEndpoint.method == method.upper())
    
    if is_active is not None:
        query = query.filter(APIEndpoint.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    query = query.order_by(APIEndpoint.path)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Get items
    items = query.all()
    
    # Create response
    response = PaginatedResponse(
        items=[APIEndpointInDB.from_orm(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
    
    return response


@router.get("/{endpoint_id}", response_model=APIEndpointInDB)
async def get_api_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get a specific API endpoint by ID.
    """
    endpoint = db.query(APIEndpoint).filter(APIEndpoint.id == endpoint_id).first()
    
    if not endpoint:
        raise HTTPException(status_code=404, detail="API endpoint not found")
        
    return endpoint


@router.put("/{endpoint_id}", response_model=APIEndpointInDB)
async def update_api_endpoint(
    endpoint_id: int,
    endpoint_update: APIEndpointUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Update a specific API endpoint.
    Only accessible by admin users.
    """
    # Get the endpoint
    db_endpoint = db.query(APIEndpoint).filter(APIEndpoint.id == endpoint_id).first()
    
    if not db_endpoint:
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Update fields if they exist in the request
    update_data = endpoint_update.dict(exclude_unset=True)
    
    # If updating path or method, check for conflicts
    if ('path' in update_data or 'method' in update_data) and not ('version_id' in update_data):
        new_path = update_data.get('path', db_endpoint.path)
        new_method = update_data.get('method', db_endpoint.method)
        
        # Check if another endpoint with the same path and method exists
        existing_endpoint = db.query(APIEndpoint).filter(
            APIEndpoint.path == new_path,
            APIEndpoint.method == new_method,
            APIEndpoint.version_id == db_endpoint.version_id,
            APIEndpoint.id != endpoint_id
        ).first()
        
        if existing_endpoint:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Endpoint {new_method} {new_path} already exists for this version"
            )
    
    # Apply updates
    for key, value in update_data.items():
        setattr(db_endpoint, key, value)
    
    # Save changes
    db.add(db_endpoint)
    db.commit()
    db.refresh(db_endpoint)
    
    return db_endpoint


@router.delete("/{endpoint_id}", response_model=Dict[str, Any])
async def delete_api_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Delete a specific API endpoint.
    Only accessible by admin users.
    """
    # Get the endpoint
    db_endpoint = db.query(APIEndpoint).filter(APIEndpoint.id == endpoint_id).first()
    
    if not db_endpoint:
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Delete the endpoint
    db.delete(db_endpoint)
    db.commit()
    
    return {"success": True, "message": "API endpoint deleted successfully"}


@router.get("/version/{version_name}", response_model=List[APIEndpointInDB])
async def get_endpoints_for_version(
    version_name: str,
    is_active: Optional[bool] = Query(True),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get all endpoints for a specific API version by name.
    """
    # Find the version first
    version = db.query(APIVersion).filter(APIVersion.version == version_name).first()
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API version '{version_name}' not found"
        )
    
    # Find all endpoints for this version
    query = db.query(APIEndpoint).filter(APIEndpoint.version_id == version.id)
    
    # Apply active filter if specified
    if is_active is not None:
        query = query.filter(APIEndpoint.is_active == is_active)
    
    # Execute query
    endpoints = query.all()
    
    return [APIEndpointInDB.from_orm(endpoint) for endpoint in endpoints]


@router.post("/{endpoint_id}/activate", response_model=APIEndpointInDB)
async def activate_api_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Activate an API endpoint.
    Only accessible by admin users.
    """
    # Get the endpoint
    db_endpoint = db.query(APIEndpoint).filter(APIEndpoint.id == endpoint_id).first()
    
    if not db_endpoint:
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Activate
    db_endpoint.is_active = True
    
    # Save changes
    db.add(db_endpoint)
    db.commit()
    db.refresh(db_endpoint)
    
    return db_endpoint


@router.post("/{endpoint_id}/deactivate", response_model=APIEndpointInDB)
async def deactivate_api_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Deactivate an API endpoint.
    Only accessible by admin users.
    """
    # Get the endpoint
    db_endpoint = db.query(APIEndpoint).filter(APIEndpoint.id == endpoint_id).first()
    
    if not db_endpoint:
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Deactivate
    db_endpoint.is_active = False
    
    # Save changes
    db.add(db_endpoint)
    db.commit()
    db.refresh(db_endpoint)
    
    return db_endpoint
