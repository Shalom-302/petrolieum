"""
Database models for data import/export functionality.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SQLAlchemyEnum, ForeignKey, 
    Integer, JSON, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.orm import relationship

from app.core.db import Base


class DataFormatType(str, Enum):
    """Supported data formats for import/export."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    XML = "xml"


class JobStatusType(str, Enum):
    """Status of import/export jobs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"
    CANCELED = "canceled"


class ScheduleFrequencyType(str, Enum):
    """Frequency of scheduled jobs."""
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"  # For custom cron expressions


class ImportExportJob(Base):
    """Model for import/export job records."""
    __tablename__ = "data_exchange_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Job type
    is_import = Column(Boolean, default=True)  # True for import, False for export
    
    # Data format and configuration
    format_type = Column(SQLAlchemyEnum(DataFormatType), nullable=False)
    source_path = Column(String(255), nullable=False)  # File path or API endpoint
    target_entity = Column(String(255), nullable=False)  # Database table or file path
    
    # Configuration for the job (column mappings, validation rules, etc.)
    configuration = Column(JSON, nullable=True)
    
    # Template relationship
    template_id = Column(Integer, ForeignKey("data_exchange_templates.id"), nullable=True)
    template = relationship("ImportExportTemplate", back_populates="jobs")
    
    # Schedule relationship
    schedule_id = Column(Integer, ForeignKey("data_exchange_schedules.id"), nullable=True)
    schedule = relationship("ImportExportSchedule", back_populates="jobs")
    
    # Job status and results
    status = Column(SQLAlchemyEnum(JobStatusType), default=JobStatusType.PENDING)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Statistics
    records_processed = Column(Integer, default=0)
    records_succeeded = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    
    # Result logs (for errors, warnings, etc.)
    result_log = Column(JSON, nullable=True)
    
    # Ownership and timestamps
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ImportExportTemplate(Base):
    """Templates for reusable import/export configurations."""
    __tablename__ = "data_exchange_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Template type
    is_import = Column(Boolean, default=True)  # True for import, False for export
    
    # Data format and configuration
    format_type = Column(SQLAlchemyEnum(DataFormatType), nullable=False)
    target_entity = Column(String(255), nullable=False)  # Database table or file structure
    
    # Configuration for the job (column mappings, validation rules, etc.)
    configuration = Column(JSON, nullable=False)
    
    # Jobs using this template
    jobs = relationship("ImportExportJob", back_populates="template")
    
    # Ownership and timestamps
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ImportExportSchedule(Base):
    """Schedule configuration for automated import/export jobs."""
    __tablename__ = "data_exchange_schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Schedule configuration
    frequency = Column(SQLAlchemyEnum(ScheduleFrequencyType), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    
    # For custom schedules (cron expressions)
    cron_expression = Column(String(100), nullable=True)
    
    # Additional scheduling parameters
    parameters = Column(JSON, nullable=True)  # For day of week, hour, etc.
    
    # Jobs using this schedule
    jobs = relationship("ImportExportJob", back_populates="schedule")
    
    # Ownership and timestamps
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ValidationRule(Base):
    """Data validation rules that can be applied to import/export operations."""
    __tablename__ = "data_exchange_validation_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Rule type and configuration
    rule_type = Column(String(50), nullable=False)  # regex, range, enum, required, etc.
    configuration = Column(JSON, nullable=False)  # Rule-specific configuration
    
    # Target field and entity
    field_name = Column(String(100), nullable=False)
    target_entity = Column(String(255), nullable=False)
    
    # Ownership and timestamps
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
