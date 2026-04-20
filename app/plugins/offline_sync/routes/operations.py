"""
API routes for managing sync operations.
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.advanced_auth.models import User

from ..models.base import SyncOperationDB, SyncStatus, SyncPriority
from ..schemas.sync_operation import (
    SyncOperationCreate,
    SyncOperationUpdate,
    SyncOperationResponse,
    SyncOperationList
)
from ..utils.sync_manager import get_sync_manager, SyncManager, start_background_sync
from ..utils.security import sync_security

logger = logging.getLogger(__name__)


def get_operations_router() -> APIRouter:
    """Get the operations router."""
    router = APIRouter()
    
    @router.post("", response_model=SyncOperationResponse)
    async def create_sync_operation(
        operation: SyncOperationCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        sync_manager: SyncManager = Depends(get_sync_manager)
    ):
        """
        Create a new sync operation.
        
        Args:
            operation: Operation data
            background_tasks: FastAPI background tasks
            db: Database session
            current_user: Current authenticated user
            sync_manager: Sync manager instance
            
        Returns:
            Created operation
        """
        # Security validation
        if not sync_security.validate_payload(operation.payload or {}, required_fields=["data"]):
            logger.warning(f"Invalid payload for sync operation: {operation.endpoint}")
            raise HTTPException(status_code=400, detail="Invalid payload")
            
        # Override the user_id with the authenticated user
        operation.user_id = current_user.id
        
        # Check if sensitive data should be encrypted
        if operation.endpoint in ["/payments", "/users", "/auth"]:
            # Mark as requiring encryption
            operation.is_encrypted = True
            # Encrypt sensitive data
            encrypted_package = sync_security.encrypt_data(operation.payload)
            operation.payload = {"encrypted": True, "package": encrypted_package}
            
        try:
            db_operation = await sync_manager.enqueue_operation(operation)
            
            # Log the operation for audit
            logger.info(
                f"User {current_user.id} created sync operation for {operation.method} {operation.endpoint}",
                extra={"user_id": current_user.id, "operation_id": db_operation.id}
            )
            
            # Start background sync if automatic mode
            if operation.priority in [SyncPriority.HIGH, SyncPriority.CRITICAL]:
                start_background_sync(background_tasks, user_id=current_user.id, limit=10)
                
            return db_operation
            
        except SQLAlchemyError as e:
            logger.error(f"Database error creating sync operation: {str(e)}")
            raise HTTPException(status_code=500, detail="Error creating sync operation")
    
    @router.get("", response_model=SyncOperationList)
    async def list_sync_operations(
        status: Optional[SyncStatus] = None,
        priority: Optional[SyncPriority] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        List sync operations.
        
        Args:
            status: Filter by status
            priority: Filter by priority
            skip: Number of records to skip
            limit: Maximum number of records to return
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            List of operations
        """
        # Initialize query for user's operations
        query = db.query(SyncOperationDB).filter(SyncOperationDB.user_id == current_user.id)
        
        # Apply filters
        if status:
            query = query.filter(SyncOperationDB.status == status)
        if priority:
            query = query.filter(SyncOperationDB.priority == priority)
            
        # Get total count
        total = query.count()
        
        # Apply pagination and sort by creation date (newest first)
        query = query.order_by(SyncOperationDB.created_at.desc()).offset(skip).limit(limit)
        
        # Execute query
        operations = query.all()
        
        # Log the activity
        logger.info(
            f"User {current_user.id} listed sync operations",
            extra={"user_id": current_user.id, "count": len(operations)}
        )
        
        return {
            "total": total,
            "items": operations
        }
    
    @router.get("/{operation_id}", response_model=SyncOperationResponse)
    async def get_sync_operation(
        operation_id: str = Path(..., title="The ID of the sync operation"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Get a specific sync operation.
        
        Args:
            operation_id: Operation ID
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Operation details
        """
        operation = db.query(SyncOperationDB).filter(
            SyncOperationDB.id == operation_id,
            SyncOperationDB.user_id == current_user.id
        ).first()
        
        if not operation:
            raise HTTPException(status_code=404, detail="Operation not found")
            
        # Decrypt payload if encrypted
        if operation.is_encrypted and operation.payload and operation.payload.get("encrypted"):
            try:
                encrypted_package = operation.payload.get("package", {})
                operation.payload = {
                    "encrypted": True,
                    "decrypted_data": sync_security.decrypt_data(encrypted_package)
                }
            except Exception as e:
                logger.error(f"Error decrypting operation payload: {str(e)}")
                # Keep the encrypted payload, don't expose error details
                
        # Log the activity
        logger.info(
            f"User {current_user.id} viewed sync operation {operation_id}",
            extra={"user_id": current_user.id, "operation_id": operation_id}
        )
        
        return operation
    
    @router.put("/{operation_id}", response_model=SyncOperationResponse)
    async def update_sync_operation(
        operation_update: SyncOperationUpdate,
        operation_id: str = Path(..., title="The ID of the sync operation"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Update a sync operation.
        
        Args:
            operation_update: Update data
            operation_id: Operation ID
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Updated operation
        """
        operation = db.query(SyncOperationDB).filter(
            SyncOperationDB.id == operation_id,
            SyncOperationDB.user_id == current_user.id
        ).first()
        
        if not operation:
            raise HTTPException(status_code=404, detail="Operation not found")
            
        # Only allow updates to specific fields and only if the operation is not in progress
        if operation.status == SyncStatus.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Cannot update an operation in progress")
            
        # Update fields if provided
        if operation_update.status is not None:
            operation.status = operation_update.status
        if operation_update.priority is not None:
            operation.priority = operation_update.priority
            
        operation.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(operation)
            
            # Log the activity
            logger.info(
                f"User {current_user.id} updated sync operation {operation_id}",
                extra={"user_id": current_user.id, "operation_id": operation_id}
            )
            
            return operation
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating sync operation: {str(e)}")
            raise HTTPException(status_code=500, detail="Error updating sync operation")
    
    @router.delete("/{operation_id}", status_code=204)
    async def delete_sync_operation(
        operation_id: str = Path(..., title="The ID of the sync operation"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Delete a sync operation.
        
        Args:
            operation_id: Operation ID
            db: Database session
            current_user: Current authenticated user
        """
        operation = db.query(SyncOperationDB).filter(
            SyncOperationDB.id == operation_id,
            SyncOperationDB.user_id == current_user.id
        ).first()
        
        if not operation:
            raise HTTPException(status_code=404, detail="Operation not found")
            
        # Only allow deletion if not in progress
        if operation.status == SyncStatus.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Cannot delete an operation in progress")
            
        try:
            db.delete(operation)
            db.commit()
            
            # Log the activity
            logger.info(
                f"User {current_user.id} deleted sync operation {operation_id}",
                extra={"user_id": current_user.id, "operation_id": operation_id}
            )
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting sync operation: {str(e)}")
            raise HTTPException(status_code=500, detail="Error deleting sync operation")
            
    @router.post("/{operation_id}/sync", response_model=SyncOperationResponse)
    async def sync_operation(
        operation_id: str = Path(..., title="The ID of the sync operation"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        sync_manager: SyncManager = Depends(get_sync_manager)
    ):
        """
        Manually trigger synchronization for an operation.
        
        Args:
            operation_id: Operation ID
            db: Database session
            current_user: Current authenticated user
            sync_manager: Sync manager instance
            
        Returns:
            Updated operation
        """
        operation = db.query(SyncOperationDB).filter(
            SyncOperationDB.id == operation_id,
            SyncOperationDB.user_id == current_user.id
        ).first()
        
        if not operation:
            raise HTTPException(status_code=404, detail="Operation not found")
            
        # Only allow sync if not already in progress
        if operation.status == SyncStatus.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Operation is already in progress")
            
        # Process the operation
        success, error = await sync_manager.process_operation(operation_id)
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail=f"Synchronization failed: {error or 'Unknown error'}"
            )
            
        # Get the updated operation
        operation = db.query(SyncOperationDB).filter(SyncOperationDB.id == operation_id).first()
        
        # Log the activity
        logger.info(
            f"User {current_user.id} manually synchronized operation {operation_id}",
            extra={"user_id": current_user.id, "operation_id": operation_id}
        )
        
        return operation
    
    return router
