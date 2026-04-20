"""
API Gateway management endpoints.

Provides routes for managing API keys, permissions, and monitoring API usage.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.advanced_auth.models import UserDB

from ..models.api_key import ApiKeyDB, ApiPermissionDB, ApiKeyCreate, ApiKeyResponse, ApiKeyWithSecret
from ..models.audit import ApiAuditLogDB, ApiAuditLogResponse, ApiAuditLogFilter
from ..routes.registry import ApiRegistry

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# API Keys management endpoints
@router.post("/keys", response_model=ApiKeyWithSecret, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    api_key_create: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Create a new API key.
    
    Note: The full API key will only be shown once upon creation.
    """
    # Security check - encryption of sensitive metadata
    if current_user.is_superuser or str(current_user.id) == api_key_create.owner_id:
        # Create a new API key
        api_key_db, plain_key = ApiKeyDB.create_key(
            name=api_key_create.name,
            owner_id=api_key_create.owner_id,
            owner_type=api_key_create.owner_type,
            expires_days=api_key_create.expires_days,
            rate_limit_per_minute=api_key_create.rate_limit_per_minute,
            rate_limit_per_day=api_key_create.rate_limit_per_day,
            allowed_ips=api_key_create.allowed_ips,
            allowed_origins=api_key_create.allowed_origins
        )
        
        db.add(api_key_db)
        
        # Add permissions
        for perm in api_key_create.permissions:
            permission = ApiPermissionDB(
                api_key_id=api_key_db.id,
                namespace=perm.get("namespace", "*"),
                resource=perm.get("resource", "*"),
                action=perm.get("action", "read")
            )
            db.add(permission)
        
        # Audit logging
        logger.info(f"API key created by user {current_user.id} for owner {api_key_create.owner_id}")
        
        # Commit changes
        db.commit()
        db.refresh(api_key_db)
        
        # Return the key with the secret (visible only at creation)
        return ApiKeyWithSecret(
            **api_key_db.__dict__,
            key=plain_key
        )
    else:
        # Audit logging
        logger.warning(f"Unauthorized attempt to create API key by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create API keys for yourself"
        )


