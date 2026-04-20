"""
Pydantic schemas for the file storage plugin
"""

from pydantic import BaseModel, Field, validator, HttpUrl, AnyUrl, ValidationError
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class StorageProviderType(str, Enum):
    """Supported storage provider types"""
    MINIO = "minio"
    S3 = "s3"
    GOOGLE_CLOUD = "google_cloud" 
    AZURE_BLOB = "azure_blob"
    LOCAL = "local"


class StorageProviderBase(BaseModel):
    """Base schema for storage providers"""
    name: str = Field(..., description="Unique provider name", example="MinIO Local")
    provider_type: StorageProviderType = Field(..., description="Storage provider type")
    is_default: bool = Field(False, description="If this provider is the default provider")
    is_active: bool = Field(True, description="If this provider is active")
    bucket_name: str = Field(..., description="Bucket/container name", example="files")
    region: Optional[str] = Field(None, description="Region (if applicable)", example="us-east-1")
    endpoint_url: Optional[str] = Field(None, description="Custom endpoint URL (required for MinIO)", 
                                     example="http://minio-server:9000")


class StorageProviderCreate(StorageProviderBase):
    """Schema to create a storage provider"""
    access_key: Optional[str] = Field(None, description="Access key")
    secret_key: Optional[str] = Field(None, description="Secret key")
    config_options: Optional[Dict[str, Any]] = Field(None, description="Advanced configuration options")

    @validator('endpoint_url', always=True)
    def validate_endpoint_for_minio(cls, v, values):
        if values.get('provider_type') == StorageProviderType.MINIO and not v:
            raise ValueError("Endpoint URL is required for the MinIO provider")
        return v

    @validator('access_key', 'secret_key', always=True)
    def validate_credentials(cls, v, values):
        provider_type = values.get('provider_type')
        if provider_type in [StorageProviderType.MINIO, StorageProviderType.S3] and not v:
            raise ValueError(f"Credentials are required for the {provider_type} provider")
        return v


class StorageProviderUpdate(BaseModel):
    """Schema to update a storage provider"""
    name: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    bucket_name: Optional[str] = None
    region: Optional[str] = None
    endpoint_url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    config_options: Optional[Dict[str, Any]] = None


