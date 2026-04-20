"""
Main module for the offline synchronization plugin.

This plugin provides functionality for queuing operations when offline
and synchronizing them when connectivity is restored.
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, APIRouter, Depends, BackgroundTasks

from app.core.config import settings

from .routes import get_operations_router, get_batches_router, get_config_router
from .utils.sync_manager import start_background_sync
from .models.base import SyncStatus, SyncPriority

logger = logging.getLogger(__name__)


class OfflineSyncPlugin:
    """
    Plugin for offline synchronization capabilities.
    
    This plugin allows for operations to be queued when offline
    and synchronized later when connectivity is restored.
    """
    
    def __init__(self) -> None:
        """Initialize the offline sync plugin."""
        self.name = "offline_sync"
        self.description = "Offline operation queuing and synchronization"
        self.version = "0.1.0"
        self.dependencies = ["api_gateway"]
        self.router = APIRouter(prefix="/sync", tags=["Synchronization"])
        
    async def on_startup(self, app: FastAPI) -> None:
        """
        Execute startup tasks for the plugin.
        
        Args:
            app: The FastAPI application
        """
        logger.info("Starting Offline Sync Plugin")
        
        # Register routes
        self._register_routes()
        
        # Set up scheduled tasks for automatic synchronization
        # In a real implementation, this would set up background tasks
        # that run periodically to check and process pending operations
        
        # Initialize security for the plugin
        from .utils.security import sync_security
        logger.info("Initialized security for Offline Sync Plugin")
        
    async def on_shutdown(self, app: FastAPI) -> None:
        """
        Execute shutdown tasks for the plugin.
        
        Args:
            app: The FastAPI application
        """
        logger.info("Shutting down Offline Sync Plugin")
        
    def _register_routes(self) -> None:
        """Register routes for the plugin."""
        # Add operations routes
        operations_router = get_operations_router()
        self.router.include_router(
            operations_router,
            prefix="/operations",
            tags=["Sync Operations"]
        )
        
        # Add batches routes
        batches_router = get_batches_router()
        self.router.include_router(
            batches_router,
            prefix="/batches",
            tags=["Sync Batches"]
        )
        
        # Add config routes
        config_router = get_config_router()
        self.router.include_router(
            config_router,
            prefix="/config",
            tags=["Sync Configuration"]
        )
        
        logger.info("Registered routes for Offline Sync Plugin")
        
    def expose_functions(self) -> Dict[str, Any]:
        """
        Expose functions to be used by other plugins.
        
        Returns:
            Dict of functions exposed by this plugin
        """
        return {
            "enqueue_operation": self.enqueue_operation,
            "get_sync_statuses": self.get_sync_statuses,
            "get_sync_priorities": self.get_sync_priorities,
            "trigger_sync": self.trigger_sync
        }
        
    async def enqueue_operation(
        self,
        endpoint: str,
        method: str,
        payload: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        priority: Optional[str] = None,
        batch_id: Optional[str] = None,
        is_encrypted: bool = False,
        encryption_metadata: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Enqueue an operation for later synchronization.
        
        This method is intended to be called by other plugins or components
        to add operations to the synchronization queue.
        
        Args:
            endpoint: API endpoint for the operation
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            payload: Optional request payload
            user_id: User ID associated with the operation
            priority: Priority level (CRITICAL, HIGH, NORMAL, LOW)
            batch_id: Optional batch ID to group related operations
            is_encrypted: Whether the payload should be encrypted
            encryption_metadata: Additional metadata for encryption
            headers: Optional request headers
            query_params: Optional query parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict with created operation details
        """
        # This is just a placeholder implementation
        # In a real implementation, this would use the SyncManager to enqueue the operation
        from .utils.sync_manager import get_sync_manager
        from .schemas.sync_operation import SyncOperationCreate
        
        # Initialize sync manager
        db = next(get_db())
        sync_manager = SyncManager(db_session=db, base_url="http://localhost:8000")
        
        # Validate and set priority
        if priority and priority.upper() in [p.name for p in SyncPriority]:
            sync_priority = SyncPriority[priority.upper()]
        else:
            sync_priority = SyncPriority.NORMAL
        
        # Create operation
        operation = SyncOperationCreate(
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            payload=payload,
            headers=headers,
            query_params=query_params,
            priority=sync_priority,
            max_retries=max_retries,
            batch_id=batch_id,
            is_encrypted=is_encrypted,
            encryption_metadata=encryption_metadata
        )
        
        # Enqueue the operation
        created_operation = await sync_manager.enqueue_operation(operation)
        
        return {
            "id": created_operation.id,
            "status": created_operation.status.value,
            "created_at": created_operation.created_at.isoformat(),
        }
        
    def get_sync_statuses(self) -> List[str]:
        """
        Get list of possible synchronization statuses.
        
        Returns:
            List of status strings
        """
        return [status.value for status in SyncStatus]
        
    def get_sync_priorities(self) -> List[str]:
        """
        Get list of possible synchronization priorities.
        
        Returns:
            List of priority strings
        """
        return [priority.value for priority in SyncPriority]
        
    async def trigger_sync(
        self,
        background_tasks: BackgroundTasks,
        user_id: Optional[str] = None,
        limit: int = 50,
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger synchronization process.
        
        Args:
            background_tasks: FastAPI background tasks
            user_id: Optional user ID to filter operations
            limit: Maximum number of operations to process
            batch_id: Optional batch ID to process
            
        Returns:
            Dict with processing information
        """
        # Start background synchronization
        start_background_sync(
            background_tasks=background_tasks,
            user_id=user_id,
            limit=limit
        )
        
        return {
            "message": "Synchronization started",
            "user_id": user_id,
            "limit": limit,
            "batch_id": batch_id
        }
        

# Initialize the plugin
plugin = OfflineSyncPlugin()


async def get_db():
    """Database session dependency placeholder."""
    # This is a placeholder - in the actual application, this would be imported from app.core.db
    from app.core.db import get_db as app_get_db
    return app_get_db


def get_router() -> APIRouter:
    """
    Get the main API router for the plugin.
    
    Returns:
        FastAPI router
    """
    return plugin.router


def initialize_plugin(app: FastAPI) -> None:
    """
    Initialize the plugin.
    
    Args:
        app: FastAPI application
    """
    plugin.on_startup(app)
    
    
def get_plugin_info() -> Dict[str, Any]:
    """
    Get information about the plugin.
    
    Returns:
        Dict with plugin information
    """
    return {
        "name": plugin.name,
        "description": plugin.description,
        "version": plugin.version,
        "dependencies": plugin.dependencies
    }

offline_sync_router = get_router()