@router.get("/keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    owner_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    List API keys with optional filters.
    
    Superusers can view all keys or filter by owner.
    Regular users can only view their own keys.
    """
    query = db.query(ApiKeyDB)
    
    # Filter by owner
    if not current_user.is_superuser:
        # Regular users can only view their own keys
        query = query.filter(ApiKeyDB.owner_id == str(current_user.id))
    elif owner_id:
        # Superusers can filter by owner
        query = query.filter(ApiKeyDB.owner_id == owner_id)
    
    # Apply additional filters
    if is_active is not None:
        query = query.filter(ApiKeyDB.is_active == is_active)
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    # Get results
    api_keys = query.all()
    
    # Audit logging
    logger.info(f"API keys listed by user {current_user.id}")
    
    return api_keys


@router.get("/keys/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Get details for a specific API key.
    
    Superusers can view any key.
    Regular users can only view their own keys.
    """
    api_key = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions
    if not current_user.is_superuser and api_key.owner_id != str(current_user.id):
        # Logging unauthorized attempts
        logger.warning(f"Unauthorized attempt to access API key {key_id} by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own API keys"
        )
    
    # Logging for audit
    logger.info(f"API key {key_id} viewed by user {current_user.id}")
    
    return api_key


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Delete an API key.
    
    Superusers can delete any key.
    Regular users can only delete their own keys.
    """
    api_key = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions
    if not current_user.is_superuser and api_key.owner_id != str(current_user.id):
        # Logging unauthorized attempts
        logger.warning(f"Unauthorized attempt to delete API key {key_id} by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own API keys"
        )
    
    # Delete key (cascades to permissions and audit logs)
    db.delete(api_key)
    db.commit()
    
    # Logging for audit
    logger.info(f"API key {key_id} deleted by user {current_user.id}")
    
    return None


@router.patch("/keys/{key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_api_key(
    key_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Revoke (deactivate) an API key.
    
    Superusers can revoke any key.
    Regular users can only revoke their own keys.
    """
    api_key = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions
    if not current_user.is_superuser and api_key.owner_id != str(current_user.id):
        # Logging unauthorized attempts
        logger.warning(f"Unauthorized attempt to revoke API key {key_id} by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revoke your own API keys"
        )
    
    # Revoke key
    api_key.is_active = False
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    # Logging for audit
    logger.info(f"API key {key_id} revoked by user {current_user.id}")
    
    return api_key


# API Key Permissions
@router.get("/keys/{key_id}/permissions", response_model=List[str])
async def get_api_key_permissions(
    key_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    Get permissions for a specific API key.
    
    Superusers can view permissions for any key.
    Regular users can only view permissions for their own keys.
    """
    api_key = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions
    if not current_user.is_superuser and api_key.owner_id != str(current_user.id):
        # Logging unauthorized attempts
        logger.warning(f"Unauthorized attempt to access API key permissions {key_id} by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view permissions for your own API keys"
        )
    
    # Get permissions
    permissions = db.query(ApiPermissionDB).filter(ApiPermissionDB.api_key_id == key_id).all()
    
    # Convert to scope strings
    scopes = [f"{perm.namespace}.{perm.resource}.{perm.action}" for perm in permissions]
    
    # Logging for audit
    logger.info(f"API key permissions for {key_id} viewed by user {current_user.id}")
    
    return scopes


# API Usage and Audit
@router.get("/audit-logs", response_model=List[ApiAuditLogResponse])
async def list_audit_logs(
    filter: ApiAuditLogFilter = Depends(),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    List API audit logs with filtering.
    
    Only superusers can access this endpoint.
    """
    if not current_user.is_superuser:
        # Logging unauthorized attempts
        logger.warning(f"Unauthorized attempt to access audit logs by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can view audit logs"
        )
    
    # Build query with filters
    query = db.query(ApiAuditLogDB)
    
    if filter.start_time:
        query = query.filter(ApiAuditLogDB.timestamp >= filter.start_time)
    
    if filter.end_time:
        query = query.filter(ApiAuditLogDB.timestamp <= filter.end_time)
    
    if filter.methods:
        query = query.filter(ApiAuditLogDB.method.in_(filter.methods))
    
    if filter.path_contains:
        query = query.filter(ApiAuditLogDB.path.like(f"%{filter.path_contains}%"))
    
    if filter.api_key_prefix:
        query = query.filter(ApiAuditLogDB.api_key_prefix == filter.api_key_prefix)
    
    if filter.client_ip:
        query = query.filter(ApiAuditLogDB.client_ip == filter.client_ip)
    
    if filter.min_status:
        query = query.filter(ApiAuditLogDB.response_status >= filter.min_status)
    
    if filter.max_status:
        query = query.filter(ApiAuditLogDB.response_status <= filter.max_status)
    
    if filter.auth_status:
        query = query.filter(ApiAuditLogDB.auth_status == filter.auth_status)
    
    if filter.threat_level:
        query = query.filter(ApiAuditLogDB.threat_level == filter.threat_level)
    
    # Sort by timestamp (newest first) and apply pagination
    query = query.order_by(ApiAuditLogDB.timestamp.desc()).offset(filter.offset).limit(filter.limit)
    
    # Execute the query
    logs = query.all()
    
    # Audit logging
    logger.info(f"Audit logs viewed by user {current_user.id}")
    
    return logs


# API Registry endpoints
@router.get("/registry", response_model=List[dict])
async def list_api_endpoints(
    namespace: Optional[str] = None,
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    List all registered API endpoints.
    
    Optionally filter by namespace.
    Only superusers can access this endpoint.
    """
    if not current_user.is_superuser:
        # Logging unauthorized attempts
        logger.warning(f"Unauthorized attempt to access API registry by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can view the API registry"
        )
    
    if namespace:
        endpoints = api_registry.get_routes_by_namespace(namespace)
    else:
        endpoints = api_registry.get_all_routes()
    
    # Convert to dict for response
    result = []
    for endpoint in endpoints:
        result.append({
            "path": endpoint.path,
            "method": endpoint.method,
            "namespace": endpoint.namespace,
            "requires": endpoint.requires,
            "rate_limit": endpoint.rate_limit,
            "version": endpoint.version,
            "deprecated": endpoint.deprecated,
            "audit_level": endpoint.audit_level,
            "description": endpoint.description,
            "tags": endpoint.tags
        })
    
    # Audit logging
    logger.info(f"API registry viewed by user {current_user.id}")
    
    return result


@router.get("/namespaces", response_model=List[str])
async def list_api_namespaces(
    current_user: UserDB = Depends(get_current_active_user)
):
    """
    List all API namespaces.
    
    Only superusers can access this endpoint.
    """
    if not current_user.is_superuser:
        # Logging unauthorized attempts
        logger.warning(f"Unauthorized attempt to access API namespaces by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can view API namespaces"
        )
    
    namespaces = api_registry.get_namespaces()
    
    # Audit logging
    logger.info(f"API namespaces viewed by user {current_user.id}")
    
    return namespaces