class StorageProviderRead(StorageProviderBase):
    """Schema to read a storage provider"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StorageProviderDetail(StorageProviderRead):
    """Schema to read a storage provider (with sensitive information masked)"""
    access_key: Optional[str] = None
    secret_key: Optional[str] = Field(None, description="Always masked for security reasons")
    config_options: Optional[Dict[str, Any]] = None
    
    @validator('access_key')
    def mask_access_key(cls, v):
        if v:
            # Show only the first 4 characters
            return v[:4] + "****" if len(v) > 4 else "****"
        return v

    @validator('secret_key')
    def mask_secret_key(cls, v):
        if v:
            return "********"
        return v


class StorageProviderResponse(BaseModel):
    """Response schema for storage provider operations"""
    provider: StorageProviderDetail
    message: str = "Storage provider operation completed successfully"


class StoredFileBase(BaseModel):
    """Schema for base stored files"""
    filename: str = Field(..., description="Filename in storage")
    original_filename: str = Field(..., description="Original filename during upload")
    mime_type: str = Field(..., description="MIME type of the file", example="image/jpeg")
    is_public: bool = Field(False, description="If the file is accessible publicly")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the file")


class StoredFileCreate(BaseModel):
    """Schema used after file upload to create database entry"""
    provider_id: Optional[int] = Field(None, description="ID of the storage provider (if not specified, the default provider will be used)")
    filename: str
    original_filename: str
    storage_path: str
    file_size: int
    mime_type: str
    content_hash: Optional[str] = None
    is_public: bool = False
    metadata: Optional[Dict[str, Any]] = None


class StoredFileUpdate(BaseModel):
    """Schema to update a stored file"""
    filename: Optional[str] = None
    is_public: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class StoredFileRead(StoredFileBase):
    """Schema to read a stored file"""
    id: int
    provider_id: int
    storage_path: str
    file_size: int
    content_hash: Optional[str] = None
    access_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    uploaded_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StoredFileDetail(StoredFileRead):
    """Schema to read a stored file (with download URL)"""
    download_url: str = Field(..., description="URL to download the file")
    view_url: Optional[str] = Field(None, description="URL to view the file (for images, PDF, etc.)")
    thumbnails: Optional[List["FileThumbnailRead"]] = None
    provider: StorageProviderRead


class FileThumbnailBase(BaseModel):
    """Schema for base thumbnails"""
    size: str = Field(..., description="Thumbnail size", example="sm, md, lg or 150x150")
    width: Optional[int] = None
    height: Optional[int] = None


class FileThumbnailCreate(FileThumbnailBase):
    """Schema to create a thumbnail"""
    original_file_id: int
    storage_path: str
    file_size: int


class FileThumbnailRead(FileThumbnailBase):
    """Schema to read a thumbnail"""
    id: int
    original_file_id: int
    storage_path: str
    file_size: int
    created_at: datetime
    url: str = Field(..., description="URL to access the thumbnail")
    
    class Config:
        from_attributes = True


class FileThumbnailResponse(BaseModel):
    """Response schema for thumbnail operations"""
    thumbnail: FileThumbnailRead
    message: str = "Thumbnail operation completed successfully"


class FileFolderBase(BaseModel):
    """Schema for base folders"""
    name: str = Field(..., description="Folder name")
    parent_id: Optional[int] = Field(None, description="ID of the parent folder (null for root folder)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the folder")


class FileFolderCreate(FileFolderBase):
    """Schema to create a folder"""
    pass


class FileFolderUpdate(BaseModel):
    """Schema to update a folder"""
    name: Optional[str] = None
    parent_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class FileFolderRead(FileFolderBase):
    """Schema to read a folder"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FileFolderDetail(FileFolderRead):
    """Schema to read a folder (with children and file count)"""
    children: List["FileFolderRead"] = []
    files_count: int = 0
    
    class Config:
        from_attributes = True


class FileFolderResponse(BaseModel):
    """Response schema for folder operations"""
    folder: FileFolderRead
    message: str = "Folder operation completed successfully"


class FileFolderDetailResponse(BaseModel):
    """Response schema for detailed folder information"""
    folder: FileFolderDetail
    message: str = "Folder details retrieved successfully"


class FileUploadResponse(BaseModel):
    """Response after a successful file upload"""
    file: StoredFileDetail
    message: str = "File uploaded successfully"


class StoredFileResponse(BaseModel):
    """Response schema for stored file operations"""
    file: StoredFileRead
    message: str = "File operation completed successfully"


class StoredFileDetailResponse(BaseModel):
    """Response schema for detailed stored file information"""
    file: StoredFileDetail
    message: str = "File details retrieved successfully"


class FileUploadRequest(BaseModel):
    """Metadata for file upload requests"""
    provider_id: Optional[int] = None
    folder_id: Optional[int] = None
    is_public: bool = False
    metadata: Optional[Dict[str, Any]] = None
    generate_thumbnails: bool = Field(True, description="Generate thumbnails automatically for images")


class ImageTransformRequest(BaseModel):
    """Request for image transformation"""
    file_id: int = Field(..., description="ID of the file to transform")
    operations: List[Dict[str, Any]] = Field(..., description="List of operations to perform")
    output_format: Optional[str] = Field("jpeg", description="Output format (jpeg, png, webp, etc.)")
    output_quality: Optional[int] = Field(85, description="Output quality (1-100)")
    create_copy: bool = Field(True, description="Create a copy or replace the original")


# Resolve circular references
StoredFileDetail.update_forward_refs()
FileFolderDetail.update_forward_refs()
