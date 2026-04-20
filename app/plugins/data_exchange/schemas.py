"""
Schemas for data import/export plugin.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator

from app.plugins.data_exchange.models import (
    DataFormatType, JobStatusType, ScheduleFrequencyType
)


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common fields."""
    
    class Config:
        from_attributes = True


# Template schemas
class TemplateBase(BaseSchema):
    """Base schema for import/export templates."""
    name: str
    description: Optional[str] = None
    is_import: bool = True
    format_type: DataFormatType
    target_entity: str
    configuration: Dict[str, Any]


class TemplateCreate(TemplateBase):
    """Schema for creating a new template."""
    pass


class TemplateUpdate(BaseSchema):
    """Schema for updating an existing template."""
    name: Optional[str] = None
    description: Optional[str] = None
    is_import: Optional[bool] = None
    format_type: Optional[DataFormatType] = None
    target_entity: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class TemplateResponse(TemplateBase):
    """Schema for template response."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


# Schedule schemas
class ScheduleParameter(BaseSchema):
    """Schema for schedule parameters."""
    day_of_week: Optional[List[int]] = None
    hour: Optional[List[int]] = None
    minute: Optional[List[int]] = None
    day_of_month: Optional[List[int]] = None
    month: Optional[List[int]] = None


class ScheduleBase(BaseSchema):
    """Base schema for import/export schedules."""
    name: str
    description: Optional[str] = None
    frequency: ScheduleFrequencyType
    start_date: datetime
    end_date: Optional[datetime] = None
    cron_expression: Optional[str] = None
    parameters: Optional[ScheduleParameter] = None
    
    @validator('cron_expression')
    def validate_cron_expression(cls, v, values):
        if values.get('frequency') == ScheduleFrequencyType.CUSTOM and not v:
            raise ValueError('Cron expression is required for custom frequency')
        return v


class ScheduleCreate(ScheduleBase):
    """Schema for creating a new schedule."""
    pass


class ScheduleUpdate(BaseSchema):
    """Schema for updating an existing schedule."""
    name: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[ScheduleFrequencyType] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    cron_expression: Optional[str] = None
    parameters: Optional[ScheduleParameter] = None
    is_active: Optional[bool] = None


class ScheduleResponse(ScheduleBase):
    """Schema for schedule response."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


# Job schemas
class JobBase(BaseSchema):
    """Base schema for import/export jobs."""
    name: str
    description: Optional[str] = None
    is_import: bool = True
    format_type: DataFormatType
    source_path: str
    target_entity: str
    configuration: Optional[Dict[str, Any]] = None
    template_id: Optional[int] = None
    schedule_id: Optional[int] = None


class JobCreate(JobBase):
    """Schema for creating a new job."""
    pass


class JobUpdate(BaseSchema):
    """Schema for updating an existing job."""
    name: Optional[str] = None
    description: Optional[str] = None
    is_import: Optional[bool] = None
    format_type: Optional[DataFormatType] = None
    source_path: Optional[str] = None
    target_entity: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    template_id: Optional[int] = None
    schedule_id: Optional[int] = None
    status: Optional[JobStatusType] = None
    is_active: Optional[bool] = None


class JobStatusUpdate(BaseSchema):
    """Schema for updating job status."""
    status: JobStatusType
    error_message: Optional[str] = None
    records_processed: Optional[int] = None
    records_succeeded: Optional[int] = None
    records_failed: Optional[int] = None


class JobResponse(JobBase):
    """Schema for job response."""
    id: int
    user_id: int
    status: JobStatusType
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    records_processed: int = 0
    records_succeeded: int = 0
    records_failed: int = 0
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


class JobDetailResponse(JobResponse):
    """Schema for detailed job response."""
    result_log: Optional[Dict[str, Any]] = None
    template: Optional[TemplateResponse] = None
    schedule: Optional[ScheduleResponse] = None


# Validation rule schemas
class ValidationRuleBase(BaseSchema):
    """Base schema for validation rules."""
    name: str
    description: Optional[str] = None
    rule_type: str
    configuration: Dict[str, Any]
    field_name: str
    target_entity: str


class ValidationRuleCreate(ValidationRuleBase):
    """Schema for creating a new validation rule."""
    pass


class ValidationRuleUpdate(BaseSchema):
    """Schema for updating an existing validation rule."""
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    field_name: Optional[str] = None
    target_entity: Optional[str] = None
    is_active: Optional[bool] = None


class ValidationRuleResponse(ValidationRuleBase):
    """Schema for validation rule response."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


# Request schemas for specific operations
class ImportDataRequest(BaseSchema):
    """Schema for importing data."""
    job_id: Optional[int] = None
    template_id: Optional[int] = None
    file_path: Optional[str] = None
    format_type: Optional[DataFormatType] = None
    target_entity: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    validate_only: bool = False
    
    @validator('job_id', 'template_id')
    def validate_at_least_one_reference(cls, v, values):
        # Either job_id, template_id, or file_path + format_type + target_entity must be provided
        if not v and not values.get('job_id') and not values.get('template_id'):
            if not (values.get('file_path') and values.get('format_type') and values.get('target_entity')):
                raise ValueError('Either job_id, template_id, or file_path + format_type + target_entity must be provided')
        return v


class ExportDataRequest(BaseSchema):
    """Schema for exporting data."""
    job_id: Optional[int] = None
    template_id: Optional[int] = None
    file_path: Optional[str] = None
    format_type: Optional[DataFormatType] = None
    target_entity: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    query_filters: Optional[Dict[str, Any]] = None
    
    @validator('job_id', 'template_id')
    def validate_at_least_one_reference(cls, v, values):
        # Either job_id, template_id, or file_path + format_type + target_entity must be provided
        if not v and not values.get('job_id') and not values.get('template_id'):
            if not (values.get('file_path') and values.get('format_type') and values.get('target_entity')):
                raise ValueError('Either job_id, template_id, or file_path + format_type + target_entity must be provided')
        return v


class ColumnMapping(BaseSchema):
    """Schema for column mapping configuration."""
    source_column: str
    target_column: str
    transform_function: Optional[str] = None
    default_value: Optional[Any] = None
    validation_rules: Optional[List[int]] = None


class DataValidationError(BaseSchema):
    """Schema for validation errors."""
    row_index: int
    field_name: str
    error_message: str
    value: Optional[Any] = None


class DataImportPreviewResponse(BaseSchema):
    """Schema for data import preview response."""
    headers: List[str]
    sample_data: List[Dict[str, Any]]
    detected_types: Dict[str, str]
    suggested_mappings: Dict[str, str]
    validation_errors: Optional[List[DataValidationError]] = None


class DataImportResponse(BaseSchema):
    """Schema for data import response."""
    success: bool
    job_id: Optional[int] = None
    records_processed: int = 0
    records_succeeded: int = 0
    records_failed: int = 0
    validation_errors: Optional[List[DataValidationError]] = None
    error_message: Optional[str] = None


class DataExportResponse(BaseSchema):
    """Schema for data export response."""
    success: bool
    job_id: Optional[int] = None
    file_path: Optional[str] = None
    records_processed: int = 0
    error_message: Optional[str] = None


# Pagination schemas
class PaginatedResponse(BaseSchema):
    """Base schema for paginated responses."""
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 50
    pages: int = 1
