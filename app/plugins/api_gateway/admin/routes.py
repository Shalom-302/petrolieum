"""
Admin routes for the API Gateway plugin.

Provides administrative endpoints for managing API keys, viewing audit logs,
and configuring the API Gateway.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from functools import wraps

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..models.api_key import ApiKeyDB
from ..models.audit import ApiAuditLogDB
from ..models.rate_limit import RateLimitDB
from ..config import ApiGatewayConfig
from ..schemas.admin import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyList,
    ApiKeyUpdate,
    ApiAuditLogResponse,
    ApiAuditLogList,
    RateLimitResponse,
    RateLimitList
)
from app.core.db import get_db
from app.core.security import get_current_active_admin_user

# Setup logging
logger = logging.getLogger(__name__)


def get_admin_router(config: ApiGatewayConfig) -> APIRouter:
    """
    Create and return the admin router for the API Gateway plugin.
    
    Args:
        config: API Gateway configuration
        
    Returns:
        APIRouter: Admin router for the API Gateway plugin
    """
    router = APIRouter()
    
    # Create a custom admin dependency that combines admin user check with permissions
    def require_admin_with_permissions():
        """
        Dependency for requiring an admin user with the configured permissions.
        This combines the standard admin user check with any plugin-specific permission requirements.
        """
        async def verify_admin(current_user = Depends(get_current_active_admin_user)):
            # Here we could check additional plugin-specific permissions if needed
            # For example, if we wanted to use casbin or another permission system
            # to check specific permissions defined in config.admin_permissions
            
            # For now, the standard admin check is sufficient
            return current_user
            
        return Depends(verify_admin)
    
    # API Keys management endpoints
    
    @router.post("/keys", response_model=ApiKeyResponse)
    async def create_api_key(
        api_key_data: ApiKeyCreate,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        Create a new API key.
        
        Admin only endpoint for creating API keys with specific permissions and rate limits.
        """
        try:
            # Calculate expiry date if provided
            expiry_date = None
            if api_key_data.expires_in_days:
                expiry_date = datetime.utcnow() + timedelta(days=api_key_data.expires_in_days)
            elif api_key_data.expiry_date:
                expiry_date = api_key_data.expiry_date
            else:
                # Use default expiry from config
                expiry_date = datetime.utcnow() + timedelta(days=config.default_key_expiry_days)
            
            # Create the API key
            api_key, plain_key = ApiKeyDB.create_key(
                db=db,
                name=api_key_data.name,
                permissions=api_key_data.permissions,
                rate_limit=api_key_data.rate_limit or config.default_rate_limit,
                expires_at=expiry_date,
                created_by=current_user.id if current_user else None,
                ip_whitelist=api_key_data.ip_whitelist,
                origin_whitelist=api_key_data.origin_whitelist,
                metadata=api_key_data.metadata
            )
            
            # Commit to save the API key
            db.commit()
            
            # Create response with plain key (only shown once)
            response = ApiKeyResponse(
                id=api_key.id,
                name=api_key.name,
                key=plain_key,  # Plain key is only returned upon creation
                permissions=api_key.permissions,
                rate_limit=api_key.rate_limit,
                created_at=api_key.created_at,
                expires_at=api_key.expires_at,
                created_by=api_key.created_by,
                ip_whitelist=api_key.ip_whitelist,
                origin_whitelist=api_key.origin_whitelist,
                metadata=api_key.metadata,
                is_active=api_key.is_active
            )
            
            logger.info(f"API key created: {api_key.id} (name: {api_key.name})")
            return response
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating API key: {e}")
            raise HTTPException(status_code=500, detail="Database error creating API key")
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/keys", response_model=ApiKeyList)
    async def list_api_keys(
        skip: int = 0,
        limit: int = 100,
        name: Optional[str] = None,
        is_active: Optional[bool] = None,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        List all API keys with optional filtering.
        
        Admin only endpoint for listing and filtering API keys.
        """
        try:
            # Query API keys with optional filters
            query = db.query(ApiKeyDB)
            
            if name:
                query = query.filter(ApiKeyDB.name.ilike(f"%{name}%"))
            
            if is_active is not None:
                query = query.filter(ApiKeyDB.is_active == is_active)
            
            # Count total
            total = query.count()
            
            # Apply pagination
            api_keys = query.order_by(ApiKeyDB.created_at.desc()).offset(skip).limit(limit).all()
            
            # Convert to API response models (without plain key)
            items = [
                ApiKeyResponse(
                    id=key.id,
                    name=key.name,
                    key=None,  # Plain key is never returned on list operations
                    permissions=key.permissions,
                    rate_limit=key.rate_limit,
                    created_at=key.created_at,
                    expires_at=key.expires_at,
                    created_by=key.created_by,
                    ip_whitelist=key.ip_whitelist,
                    origin_whitelist=key.origin_whitelist,
                    metadata=key.metadata,
                    is_active=key.is_active
                )
                for key in api_keys
            ]
            
            return ApiKeyList(items=items, total=total)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error listing API keys: {e}")
            raise HTTPException(status_code=500, detail="Database error listing API keys")
        except Exception as e:
            logger.error(f"Error listing API keys: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/keys/{key_id}", response_model=ApiKeyResponse)
    async def get_api_key(
        key_id: str,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        Get details of a specific API key.
        
        Admin only endpoint for retrieving detailed information about an API key.
        """
        try:
            # Query the API key
            api_key = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
            
            if not api_key:
                raise HTTPException(status_code=404, detail="API key not found")
            
            # Convert to API response model (without plain key)
            return ApiKeyResponse(
                id=api_key.id,
                name=api_key.name,
                key=None,  # Plain key is never returned on get operations
                permissions=api_key.permissions,
                rate_limit=api_key.rate_limit,
                created_at=api_key.created_at,
                expires_at=api_key.expires_at,
                created_by=api_key.created_by,
                ip_whitelist=api_key.ip_whitelist,
                origin_whitelist=api_key.origin_whitelist,
                metadata=api_key.metadata,
                is_active=api_key.is_active
            )
            
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error getting API key: {e}")
            raise HTTPException(status_code=500, detail="Database error getting API key")
        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/keys/{key_id}", response_model=ApiKeyResponse)
    async def update_api_key(
        key_id: str,
        api_key_update: ApiKeyUpdate,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        Update an existing API key.
        
        Admin only endpoint for updating API key details, permissions, and rate limits.
        """
        try:
            # Query the API key
            api_key = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
            
            if not api_key:
                raise HTTPException(status_code=404, detail="API key not found")
            
            # Update fields
            if api_key_update.name is not None:
                api_key.name = api_key_update.name
            
            if api_key_update.permissions is not None:
                api_key.permissions = api_key_update.permissions
            
            if api_key_update.rate_limit is not None:
                api_key.rate_limit = api_key_update.rate_limit
            
            if api_key_update.is_active is not None:
                api_key.is_active = api_key_update.is_active
            
            if api_key_update.ip_whitelist is not None:
                api_key.ip_whitelist = api_key_update.ip_whitelist
            
            if api_key_update.origin_whitelist is not None:
                api_key.origin_whitelist = api_key_update.origin_whitelist
            
            if api_key_update.metadata is not None:
                api_key.metadata = api_key_update.metadata
            
            # Update expiry date if provided
            if api_key_update.expires_in_days is not None:
                api_key.expires_at = datetime.utcnow() + timedelta(days=api_key_update.expires_in_days)
            elif api_key_update.expiry_date is not None:
                api_key.expires_at = api_key_update.expiry_date
            
            # Commit the updates
            db.commit()
            db.refresh(api_key)
            
            logger.info(f"API key updated: {api_key.id} (name: {api_key.name})")
            
            # Convert to API response model (without plain key)
            return ApiKeyResponse(
                id=api_key.id,
                name=api_key.name,
                key=None,  # Plain key is never returned on update operations
                permissions=api_key.permissions,
                rate_limit=api_key.rate_limit,
                created_at=api_key.created_at,
                expires_at=api_key.expires_at,
                created_by=api_key.created_by,
                ip_whitelist=api_key.ip_whitelist,
                origin_whitelist=api_key.origin_whitelist,
                metadata=api_key.metadata,
                is_active=api_key.is_active
            )
            
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating API key: {e}")
            raise HTTPException(status_code=500, detail="Database error updating API key")
        except Exception as e:
            logger.error(f"Error updating API key: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/keys/{key_id}")
    async def delete_api_key(
        key_id: str,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        Delete an API key.
        
        Admin only endpoint for permanently deleting an API key.
        """
        try:
            # Query the API key
            api_key = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
            
            if not api_key:
                raise HTTPException(status_code=404, detail="API key not found")
            
            # Delete the API key
            db.delete(api_key)
            db.commit()
            
            logger.info(f"API key deleted: {key_id}")
            
            return {"message": "API key deleted successfully"}
            
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting API key: {e}")
            raise HTTPException(status_code=500, detail="Database error deleting API key")
        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/keys/{key_id}/regenerate", response_model=ApiKeyResponse)
    async def regenerate_api_key(
        key_id: str,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        Regenerate an API key while preserving its settings.
        
        Admin only endpoint for regenerating an API key with new credentials but the same settings.
        """
        try:
            # Query the API key
            api_key = db.query(ApiKeyDB).filter(ApiKeyDB.id == key_id).first()
            
            if not api_key:
                raise HTTPException(status_code=404, detail="API key not found")
            
            # Regenerate the key
            plain_key = api_key.regenerate_key(db)
            
            # Commit the updates
            db.commit()
            db.refresh(api_key)
            
            logger.info(f"API key regenerated: {api_key.id} (name: {api_key.name})")
            
            # Convert to API response model with the new plain key
            return ApiKeyResponse(
                id=api_key.id,
                name=api_key.name,
                key=plain_key,  # Return the new plain key
                permissions=api_key.permissions,
                rate_limit=api_key.rate_limit,
                created_at=api_key.created_at,
                expires_at=api_key.expires_at,
                created_by=api_key.created_by,
                ip_whitelist=api_key.ip_whitelist,
                origin_whitelist=api_key.origin_whitelist,
                metadata=api_key.metadata,
                is_active=api_key.is_active
            )
            
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error regenerating API key: {e}")
            raise HTTPException(status_code=500, detail="Database error regenerating API key")
        except Exception as e:
            logger.error(f"Error regenerating API key: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # API Audit Logs endpoints
    
    @router.get("/audit-logs", response_model=ApiAuditLogList)
    async def list_audit_logs(
        skip: int = 0,
        limit: int = 100,
        api_key_id: Optional[str] = None,
        path: Optional[str] = None,
        status_code_min: Optional[int] = None,
        status_code_max: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        List API audit logs with optional filtering.
        
        Admin only endpoint for viewing and filtering API request audit logs.
        """
        try:
            # Query audit logs with optional filters
            query = db.query(ApiAuditLogDB)
            
            if api_key_id:
                query = query.filter(ApiAuditLogDB.api_key_id == api_key_id)
            
            if path:
                query = query.filter(ApiAuditLogDB.path.like(f"%{path}%"))
            
            if status_code_min:
                query = query.filter(ApiAuditLogDB.status_code >= status_code_min)
            
            if status_code_max:
                query = query.filter(ApiAuditLogDB.status_code <= status_code_max)
            
            if start_time:
                query = query.filter(ApiAuditLogDB.timestamp >= start_time)
            
            if end_time:
                query = query.filter(ApiAuditLogDB.timestamp <= end_time)
            
            # Count total
            total = query.count()
            
            # Apply pagination
            audit_logs = query.order_by(ApiAuditLogDB.timestamp.desc()).offset(skip).limit(limit).all()
            
            # Convert to API response models
            items = [
                ApiAuditLogResponse(
                    id=log.id,
                    api_key_id=log.api_key_id,
                    method=log.method,
                    path=log.path,
                    query_params=log.query_params,
                    ip_address=log.ip_address,
                    user_agent=log.user_agent,
                    request_headers=log.request_headers,
                    request_body=log.request_body,
                    status_code=log.status_code,
                    response_body=log.response_body,
                    response_time_ms=log.response_time_ms,
                    timestamp=log.timestamp,
                    error=log.error
                )
                for log in audit_logs
            ]
            
            return ApiAuditLogList(items=items, total=total)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error listing audit logs: {e}")
            raise HTTPException(status_code=500, detail="Database error listing audit logs")
        except Exception as e:
            logger.error(f"Error listing audit logs: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/audit-logs/{log_id}", response_model=ApiAuditLogResponse)
    async def get_audit_log(
        log_id: str,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        Get details of a specific audit log entry.
        
        Admin only endpoint for viewing detailed information about an API request audit log.
        """
        try:
            # Query the audit log
            audit_log = db.query(ApiAuditLogDB).filter(ApiAuditLogDB.id == log_id).first()
            
            if not audit_log:
                raise HTTPException(status_code=404, detail="Audit log not found")
            
            # Convert to API response model
            return ApiAuditLogResponse(
                id=audit_log.id,
                api_key_id=audit_log.api_key_id,
                method=audit_log.method,
                path=audit_log.path,
                query_params=audit_log.query_params,
                ip_address=audit_log.ip_address,
                user_agent=audit_log.user_agent,
                request_headers=audit_log.request_headers,
                request_body=audit_log.request_body,
                status_code=audit_log.status_code,
                response_body=audit_log.response_body,
                response_time_ms=audit_log.response_time_ms,
                timestamp=audit_log.timestamp,
                error=audit_log.error
            )
            
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error getting audit log: {e}")
            raise HTTPException(status_code=500, detail="Database error getting audit log")
        except Exception as e:
            logger.error(f"Error getting audit log: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Rate Limits monitoring endpoints
    
    @router.get("/rate-limits", response_model=RateLimitList)
    async def list_rate_limits(
        skip: int = 0,
        limit: int = 100,
        api_key_id: Optional[str] = None,
        window_key: Optional[str] = None,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        List active rate limits with optional filtering.
        
        Admin only endpoint for monitoring rate limit usage across API keys.
        """
        try:
            # Query rate limits with optional filters
            query = db.query(RateLimitDB)
            
            if api_key_id:
                query = query.filter(RateLimitDB.api_key_id == api_key_id)
            
            if window_key:
                query = query.filter(RateLimitDB.window_key.like(f"%{window_key}%"))
            
            # Count total
            total = query.count()
            
            # Apply pagination
            rate_limits = query.order_by(RateLimitDB.last_request.desc()).offset(skip).limit(limit).all()
            
            # Convert to API response models
            items = [
                RateLimitResponse(
                    id=limit_obj.id,
                    api_key_id=limit_obj.api_key_id,
                    window_key=limit_obj.window_key,
                    window_size_seconds=limit_obj.window_size_seconds,
                    max_requests=limit_obj.max_requests,
                    current_requests=limit_obj.current_requests,
                    last_request=limit_obj.last_request,
                    window_expires=limit_obj.window_expires
                )
                for limit_obj in rate_limits
            ]
            
            return RateLimitList(items=items, total=total)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error listing rate limits: {e}")
            raise HTTPException(status_code=500, detail="Database error listing rate limits")
        except Exception as e:
            logger.error(f"Error listing rate limits: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/rate-limits/{limit_id}")
    async def reset_rate_limit(
        limit_id: str,
        db: Session = Depends(get_db),
        current_user = Depends(require_admin_with_permissions)
    ):
        """
        Reset a specific rate limit.
        
        Admin only endpoint for resetting a rate limit counter.
        """
        try:
            # Query the rate limit
            rate_limit = db.query(RateLimitDB).filter(RateLimitDB.id == limit_id).first()
            
            if not rate_limit:
                raise HTTPException(status_code=404, detail="Rate limit not found")
            
            # Reset the rate limit
            rate_limit.current_requests = 0
            db.commit()
            
            logger.info(f"Rate limit reset: {limit_id}")
            
            return {"message": "Rate limit reset successfully"}
            
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error resetting rate limit: {e}")
            raise HTTPException(status_code=500, detail="Database error resetting rate limit")
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router
