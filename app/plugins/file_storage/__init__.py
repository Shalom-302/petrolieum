"""
File storage plugin for Kaapi

This plugin allows managing file storage with different providers:
- Local storage (file system)
- MinIO (compatible S3, for local development)
- Amazon S3
- Google Cloud Storage

It also includes image processing features:
- Generation of thumbnails
- Image optimization
- Image transformations (resizing, cropping, etc.)
"""

from .main import file_storage_router, file_storage_public_router

__all__ = ["file_storage_router", "file_storage_public_router"]
