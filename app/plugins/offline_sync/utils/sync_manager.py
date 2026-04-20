"""
Utilities for managing synchronization operations.
"""

import logging
import json
import httpx
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks, Depends

from app.core.security import get_current_active_user
from app.core.db import get_db
from ..models.base import SyncOperationDB, SyncBatchDB, SyncStatus, SyncPriority
from ..schemas.sync_operation import SyncOperationCreate, SyncOperationUpdate

logger = logging.getLogger(__name__)


class SyncManager:
    """Manager class for handling synchronization operations."""
    
    def __init__(self, db_session: Session, base_url: str):
        """
        Initialize the sync manager.
        
        Args:
            db_session: Database session
            base_url: Base URL for API requests
        """
        self.db = db_session
        self.base_url = base_url
        
    async def enqueue_operation(self, operation: SyncOperationCreate) -> SyncOperationDB:
        """
        Add a new operation to the synchronization queue.
        
        Args:
            operation: Operation to enqueue
            
        Returns:
            Created sync operation
        """
        db_operation = SyncOperationDB(
            user_id=operation.user_id,
            endpoint=operation.endpoint,
            method=operation.method,
            payload=operation.payload,
            headers=operation.headers,
            query_params=operation.query_params,
            priority=operation.priority,
            max_retries=operation.max_retries,
            batch_id=operation.batch_id,
            is_encrypted=operation.is_encrypted,
            encryption_metadata=operation.encryption_metadata
        )
        
        self.db.add(db_operation)
        self.db.commit()
        self.db.refresh(db_operation)
        
        logger.info(f"Enqueued operation {db_operation.id} for endpoint {operation.endpoint}")
        return db_operation
        
    async def process_operation(self, operation_id: str) -> Tuple[bool, Optional[str]]:
        """
        Process a single operation by executing it against the API.
        
        Args:
            operation_id: ID of the operation to process
            
        Returns:
            Tuple of (success, error_message)
        """
        operation = self.db.query(SyncOperationDB).filter(SyncOperationDB.id == operation_id).first()
        if not operation:
            logger.error(f"Operation {operation_id} not found")
            return False, "Operation not found"
            
        # Update status to in progress
        operation.status = SyncStatus.IN_PROGRESS
        operation.updated_at = datetime.utcnow()
        self.db.commit()
        
        try:
            # Build request URL
            url = f"{self.base_url}{operation.endpoint}"
            
            # Prepare request details
            method = operation.method.lower()
            headers = operation.headers or {}
            params = operation.query_params or {}
            data = operation.payload
            
            async with httpx.AsyncClient() as client:
                response = await getattr(client, method)(
                    url,
                    headers=headers,
                    params=params,
                    json=data if method in ['post', 'put', 'patch'] else None
                )
                
                # Update operation with response
                operation.response_status = response.status_code
                operation.response_data = response.json() if response.headers.get("content-type") == "application/json" else {"text": response.text}
                
                # Check if successful
                if 200 <= response.status_code < 300:
                    operation.status = SyncStatus.SUCCEEDED
                    self.db.commit()
                    logger.info(f"Successfully processed operation {operation_id}")
                    return True, None
                else:
                    # Handle conflicts specially
                    if response.status_code == 409:
                        operation.status = SyncStatus.CONFLICT
                    else:
                        operation.status = SyncStatus.FAILED
                        
                    operation.last_error = f"API returned status {response.status_code}: {response.text}"
                    operation.retry_count += 1
                    self.db.commit()
                    
                    logger.warning(f"Failed to process operation {operation_id}: {operation.last_error}")
                    return False, operation.last_error
                    
        except Exception as e:
            operation.status = SyncStatus.FAILED
            operation.last_error = str(e)
            operation.retry_count += 1
            self.db.commit()
            
            logger.error(f"Error processing operation {operation_id}: {str(e)}")
            return False, str(e)
            
    async def process_batch(self, batch_id: str) -> Dict[str, Any]:
        """
        Process all operations in a batch.
        
        Args:
            batch_id: ID of the batch to process
            
        Returns:
            Dict with processing results
        """
        batch = self.db.query(SyncBatchDB).filter(SyncBatchDB.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
            
        # Update batch status
        batch.status = SyncStatus.IN_PROGRESS
        batch.updated_at = datetime.utcnow()
        self.db.commit()
        
        operations = self.db.query(SyncOperationDB).filter(
            SyncOperationDB.batch_id == batch_id,
            SyncOperationDB.status.in_([SyncStatus.PENDING, SyncStatus.FAILED])
        ).all()
        
        results = {
            "total": len(operations),
            "succeeded": 0,
            "failed": 0,
            "conflicts": 0,
            "errors": []
        }
        
        for operation in operations:
            success, error = await self.process_operation(operation.id)
            if success:
                results["succeeded"] += 1
            else:
                if operation.status == SyncStatus.CONFLICT:
                    results["conflicts"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "operation_id": operation.id,
                        "endpoint": operation.endpoint,
                        "error": error
                    })
        
        # Update batch status based on results
        if results["failed"] == 0 and results["conflicts"] == 0:
            batch.status = SyncStatus.SUCCEEDED
        elif results["conflicts"] > 0:
            batch.status = SyncStatus.CONFLICT
        else:
            batch.status = SyncStatus.FAILED
            
        batch.updated_at = datetime.utcnow()
        self.db.commit()
        
        return results
        
    async def process_pending_operations(
        self, 
        user_id: Optional[str] = None,
        limit: int = 50,
        prioritize: bool = True
    ) -> Dict[str, Any]:
        """
        Process pending operations from the queue.
        
        Args:
            user_id: Optional user ID to filter operations
            limit: Maximum number of operations to process
            prioritize: Whether to prioritize operations by priority
            
        Returns:
            Dict with processing results
        """
        query = self.db.query(SyncOperationDB).filter(
            SyncOperationDB.status.in_([SyncStatus.PENDING, SyncStatus.FAILED]),
            SyncOperationDB.retry_count < SyncOperationDB.max_retries
        )
        
        if user_id:
            query = query.filter(SyncOperationDB.user_id == user_id)
            
        if prioritize:
            # Order by priority (critical -> high -> normal -> low) and then by created_at
            query = query.order_by(
                # Custom ordering for priority
                # This ensures CRITICAL > HIGH > NORMAL > LOW
                # Using case/when statement to ensure correct ordering
                # SQLAlchemy doesn't support direct Enum comparison in all databases
                # so we map them to numerical values
                (
                    SyncOperationDB.priority == SyncPriority.CRITICAL.value
                ).desc(),
                (
                    SyncOperationDB.priority == SyncPriority.HIGH.value
                ).desc(),
                (
                    SyncOperationDB.priority == SyncPriority.NORMAL.value
                ).desc(),
                SyncOperationDB.created_at
            )
        else:
            query = query.order_by(SyncOperationDB.created_at)
            
        operations = query.limit(limit).all()
        
        results = {
            "total": len(operations),
            "succeeded": 0,
            "failed": 0,
            "conflicts": 0,
            "errors": []
        }
        
        for operation in operations:
            success, error = await self.process_operation(operation.id)
            if success:
                results["succeeded"] += 1
            else:
                if operation.status == SyncStatus.CONFLICT:
                    results["conflicts"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "operation_id": operation.id,
                        "endpoint": operation.endpoint,
                        "error": error
                    })
                    
        return results


async def get_sync_manager(db: Session = Depends(get_db)):
    """Dependency to get a sync manager instance."""
    # In a real implementation, base_url would likely come from configuration
    return SyncManager(db_session=db, base_url="http://localhost:8000")
    
    
def start_background_sync(
    background_tasks: BackgroundTasks,
    user_id: Optional[str] = None,
    limit: int = 50
):
    """
    Start background synchronization of pending operations.
    
    Args:
        background_tasks: FastAPI background tasks
        user_id: Optional user ID to filter operations
        limit: Maximum number of operations to process
    """
    async def _run_sync():
        db = next(get_db())
        manager = SyncManager(db_session=db, base_url="http://localhost:8000")
        await manager.process_pending_operations(user_id=user_id, limit=limit)
        
    background_tasks.add_task(_run_sync)
