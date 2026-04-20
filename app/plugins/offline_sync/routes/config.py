"""
API routes for managing user sync configurations.
"""

import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.advanced_auth.models import User

from ..models.base import SyncConfigDB
from ..schemas.sync_config import (
    SyncConfigCreate,
    SyncConfigUpdate,
    SyncConfigResponse
)
from ..utils.security import sync_security

logger = logging.getLogger(__name__)


def get_config_router() -> APIRouter:
    """Get the config router."""
    router = APIRouter()
    
    @router.post("", response_model=SyncConfigResponse)
    async def create_sync_config(
        config: SyncConfigCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Create or update user's sync configuration.
        
        Args:
            config: Configuration data
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Created/updated configuration
        """
        # Override the user_id with the authenticated user
        config.user_id = current_user.id
        
        # Check if config already exists for this user
        existing_config = db.query(SyncConfigDB).filter(
            SyncConfigDB.user_id == current_user.id
        ).first()
        
        if existing_config:
            # Update existing config
            existing_config.auto_sync_enabled = config.auto_sync_enabled
            existing_config.sync_on_connectivity = config.sync_on_connectivity
            existing_config.sync_interval_minutes = config.sync_interval_minutes
            existing_config.max_offline_storage_mb = config.max_offline_storage_mb
            existing_config.conflict_resolution_strategy = config.conflict_resolution_strategy
            existing_config.prioritize_by_endpoint = config.prioritize_by_endpoint
            existing_config.updated_at = datetime.utcnow()
            
            db_config = existing_config
            
            action = "updated"
        else:
            # Create new config
            db_config = SyncConfigDB(
                user_id=config.user_id,
                auto_sync_enabled=config.auto_sync_enabled,
                sync_on_connectivity=config.sync_on_connectivity,
                sync_interval_minutes=config.sync_interval_minutes,
                max_offline_storage_mb=config.max_offline_storage_mb,
                conflict_resolution_strategy=config.conflict_resolution_strategy,
                prioritize_by_endpoint=config.prioritize_by_endpoint
            )
            
            db.add(db_config)
            action = "created"
        
        try:
            db.commit()
            db.refresh(db_config)
            
            # Log the activity
            logger.info(
                f"User {current_user.id} {action} sync configuration",
                extra={"user_id": current_user.id, "config_id": db_config.id}
            )
            
            return db_config
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error saving sync configuration: {str(e)}")
            raise HTTPException(status_code=500, detail="Error saving sync configuration")
    
    @router.get("", response_model=SyncConfigResponse)
    async def get_sync_config(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Get user's sync configuration.
        
        Args:
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            User's configuration
        """
        config = db.query(SyncConfigDB).filter(
            SyncConfigDB.user_id == current_user.id
        ).first()
        
        if not config:
            # Return default configuration
            return SyncConfigDB(
                id="default",
                user_id=current_user.id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                auto_sync_enabled=True,
                sync_on_connectivity=True,
                sync_interval_minutes=15,
                max_offline_storage_mb=100,
                conflict_resolution_strategy="server_wins",
                prioritize_by_endpoint=None
            )
            
        # Log the activity
        logger.info(
            f"User {current_user.id} viewed sync configuration",
            extra={"user_id": current_user.id, "config_id": config.id}
        )
        
        return config
    
    @router.put("", response_model=SyncConfigResponse)
    async def update_sync_config(
        config_update: SyncConfigUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
    ):
        """
        Update user's sync configuration.
        
        Args:
            config_update: Update data
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Updated configuration
        """
        config = db.query(SyncConfigDB).filter(
            SyncConfigDB.user_id == current_user.id
        ).first()
        
        if not config:
            # Create new config with the update data
            db_config = SyncConfigDB(
                user_id=current_user.id,
                auto_sync_enabled=config_update.auto_sync_enabled,
                sync_on_connectivity=config_update.sync_on_connectivity,
                sync_interval_minutes=config_update.sync_interval_minutes,
                max_offline_storage_mb=config_update.max_offline_storage_mb,
                conflict_resolution_strategy=config_update.conflict_resolution_strategy,
                prioritize_by_endpoint=config_update.prioritize_by_endpoint
            )
            
            db.add(db_config)
            action = "created"
        else:
            # Update existing config
            config.auto_sync_enabled = config_update.auto_sync_enabled
            config.sync_on_connectivity = config_update.sync_on_connectivity
            config.sync_interval_minutes = config_update.sync_interval_minutes
            config.max_offline_storage_mb = config_update.max_offline_storage_mb
            config.conflict_resolution_strategy = config_update.conflict_resolution_strategy
            config.prioritize_by_endpoint = config_update.prioritize_by_endpoint
            config.updated_at = datetime.utcnow()
            
            db_config = config
            action = "updated"
            
        try:
            db.commit()
            db.refresh(db_config)
            
            # Log the activity
            logger.info(
                f"User {current_user.id} {action} sync configuration",
                extra={"user_id": current_user.id, "config_id": db_config.id}
            )
            
            return db_config
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating sync configuration: {str(e)}")
            raise HTTPException(status_code=500, detail="Error updating sync configuration")
            
    return router
