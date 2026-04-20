"""
Routes for API documentation management.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.api_versioning.models import APIVersion, APIEndpoint
from app.plugins.api_versioning.schemas import VersionedAPIInfo, APIVersionInDB

router = APIRouter(prefix="/docs", tags=["API Documentation"])


@router.get("/info", response_model=VersionedAPIInfo)
async def get_api_info(
    db: Session = Depends(get_db)
):
    """
    Get information about the API, including available versions.
    This endpoint is public and does not require authentication.
    """
    from app.plugins.api_versioning.utils.version_manager import (
        get_active_versions,
        get_default_version,
        get_deprecated_versions
    )
    
    # Get all active and deprecated versions
    active_versions = get_active_versions(db)
    deprecated_versions = get_deprecated_versions(db)
    default_version = get_default_version(db)
    
    # Convert to response models
    active_versions_response = [APIVersionInDB.from_orm(v) for v in active_versions]
    deprecated_versions_response = [APIVersionInDB.from_orm(v) for v in deprecated_versions]
    
    # Create response
    response = VersionedAPIInfo(
        app_name="Kaapi API",
        description="The API for Kaapi application with versioning support",
        current_version=default_version.version if default_version else "Unknown",
        available_versions=active_versions_response,
        deprecated_versions=deprecated_versions_response
    )
    
    return response


@router.get("/versions/{version}/openapi.json")
async def get_openapi_schema(
    version: str,
    db: Session = Depends(get_db)
):
    """
    Get the OpenAPI schema for a specific API version.
    This endpoint is public and does not require authentication.
    """
    from app.plugins.api_versioning.utils.openapi_generator import generate_openapi_schema
    
    # Find the version
    db_version = db.query(APIVersion).filter(APIVersion.version == version).first()
    
    if not db_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API version '{version}' not found"
        )
    
    # Check if version is active
    if not db_version.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API version '{version}' is not active"
        )
    
    # Generate and return the OpenAPI schema
    schema = generate_openapi_schema(version, db)
    
    return JSONResponse(content=schema)


@router.get("/changelog/{from_version}/{to_version}")
async def get_version_changelog(
    from_version: str,
    to_version: str,
    db: Session = Depends(get_db)
):
    """
    Get a changelog between two API versions.
    This endpoint is public and does not require authentication.
    """
    from app.plugins.api_versioning.utils.changelog_generator import generate_changelog
    
    # Find the versions
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
    
    # Generate and return the changelog
    changelog = generate_changelog(from_version_obj.id, to_version_obj.id, db)
    
    return changelog


@router.get("/endpoints/{version}")
async def get_all_endpoints_for_version(
    version: str,
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get a list of all endpoints for a specific API version.
    This endpoint is public and does not require authentication.
    """
    # Find the version
    db_version = db.query(APIVersion).filter(APIVersion.version == version).first()
    
    if not db_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API version '{version}' not found"
        )
    
    # Check if version is active
    if not db_version.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API version '{version}' is not active"
        )
    
    # Query for endpoints
    query = db.query(APIEndpoint).filter(APIEndpoint.version_id == db_version.id)
    
    # Filter out inactive endpoints if requested
    if not include_inactive:
        query = query.filter(APIEndpoint.is_active == True)
    
    # Execute query
    endpoints = query.all()
    
    # Format response
    result = []
    for endpoint in endpoints:
        result.append({
            "path": endpoint.path,
            "method": endpoint.method,
            "is_active": endpoint.is_active,
            "handler": f"{endpoint.handler_module}.{endpoint.handler_function}"
        })
    
    return {"version": version, "endpoints": result}
