"""
Models for the file storage plugin
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum

from app.core.db import Base
from .providers import (
    StorageProviderType as ProviderType, 
    PROVIDER_IMPLEMENTATIONS,
    StorageProviderInterface,
    StorageException
)


class StorageProviderType(PyEnum):
    """Types of storage providers supported"""
    MINIO = "minio"
    S3 = "s3"
    GOOGLE_CLOUD = "google_cloud"
    AZURE_BLOB = "azure_blob"
    LOCAL = "local"


class StorageProvider(Base):
    """Configuration of a storage provider"""
    __tablename__ = "file_storage_providers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    provider_type = Column(String(50), nullable=False)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Common configuration
    bucket_name = Column(String(100), nullable=False)
    region = Column(String(50))
    endpoint_url = Column(String(255))
    
    # Credentials (encrypted in the database)
    access_key = Column(String(255))
    secret_key = Column(String(255))
    
    # Advanced options stored as JSON
    config_options = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    files = relationship("StoredFile", back_populates="provider")
    
    def __repr__(self):
        return f"<StorageProvider {self.name} ({self.provider_type})>"


class StoredFile(Base):
    """File stored in a storage provider"""
    __tablename__ = "file_storage_files"
    
    id = Column(Integer, primary_key=True)
    provider_id = Column(Integer, ForeignKey("file_storage_providers.id"), nullable=False)
    
    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    mime_type = Column(String(255), nullable=False)
    content_hash = Column(String(128))  # Hash SHA-256 or similar
    
    # Metadata
    file_metadata = Column(JSON, nullable=True)
    
    # Access control
    is_public = Column(Boolean, default=False)
    access_token = Column(String(128), nullable=True)  # Token for temporary access
    token_expires_at = Column(DateTime, nullable=True)
    
    # Dates
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    provider = relationship("StorageProvider", back_populates="files")
    thumbnails = relationship("FileThumbnail", back_populates="original_file", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<StoredFile {self.filename} ({self.mime_type})>"


class FileThumbnail(Base):
    """Generated thumbnails for images"""
    __tablename__ = "file_storage_thumbnails"
    
    id = Column(Integer, primary_key=True)
    original_file_id = Column(Integer, ForeignKey("file_storage_files.id"), nullable=False)
    
    # Thumbnail information
    size = Column(String(20), nullable=False)  # ex: "sm", "md", "lg" or dimensions like "150x150"
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    storage_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    
    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    original_file = relationship("StoredFile", back_populates="thumbnails")
    
    def __repr__(self):
        return f"<FileThumbnail {self.size} for file {self.original_file_id}>"


class FileFolder(Base):
    """Virtual folder to organize files (tree structure)"""
    __tablename__ = "file_storage_folders"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("file_storage_folders.id"), nullable=True)
    
    # Metadata
    file_metadata = Column(JSON, nullable=True)
    
    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    parent = relationship("FileFolder", remote_side=[id], backref="children")
    
    def __repr__(self):
        return f"<FileFolder {self.name}>"


class FileFolderAssociation(Base):
    """Association between files and folders (a file can be in multiple folders)"""
    __tablename__ = "file_storage_folder_associations"
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("file_storage_files.id"), nullable=False)
    folder_id = Column(Integer, ForeignKey("file_storage_folders.id"), nullable=False)
    
    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<FileFolderAssociation file_id={self.file_id}, folder_id={self.folder_id}>"


def create_storage_provider(db, provider_data):
    """
    Create a new storage provider in the database
    
    Args:
        db: Database session
        provider_data: Provider data containing name, provider_type, and configuration
        
    Returns:
        The created StorageProvider object
    """
    provider = StorageProvider(
        name=provider_data.name,
        provider_type=provider_data.provider_type,
        bucket_name=provider_data.bucket_name,
        region=provider_data.region,
        endpoint_url=provider_data.endpoint_url,
        access_key=provider_data.access_key,
        secret_key=provider_data.secret_key,
        config_options=provider_data.config_options,
        is_default=provider_data.is_default,
    )
    
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def get_provider_instance(provider_config, request=None):
    """
    Create a storage provider instance based on the provider configuration
    
    Args:
        provider_config: StorageProvider model instance with configuration
        request: Optional FastAPI request object that might be needed for URL generation
        
    Returns:
        A storage provider instance that can be used to interact with the storage
    """
    provider_type = provider_config.provider_type
    
    if provider_type not in [pt.value for pt in ProviderType]:
        raise ValueError(f"Unsupported storage provider type: {provider_type}")
    
    # Get the provider class from the mapping
    provider_class = PROVIDER_IMPLEMENTATIONS[ProviderType(provider_type)]
    
    # Create the provider instance
    provider_instance = provider_class()
    
    # Prepare the configuration dictionary
    config = {
        'endpoint_url': provider_config.endpoint_url,
        'access_key': provider_config.access_key,
        'secret_key': provider_config.secret_key,
        'bucket_name': provider_config.bucket_name,
        'region': provider_config.region
    }
    
    # Add any additional config options
    if provider_config.config_options:
        config.update(provider_config.config_options)
    
    # Initialize the provider with the configuration
    provider_instance.initialize(config)
    
    return provider_instance
