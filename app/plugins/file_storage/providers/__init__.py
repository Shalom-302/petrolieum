"""
File storage providers

This module contains the implementations of the different storage providers
supported by the plugin.
"""

from enum import Enum
from .base import StorageProviderInterface, StorageException
from .minio_provider import MinioStorageProvider
from .s3_provider import S3StorageProvider
from .gcs_provider import GCSStorageProvider
from .local_provider import LocalStorageProvider

class StorageProviderType(str, Enum):
    LOCAL = "local"
    MINIO = "minio"
    S3 = "s3"
    GCS = "gcs"

# Mapping supplier types to their implementation classes
PROVIDER_IMPLEMENTATIONS = {
    StorageProviderType.LOCAL: LocalStorageProvider,
    StorageProviderType.MINIO: MinioStorageProvider,
    StorageProviderType.S3: S3StorageProvider,
    StorageProviderType.GCS: GCSStorageProvider
}
