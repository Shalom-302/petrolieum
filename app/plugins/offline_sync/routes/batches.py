"""
API routes for managing sync batches.
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

from ..models.base import SyncBatchDB, SyncOperationDB, SyncStatus, SyncPriority
from ..schemas.sync_batch import (
    SyncBatchCreate,
    SyncBatchUpdate,
    SyncBatchResponse,
    SyncBatchList
)
from ..utils.sync_manager import get_sync_manager, SyncManager
from ..utils.security import sync_security

logger = logging.getLogger(__name__)


def get_batches_router() -> APIRouter:
    """Get the batches router."""
    router = APIRouter()
    
    @router.post("", response_model=SyncBatchResponse)
    async def create_sync_batch(
        batch: SyncBatchCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Create a new batch for grouping sync operations.
        
        Args:
            batch: Batch data
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Created batch
        """
        # Override the user_id with the authenticated user
        batch.user_id = current_user.id
        
        db_batch = SyncBatchDB(
            user_id=batch.user_id,
            name=batch.name,
            description=batch.description,
            priority=batch.priority
        )
        
        try:
            db.add(db_batch)
            db.commit()
            db.refresh(db_batch)
            
            # Log the activity
            logger.info(
                f"User {current_user.id} created sync batch {db_batch.id}",
                extra={"user_id": current_user.id, "batch_id": db_batch.id}
            )
            
            # Count operations (will be 0 for a new batch)
            operation_count = 0
            
            return {
                **db_batch.__dict__,
                "operation_count": operation_count
            }
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating sync batch: {str(e)}")
            raise HTTPException(status_code=500, detail="Error creating sync batch")
    
    @router.get("", response_model=SyncBatchList)
    async def list_sync_batches(
        status: Optional[SyncStatus] = None,
        priority: Optional[SyncPriority] = None,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        List sync batches.
        
        Args:
            status: Filter by status
            priority: Filter by priority
            skip: Number of records to skip
            limit: Maximum number of records to return
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            List of batches
        """
        # Initialize query for user's batches
        query = db.query(SyncBatchDB).filter(SyncBatchDB.user_id == current_user.id)
        
        # Apply filters
        if status:
            query = query.filter(SyncBatchDB.status == status)
        if priority:
            query = query.filter(SyncBatchDB.priority == priority)
            
        # Get total count
        total = query.count()
        
        # Apply pagination and sort by creation date (newest first)
        query = query.order_by(SyncBatchDB.created_at.desc()).offset(skip).limit(limit)
        
        # Execute query
        batches = query.all()
        
        # Add operation count to each batch
        result_items = []
        for batch in batches:
            # Count operations in this batch
            operation_count = db.query(SyncOperationDB).filter(
                SyncOperationDB.batch_id == batch.id
            ).count()
            
            result_items.append({
                **batch.__dict__,
                "operation_count": operation_count
            })
        
        # Log the activity
        logger.info(
            f"User {current_user.id} listed sync batches",
            extra={"user_id": current_user.id, "count": len(batches)}
        )
        
        return {
            "total": total,
            "items": result_items
        }
    
    @router.get("/{batch_id}", response_model=SyncBatchResponse)
    async def get_sync_batch(
        batch_id: str = Path(..., title="The ID of the sync batch"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Get a specific sync batch.
        
        Args:
            batch_id: Batch ID
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Batch details
        """
        batch = db.query(SyncBatchDB).filter(
            SyncBatchDB.id == batch_id,
            SyncBatchDB.user_id == current_user.id
        ).first()
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
            
        # Count operations in this batch
        operation_count = db.query(SyncOperationDB).filter(
            SyncOperationDB.batch_id == batch.id
        ).count()
        
        # Log the activity
        logger.info(
            f"User {current_user.id} viewed sync batch {batch_id}",
            extra={"user_id": current_user.id, "batch_id": batch_id}
        )
        
        return {
            **batch.__dict__,
            "operation_count": operation_count
        }
    
    @router.put("/{batch_id}", response_model=SyncBatchResponse)
    async def update_sync_batch(
        batch_update: SyncBatchUpdate,
        batch_id: str = Path(..., title="The ID of the sync batch"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Update a sync batch.
        
        Args:
            batch_update: Update data
            batch_id: Batch ID
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Updated batch
        """
        batch = db.query(SyncBatchDB).filter(
            SyncBatchDB.id == batch_id,
            SyncBatchDB.user_id == current_user.id
        ).first()
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
            
        # Only allow updates to specific fields and not if batch is in progress
        if batch.status == SyncStatus.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Cannot update a batch in progress")
            
        # Update fields if provided
        if batch_update.name is not None:
            batch.name = batch_update.name
        if batch_update.description is not None:
            batch.description = batch_update.description
        if batch_update.status is not None:
            batch.status = batch_update.status
        if batch_update.priority is not None:
            batch.priority = batch_update.priority
            
        batch.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(batch)
            
            # Count operations in this batch
            operation_count = db.query(SyncOperationDB).filter(
                SyncOperationDB.batch_id == batch.id
            ).count()
            
            # Log the activity
            logger.info(
                f"User {current_user.id} updated sync batch {batch_id}",
                extra={"user_id": current_user.id, "batch_id": batch_id}
            )
            
            return {
                **batch.__dict__,
                "operation_count": operation_count
            }
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating sync batch: {str(e)}")
            raise HTTPException(status_code=500, detail="Error updating sync batch")
    
    @router.delete("/{batch_id}", status_code=204)
    async def delete_sync_batch(
        batch_id: str = Path(..., title="The ID of the sync batch"),
        delete_operations: bool = Query(False, description="Whether to delete associated operations"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Delete a sync batch.
        
        Args:
            batch_id: Batch ID
            delete_operations: Whether to delete associated operations
            db: Database session
            current_user: Current authenticated user
        """
        batch = db.query(SyncBatchDB).filter(
            SyncBatchDB.id == batch_id,
            SyncBatchDB.user_id == current_user.id
        ).first()
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
            
        # Only allow deletion if not in progress
        if batch.status == SyncStatus.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Cannot delete a batch in progress")
            
        try:
            if delete_operations:
                # Delete all operations associated with this batch
                db.query(SyncOperationDB).filter(
                    SyncOperationDB.batch_id == batch_id
                ).delete()
            else:
                # Just remove the batch ID from operations
                operations = db.query(SyncOperationDB).filter(
                    SyncOperationDB.batch_id == batch_id
                ).all()
                
                for operation in operations:
                    operation.batch_id = None
                    
            # Delete the batch
            db.delete(batch)
            db.commit()
            
            # Log the activity
            logger.info(
                f"User {current_user.id} deleted sync batch {batch_id}",
                extra={
                    "user_id": current_user.id, 
                    "batch_id": batch_id,
                    "deleted_operations": delete_operations
                }
            )
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting sync batch: {str(e)}")
            raise HTTPException(status_code=500, detail="Error deleting sync batch")
    
    @router.post("/{batch_id}/sync", response_model=dict)
    async def sync_batch(
        batch_id: str = Path(..., title="The ID of the sync batch"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        sync_manager: SyncManager = Depends(get_sync_manager)
    ):
        """
        Manually trigger synchronization for all operations in a batch.
        
        Args:
            batch_id: Batch ID
            db: Database session
            current_user: Current authenticated user
            sync_manager: Sync manager instance
            
        Returns:
            Dict with synchronization results
        """
        batch = db.query(SyncBatchDB).filter(
            SyncBatchDB.id == batch_id,
            SyncBatchDB.user_id == current_user.id
        ).first()
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
            
        # Only allow sync if not already in progress
        if batch.status == SyncStatus.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Batch is already being synchronized")
            
        # Process the batch
        results = await sync_manager.process_batch(batch_id)
        
        # Log the activity
        logger.info(
            f"User {current_user.id} manually synchronized batch {batch_id}",
            extra={
                "user_id": current_user.id, 
                "batch_id": batch_id,
                "succeeded": results["succeeded"],
                "failed": results["failed"],
                "conflicts": results["conflicts"]
            }
        )
        
        return results
        
    return router
