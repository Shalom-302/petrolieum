"""
Pydantic schemas for the API versioning plugin.

This module defines the schemas used for API versioning changelog tracking.
All schemas are used for serialization and validation of API requests and responses.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Generic, TypeVar

from pydantic import BaseModel, Field


class APIVersionBase(BaseModel):
    """Base schema for API version information."""
    version: str = Field(..., description="Version number (e.g., '0.1', '0.2')")
    description: Optional[str] = Field(None, description="Description of this API version")


class APIVersionCreate(APIVersionBase):
    """Schema for creating a new API version."""
    is_current: bool = Field(False, description="Whether this is the current API version")


class APIVersionUpdate(BaseModel):
    """Schema for updating an API version."""
    version: Optional[str] = None
    description: Optional[str] = None
    is_current: Optional[bool] = None


class APIVersionInDB(APIVersionBase):
    """Schema for API version as stored in the database."""
    id: int
    release_date: datetime
    is_current: bool

    class Config:
        """Pydantic config."""
        from_attributes = True


class APIVersionResponse(APIVersionInDB):
    """Schema for API version response."""
    is_active: bool = Field(..., description="Whether this API version is active")
    is_deprecated: bool = Field(False, description="Whether this API version is deprecated")
    
    class Config:
        """Pydantic config."""
        from_attributes = True


T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic schema for paginated responses."""
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


class APIEndpointBase(BaseModel):
    """Base schema for API endpoint information."""
    path: str = Field(..., description="URL path of the endpoint")
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    description: Optional[str] = Field(None, description="Description of the endpoint")
    handler_module: Optional[str] = Field(None, description="Python module containing the handler")
    handler_function: Optional[str] = Field(None, description="Function name of the handler")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Parameters schema")
    response_model: Optional[Dict[str, Any]] = Field(None, description="Response model schema")


class APIEndpointCreate(APIEndpointBase):
    """Schema for creating a new API endpoint."""
    pass


class APIEndpointUpdate(BaseModel):
    """Schema for updating an API endpoint."""
    path: Optional[str] = None
    method: Optional[str] = None
    description: Optional[str] = None
    handler_module: Optional[str] = None
    handler_function: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    response_model: Optional[Dict[str, Any]] = None


class APIEndpointInDB(APIEndpointBase):
    """Schema for API endpoint as stored in the database."""
    id: int
    version_id: int
    created_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True


class APIChangeBase(BaseModel):
    """Base schema for API change information."""
    endpoint_path: str = Field(..., description="Path of the affected endpoint")
    change_type: str = Field(..., description="Type of change: 'added', 'modified', or 'removed'")
    description: str = Field(..., description="Human-readable description of the change")
    details: Optional[Dict[str, Any]] = Field(None, description="Detailed information about the change")


class APIChangeCreate(APIChangeBase):
    """Schema for creating a new API change record."""
    previous_version_id: int = Field(..., description="ID of the previous API version")
    new_version_id: int = Field(..., description="ID of the new API version")


class APIChangeInDB(APIChangeBase):
    """Schema for API change as stored in the database."""
    id: int
    previous_version_id: int
    new_version_id: int
    created_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True


class ChangelogEntry(BaseModel):
    """Schema for a changelog entry."""
    change_type: str
    endpoint_path: str
    description: str
    details: Optional[Dict[str, Any]] = None


class VersionChangelog(BaseModel):
    """Schema for a version's changelog."""
    from_version: str
    to_version: str
    release_date: datetime
    changes: List[ChangelogEntry]


class CompleteChangelog(BaseModel):
    """Schema for the complete changelog across all versions."""
    versions: List[VersionChangelog]


class VersionedAPIInfo(BaseModel):
    """Schema for versioned API information."""
    api_name: str = Field(..., description="Name of the API")
    description: Optional[str] = Field(None, description="Description of the API")
    default_version: Optional[APIVersionInDB] = Field(None, description="Default API version")
    active_versions: List[APIVersionInDB] = Field(default=[], description="List of active API versions")
    deprecated_versions: List[APIVersionInDB] = Field(default=[], description="List of deprecated API versions")
