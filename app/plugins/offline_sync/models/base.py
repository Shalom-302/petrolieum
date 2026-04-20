"""
Base models for the offline synchronization plugin.
"""

import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from app.core.db import Base


class SyncStatus(str, Enum):
    """Status of a synchronization operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CONFLICT = "conflict"


class SyncPriority(str, Enum):
    """Priority of a synchronization operation."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class SyncOperationDB(Base):
    """Model for storing operations to be synchronized."""
    __tablename__ = "offline_sync_operations"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Operation details
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE, etc.
    payload = Column(JSON, nullable=True)
    headers = Column(JSON, nullable=True)
    query_params = Column(JSON, nullable=True)
    
    # Synchronization metadata
    status = Column(String(20), default=SyncStatus.PENDING, nullable=False)
    priority = Column(String(20), default=SyncPriority.NORMAL, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_error = Column(Text, nullable=True)
    
    # Data encryption and security
    is_encrypted = Column(Boolean, default=False, nullable=False)
    encryption_metadata = Column(JSON, nullable=True)
    
    # Response data (when synchronized)
    response_data = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)
    
    # Batch synchronization
    batch_id = Column(String(36), ForeignKey("offline_sync_batches.id"), nullable=True)
    batch = relationship("SyncBatchDB", back_populates="operations")
    
    __table_args__ = (
        Index("ix_sync_operations_status_priority", "status", "priority"),
        Index("ix_sync_operations_user_id_status", "user_id", "status"),
    )


class SyncBatchDB(Base):
    """Model for grouping related operations into batches."""
    __tablename__ = "offline_sync_batches"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), default=SyncStatus.PENDING, nullable=False)
    
    # Synchronization metadata
    priority = Column(String(20), default=SyncPriority.NORMAL, nullable=False)
    
    # Relationships
    operations = relationship("SyncOperationDB", back_populates="batch")
    
    __table_args__ = (
        Index("ix_sync_batches_status_priority", "status", "priority"),
        Index("ix_sync_batches_user_id_status", "user_id", "status"),
    )


class SyncConfigDB(Base):
    """Model for storing user-specific synchronization configuration."""
    __tablename__ = "offline_sync_configs"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Configuration options
    auto_sync_enabled = Column(Boolean, default=True, nullable=False)
    sync_on_connectivity = Column(Boolean, default=True, nullable=False)
    sync_interval_minutes = Column(Integer, default=15, nullable=False)
    max_offline_storage_mb = Column(Integer, default=100, nullable=False)
    
    # Conflict resolution strategy
    conflict_resolution_strategy = Column(String(50), default="server_wins", nullable=False)
    
    # Prioritization settings
    prioritize_by_endpoint = Column(JSON, nullable=True)  # Map endpoints to priorities
