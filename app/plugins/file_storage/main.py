"""
Main module for the file storage plugin
"""

import os
import io
import uuid
import json
import logging
import re
import math
from typing import Dict, List, Optional, Any, BinaryIO, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request, BackgroundTasks, Header
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile
from datetime import datetime

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.advanced_auth.models import User

from .models import (
    StorageProvider, StoredFile, FileThumbnail, FileFolder,
    create_storage_provider, get_provider_instance
)
from .schemas import (
    StorageProviderCreate, StorageProviderUpdate, StorageProviderResponse, StorageProviderDetail,
    StoredFileCreate, StoredFileUpdate, StoredFileResponse, StoredFileDetailResponse,
    FileThumbnailResponse, FileFolderCreate, FileFolderResponse
)
from .providers import StorageProviderType, StorageException

from .routes.folders import router as folders_router
from .routes.images import router as images_router
from app.crud_base import log_audit_event  # Ajout de l'import pour l'audit

def serialize_sqlalchemy_model(model, exclude=None):
    """
    Convertit un modèle SQLAlchemy en un dictionnaire sérialisable pour Pydantic.
    
    Args:
        model: Instance de modèle SQLAlchemy
        exclude: Liste de champs à exclure
        
    Returns:
        Un dictionnaire contenant les données du modèle
    """
    exclude = exclude or []
    data = {}
    
    for column in model.__table__.columns:
        if column.name in exclude:
            continue
            
        value = getattr(model, column.name)
        
        # Conversion spéciale pour les champs JSON
        if column.type.__class__.__name__ == 'JSON':
            if value is None:
                data[column.name] = {}
            elif isinstance(value, dict):
                data[column.name] = value
            else:
                try:
                    # Essai de conversion en dictionnaire si c'est un objet JSON
                    data[column.name] = json.loads(json.dumps(value))
                except:
                    # Fallback en cas d'échec
                    data[column.name] = {}
        else:
            data[column.name] = value
            
    return data

def get_router() -> APIRouter:

    router = APIRouter()

    router.include_router(folders_router)
    router.include_router(images_router)

    logger = logging.getLogger(__name__)

    # Routes for storage providers
    @router.post("/providers", response_model=StorageProviderResponse)
    async def create_provider(
        provider_data: StorageProviderCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """
        Create a new storage provider configuration
        """
        try:
            provider = create_storage_provider(db, provider_data)
            return provider
        except Exception as e:
            logger.error(f"Error during storage provider creation: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/providers", response_model=List[StorageProviderDetail])
    async def list_providers(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """
        List available storage provider configurations
        """
        providers = db.query(StorageProvider).offset(skip).limit(limit).all()
        return providers

    @router.get("/providers/{provider_id}", response_model=StorageProviderDetail)
    async def get_provider(
        provider_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """
        Get details of a storage provider
        """
        provider = db.query(StorageProvider).filter(StorageProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        return provider

    @router.put("/providers/{provider_id}", response_model=StorageProviderDetail)
    async def update_provider(
        provider_id: int,
        provider_data: StorageProviderUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """
        Update a storage provider configuration
        """
        provider = db.query(StorageProvider).filter(StorageProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        # Mettre à jour les champs
        for field, value in provider_data.dict(exclude_unset=True).items():
            setattr(provider, field, value)
        
        try:
            db.commit()
            db.refresh(provider)
            return provider
        except Exception as e:
            db.rollback()
            logger.error(f"Error during storage provider update: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/providers/{provider_id}", response_model=dict)
    async def delete_provider(
        provider_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """
        Delete a storage provider configuration
        """
        provider = db.query(StorageProvider).filter(StorageProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        # Check if there are files using this provider
        file_count = db.query(StoredFile).filter(StoredFile.provider_id == provider_id).count()
        if file_count > 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete: {file_count} files use this provider"
            )
        
        try:
            db.delete(provider)
            db.commit()
            return {"message": "Storage provider deleted successfully"}
        except Exception as e:
            db.rollback()
            logger.error(f"Error during storage provider deletion: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    # Routes for file upload and management
    @router.post("/files/upload", response_model=StoredFileResponse)
    async def upload_file(
        file: UploadFile = File(...),
        provider_id: int = Form(...),
        folder_id: Optional[int] = Form(None),
        folder_path: Optional[str] = Form(None),
        description: str = Form(None),
        tags: str = Form(None),
        generate_thumbnails: bool = Form(False),
        optimize_images: bool = Form(False),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        request: Request = None
    ):
        """
        Upload a file to the configured storage
        """
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        # Optionally get the folder
        folder = None
        folder_prefix = ""
        if folder_id:
            folder = db.query(FileFolder).filter(FileFolder.id == folder_id).first()
            if not folder:
                raise HTTPException(status_code=404, detail=f"Folder with ID {folder_id} not found")
            folder_prefix = folder.name + "/"
        elif folder_path:
            folder_prefix = folder_path.strip("/") + "/"
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Prepare file content
            file_content = await file.read()
            
            # Sanitize the filename and add a unique identifier
            original_filename = file.filename
            sanitized_filename = re.sub(r'[^\w\-\.]', '_', original_filename)
            unique_id = uuid.uuid4().hex[:8]
            filename = f"{unique_id}_{sanitized_filename}"
            
            # Complete storage path including folder prefix
            storage_path = f"{folder_prefix}{filename}"
            
            # Create a BytesIO to store the file data (pour avoir un objet avec la méthode seek())
            file_data = io.BytesIO(file_content)
            
            # Upload the file to storage - correction de l'ordre des paramètres
            file_url = provider.upload_file(
                file_data,  # 1st parameter: file object with seek() method
                storage_path,  # 2nd parameter: destination path
                file.content_type  # 3rd parameter: content type
            )
            
            # Parse tags if provided
            tag_list = []
            if tags:
                tag_list = [tag.strip() for tag in tags.split(',')]
            
            # Create the file record
            db_file = StoredFile(
                provider_id=provider_id,
                filename=filename,
                original_filename=original_filename,
                storage_path=storage_path,
                file_size=len(file_content),
                mime_type=file.content_type or "application/octet-stream",
                file_metadata={
                    "description": description,
                    "tags": tag_list,
                    "url": file_url,  # Store the URL in metadata
                    "folder_id": folder.id if folder else None  # Store the folder ID in metadata
                }
            )
            
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
            
            # TODO: Add asynchronous thumbnail processing and optimization if necessary
            
            # Use our serialization function for the model
            file_data = serialize_sqlalchemy_model(db_file)
            
            # Log audit event for file upload
            log_audit_event(
                db=db, 
                user_id=current_user.id, 
                action="upload_file", 
                resource="file", 
                details=f"File ID: {db_file.id}, Name: {db_file.original_filename}"
            )
            
            # Return the response in the expected schema format
            return {"file": file_data, "message": "File uploaded successfully"}
            
        except StorageException as e:
            logger.error(f"Error during storage upload: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error during storage upload: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during storage upload: {str(e)}")
        finally:
            # Close the file
            await file.close()

    @router.get("/files", response_model=List[StoredFileResponse])
    async def list_files(
        provider_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        folder_path: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """
        List stored files with optional filtering
        """
        query = db.query(StoredFile)
        
        # Apply filters
        if provider_id:
            query = query.filter(StoredFile.provider_id == provider_id)
        
        # If folder_id is specified, first get the folder name
        if folder_id is not None:
            folder = db.query(FileFolder).filter(FileFolder.id == folder_id).first()
            if folder:
                # Improvement: Handle cases where the path may have an extra space after the folder name
                # Filter by the storage path that starts with the folder name followed by "/"
                # Use two OR conditions to account for both formats
                query = query.filter(
                    or_(
                        StoredFile.storage_path.like(f"{folder.name}/%"),  # Case without space
                        StoredFile.storage_path.like(f"{folder.name} /%")  # Case with space
                    )
                )
                # Check also the metadata for folder_id
                query = query.filter(
                    or_(
                        StoredFile.file_metadata['folder_id'].astext == str(folder_id),
                        StoredFile.storage_path.like(f"{folder.name}/%"),
                        StoredFile.storage_path.like(f"{folder.name} /%")
                    )
                )
        elif folder_path:
            # Filter by path with the same improvement for spaces
            query = query.filter(
                or_(
                    StoredFile.storage_path.like(f"{folder_path}/%"),
                    StoredFile.storage_path.like(f"{folder_path} /%")
                )
            )
        else:
            # If we are at the root (neither folder_id nor folder_path specified),
            # exclude files that are in folders
            
            # 1. Get all folder names
            folders = db.query(FileFolder).all()
            folder_names = [folder.name for folder in folders]
            
            # 2. Exclude files whose path starts with a folder name followed by "/"
            for folder_name in folder_names:
                query = query.filter(
                    and_(
                        ~StoredFile.storage_path.like(f"{folder_name}/%"),
                        ~StoredFile.storage_path.like(f"{folder_name} /%")
                    )
                )
                # Check also if the file does not have a folder reference in its metadata
                query = query.filter(
                    or_(
                        StoredFile.file_metadata['folder_id'] == None,
                        StoredFile.file_metadata['folder_id'].astext == 'null'
                    )
                )
        
        if content_type:
            query = query.filter(StoredFile.mime_type.like(f"{content_type}%"))
        
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            for tag in tag_list:
                query = query.filter(StoredFile.file_metadata['tags'].contains([tag]))
        
        # Execute the query with pagination
        files = query.order_by(StoredFile.uploaded_at.desc()).offset(skip).limit(limit).all()
        
        # Use our serialization function for each file
        serialized_files = [serialize_sqlalchemy_model(file) for file in files]
        
        # Return files in the format expected by the schema
        return [{"file": file, "message": "File retrieved successfully"} for file in serialized_files]

    @router.get("/files/{file_id}", response_model=StoredFileDetailResponse)
    async def get_file_details(
        file_id: int,
        db: Session = Depends(get_db),
        request: Request = None
    ):
        """
        Get details about a stored file
        """
        db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        # Get the provider instance
        provider = get_provider_instance(provider_db, request)
        
        # Generate URLS
        try:
            # Try to obtain URLs via the provider
            download_url = provider.get_file_url(db_file.storage_path, expires=3600, is_public=False, request=request)
            preview_url = provider.get_file_url(db_file.storage_path, expires=86400, is_public=True, request=request)
        except Exception as e:
            logger.warning(f"Error generating URLs via provider: {str(e)}")
            # Fallback: generate URLs directly via API
            base_url = str(request.base_url).rstrip('/')
            download_url = f"{base_url}/api/public/file-storage/files/{file_id}/download"
            preview_url = f"{base_url}/api/public/file-storage/files/{file_id}/preview"
        
        # If the URLs are still empty, force the use of API URLs
        if not download_url or not preview_url:
            base_url = str(request.base_url).rstrip('/')
            download_url = f"{base_url}/api/public/file-storage/files/{file_id}/download"
            preview_url = f"{base_url}/api/public/file-storage/files/{file_id}/preview"
        
        # Convert to dict for response
        file_dict = serialize_sqlalchemy_model(db_file)
        
        # Add URLs
        file_dict["url"] = preview_url
        file_dict["download_url"] = download_url
        
        return file_dict

    @router.get("/files/{file_id}/download")
    async def download_file(
        file_id: int,
        attachment: bool = True,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        request: Request = None
    ):
        """
        Download a stored file
        """
        db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Download the file from storage
            file_data = provider.download_file(db_file.storage_path)
            
            # Prepare headers
            headers = {}
            if attachment:
                headers["Content-Disposition"] = f'attachment; filename="{db_file.original_filename}"'
            
            # Log audit event for file download
            log_audit_event(
                db=db, 
                user_id=current_user.id, 
                action="download_file", 
                resource="file", 
                details=f"File ID: {db_file.id}, Name: {db_file.title}"
            )
            
            # Return the file data streaming
            return StreamingResponse(
                iter([file_data.getvalue()]), 
                media_type=db_file.mime_type,
                headers=headers
            )
            
        except StorageException as e:
            logger.error(f"Storage error during file download: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error during file download: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during file download: {str(e)}")

    @router.get("/files/{file_id}/download-url", response_model=dict)
    async def get_file_download_url(
        file_id: int,
        expires: int = 3600,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        request: Request = None
    ):
        """
        Get a pre-signed URL to download a stored file
        """
        db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Generate a pre-signed URL for the file
            download_url = provider.get_file_url(db_file.storage_path, expires=expires, is_public=False, request=request)
            
            # Log audit event for file download URL generation
            log_audit_event(
                db=db, 
                user_id=current_user.id, 
                action="generate_download_url", 
                resource="file", 
                details=f"File ID: {db_file.id}, Name: {db_file.title}"
            )
            
            return {"url": download_url, "filename": db_file.original_filename}
            
        except StorageException as e:
            logger.error(f"Storage error during URL generation: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error during URL generation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating download URL: {str(e)}")

    @router.get("/files/{file_id}/preview")
    async def preview_file(
        file_id: int,
        db: Session = Depends(get_db),
        request: Request = None
    ):
        """
        Preview a stored file (optimized for in-browser viewing/playing)
        Returns file with Content-Disposition: inline for browser rendering
        """
        db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Download the file from storage
            file_data = provider.download_file(db_file.storage_path)
            
            # Set Content-Disposition to inline to render in browser
            headers = {
                "Content-Disposition": f'inline; filename="{db_file.original_filename}"',
                "Accept-Ranges": "bytes"  # Enable seeking in media files
            }
            
            # Special case for PDFs
            if db_file.mime_type == "application/pdf":
                # PDFs need these specific headers
                headers["X-Content-Type-Options"] = "nosniff"
                
            # Special case for videos
            if db_file.mime_type.startswith("video/"):
                # Add specific headers for videos
                headers["X-Content-Type-Options"] = "nosniff"
                # Force the use of the appropriate content-type
                if db_file.mime_type == "video/mp4":
                    headers["Content-Type"] = "video/mp4"
                elif db_file.mime_type == "video/webm":
                    headers["Content-Type"] = "video/webm"
                elif db_file.mime_type == "video/ogg":
                    headers["Content-Type"] = "video/ogg"
            
            # Log audit event for file preview
            log_audit_event(
                db=db, 
                user_id=current_user.id, 
                action="preview_file", 
                resource="file", 
                details=f"File ID: {db_file.id}, Name: {db_file.title}"
            )
            
            # Return the file data for browser rendering
            return StreamingResponse(
                iter([file_data.getvalue()]), 
                headers=headers,
                media_type=db_file.mime_type
            )
            
        except StorageException as e:
            logger.error(f"Storage error during file preview: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error during file preview: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during file preview: {str(e)}")

    @router.delete("/files/{file_id}", response_model=dict)
    async def delete_file(
        file_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        request: Request = None
    ):
        """
        Delete a stored file and its metadata
        """
        db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Delete all thumbnails
            thumbnails = db.query(FileThumbnail).filter(FileThumbnail.original_file_id == file_id).all()
            for thumbnail in thumbnails:
                # Delete the thumbnail file from storage
                try:
                    provider.delete_file(thumbnail.storage_path)
                except Exception as e:
                    logger.warning(f"Unable to delete thumbnail {thumbnail.id}: {str(e)}")
                
                # Delete the thumbnail record
                db.delete(thumbnail)
            
            # Delete the file from storage
            provider.delete_file(db_file.storage_path)
            
            # Delete the file record
            db.delete(db_file)
            db.commit()
            
            # Log audit event for file deletion
            log_audit_event(
                db=db, 
                user_id=current_user.id, 
                action="delete_file", 
                resource="file", 
                details=f"File ID: {db_file.id}, Name: {db_file.original_filename}"
            )
            
            return {"message": "File deleted successfully"}
            
        except StorageException as e:
            db.rollback()
            logger.error(f"Storage error during file deletion: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error during file deletion: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during file deletion: {str(e)}")

    # Implementations for folders, thumbnails, and image processing
    # will be added in separate modules to maintain code readability.

    router.include_router(folders_router)
    router.include_router(images_router)

    return router

def get_public_router() -> APIRouter:
    router = APIRouter()

    router.include_router(folders_router)
    router.include_router(images_router)

    logger = logging.getLogger(__name__)
    

    @router.get("/providers", response_model=List[StorageProviderDetail])
    async def list_providers(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        """
        List available storage provider configurations
        """
        providers = db.query(StorageProvider).offset(skip).limit(limit).all()
        return providers

    @router.get("/status", include_in_schema=True)
    async def check_storage_status():
        """
        Public endpoint to check the storage service status
        No authentication required
        """
        return {
            "status": "ok",
            "message": "File storage service is running"
        }
        
    @router.get("/files/{file_id}/preview-url", response_model=Dict[str, str])
    async def get_preview_url(
        file_id: int,
        db: Session = Depends(get_db),
        request: Request = None
    ):
        """
        Generate a presigned URL optimized for streaming media and inline viewing
        Returns a URL that can be used to access the file directly
        No authentication required for public access
        """
        try:
            # Get the file from the database
            db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
            if not db_file:
                raise HTTPException(status_code=404, detail="File not found")
                
            # Get the provider
            provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
            if not provider_db:
                raise HTTPException(status_code=404, detail="Storage provider not found")
                
            # Create a provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Generate a presigned URL with response-content-disposition=inline
            # and other headers optimized for streaming
            url_params = {
                "ResponseContentDisposition": f"inline; filename=\"{db_file.original_filename}\"",
                "ResponseContentType": db_file.mime_type,
                "ResponseCacheControl": "public, max-age=3600",  # Cache for 1 hour
            }
            
            # Generate the URL with a 1 hour expiry by default
            url = provider.generate_presigned_url(
                db_file.storage_path, 
                expiry=3600,
                extra_params=url_params
            )
            
            return {"url": url}
            
        except StorageException as e:
            logger.error(f"Storage error generating preview URL: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error generating preview URL: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating preview URL: {str(e)}")

    @router.get("/files", response_model=Dict[str, Any])
    async def list_public_files(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        search: str = Query("", min_length=0, max_length=100),
        sort_by: str = Query("created_at", min_length=1, max_length=50),
        sort_order: str = Query("desc", min_length=1, max_length=4),
        file_type: Optional[str] = Query(None, min_length=0, max_length=50),
        db: Session = Depends(get_db),
        request: Request = None
    ):
        """
        List public files
        """
        # Creating the basic query
        query = db.query(StoredFile)
        
        # Filter by file type
        if file_type:
            query = query.filter(StoredFile.mime_type.ilike(f"{file_type}%"))
        
        # Search
        if search:
            query = query.filter(
                or_(
                    StoredFile.original_filename.ilike(f"%{search}%"),
                    StoredFile.description.ilike(f"%{search}%"),
                    StoredFile.mime_type.ilike(f"%{search}%")
                )
            )
        
        # Sorting
        if sort_order.lower() not in ["asc", "desc"]:
            sort_order = "desc"
        
        sort_column = getattr(StoredFile, sort_by, StoredFile.uploaded_at)
        if sort_order.lower() == "desc":
            sort_column = sort_column.desc()
        else:
            sort_column = sort_column.asc()
        
        query = query.order_by(sort_column)
        
        # Count total
        total = query.count()
        
        # Pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        # Execute the query
        files = query.all()
        
        # Retrieve providers for these files
        provider_ids = [file.provider_id for file in files]
        providers = {
            provider.id: provider 
            for provider in db.query(StorageProvider).filter(
                StorageProvider.id.in_(provider_ids)
            ).all()
        }
        
        # Prepare the results
        results = []
        base_url = str(request.base_url).rstrip('/') if request else ""
        
        for file in files:
            # Retrieve the provider instance
            provider_db = providers.get(file.provider_id)
            if not provider_db:
                continue
                
            provider = get_provider_instance(provider_db, request)
            
            # Try to generate a URL via the provider
            try:
                preview_url = provider.get_file_url(file.storage_path, expires=86400, is_public=True, request=request)
                download_url = provider.get_file_url(file.storage_path, expires=3600, is_public=False, request=request)
            except Exception as e:
                logger.warning(f"Error generating URL for file {file.id}: {str(e)}")
                preview_url = ""
                download_url = ""
            
            # If the URL is empty, generate a direct URL via the API
            if not preview_url:
                preview_url = f"{base_url}/api/public/file-storage/files/{file.id}/preview"
                
            if not download_url:
                download_url = f"{base_url}/api/public/file-storage/files/{file.id}/download"
            
            file_dict = serialize_sqlalchemy_model(file)
            file_dict["url"] = preview_url
            file_dict["download_url"] = download_url
            
            results.append(file_dict)
            
        return {
            "items": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size)
        }
        
    @router.get("/files/{file_id}/download")
    async def public_download_file(
        file_id: int, 
        attachment: bool = True, 
        db: Session = Depends(get_db),
        request: Request = None
    ):
        """Download a file publicly"""
        db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Download the file from storage
            file_data = provider.download_file(db_file.storage_path)
            
            # Encoder le nom de fichier pour éviter les problèmes d'encodage
            import urllib.parse
            encoded_filename = urllib.parse.quote(db_file.original_filename)
            
            # Set Content-Disposition header based on attachment parameter
            if attachment:
                content_disposition = f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            else:
                content_disposition = f'inline; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
                
            headers = {
                "Content-Disposition": content_disposition,
                "Access-Control-Allow-Origin": "*",  # CORS for allowing access from the frontend
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Content-Type": db_file.mime_type,
                "Accept-Ranges": "bytes"
            }
            
            # Retourner le contenu du fichier
            return StreamingResponse(
                iter([file_data.getvalue()]), 
                headers=headers,
                media_type=db_file.mime_type
            )
            
        except StorageException as e:
            logger.error(f"Storage error during file download: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error during file download: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during file download: {str(e)}")

    @router.get("/files/{file_id}/preview")
    async def public_preview_file(
        file_id: int,
        db: Session = Depends(get_db),
        request: Request = None,
        range_header: Optional[str] = Header(None, alias="Range")
    ):
        """
        Endpoint public to preview a file with streaming and Range requests support
        """
        db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Download the file from storage
            file_data = provider.download_file(db_file.storage_path)
            file_bytes = file_data.getvalue()
            file_size = len(file_bytes)
            
            # Base headers optimized for preview
            headers = {
                "Content-Type": db_file.mime_type,
                "Content-Disposition": f'inline; filename="{db_file.original_filename}"',
                "Accept-Ranges": "bytes",
                "Cache-Control": "max-age=86400",  # 24h cache
                "Access-Control-Allow-Origin": "*",  # CORS for allowing access from the frontend
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "Range, Content-Type, Accept, Origin, Authorization, Content-Range",
                "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges"
            }
            
            # Special case for PDFs
            if db_file.mime_type == "application/pdf":
                # PDFs need these specific headers
                headers["X-Content-Type-Options"] = "nosniff"
                
            # Special case for images
            if db_file.mime_type.startswith("image/"):
                # Make sure the image is properly cached
                headers["Cache-Control"] = "public, max-age=604800"  # 7 days
                
            # Special case for videos
            if db_file.mime_type.startswith("video/"):
                # Add specific headers for videos
                headers["X-Content-Type-Options"] = "nosniff"
                
                # Enable Cross-Origin Resource Sharing specifically for videos
                headers["Access-Control-Allow-Origin"] = "*"
                headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
                headers["Access-Control-Allow-Headers"] = "Range, Content-Type, Accept, Origin, Authorization, Content-Range"
                headers["Access-Control-Expose-Headers"] = "Content-Range, Content-Length, Accept-Ranges"
                
                # Force the use of the appropriate content-type
                if db_file.mime_type == "video/mp4":
                    headers["Content-Type"] = "video/mp4"
                elif db_file.mime_type == "video/webm":
                    headers["Content-Type"] = "video/webm"
                elif db_file.mime_type == "video/ogg":
                    headers["Content-Type"] = "video/ogg"
                elif db_file.mime_type == "video/quicktime":
                    headers["Content-Type"] = "video/mp4"  # Convertir QuickTime en MP4 pour compatibilité
            
            # If no Range header, return the complete file
            if not range_header:
                headers["Content-Length"] = str(file_size)
                return StreamingResponse(
                    io.BytesIO(file_bytes),
                    headers=headers,
                    media_type=db_file.mime_type
                )
            
            # Handle Range requests for streaming
            try:
                # Log the range header for debugging
                logger.info(f"Range header received: {range_header}")
                
                range_header = range_header.replace("bytes=", "")
                ranges = range_header.split("-")
                
                # Extract start and end
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
                
                # Verify limits
                if start < 0:
                    start = 0
                if end >= file_size:
                    end = file_size - 1
                
                # Calculate the chunk size
                chunk_size = end - start + 1
                
                # Prepare headers for partial response
                headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
                headers["Content-Length"] = str(chunk_size)
                
                # Log the response range for debugging
                logger.info(f"Serving range: bytes {start}-{end}/{file_size}")
                
                # Extract the requested chunk
                chunk = file_bytes[start:end+1]
                
                # Return a 206 (Partial Content) response
                return StreamingResponse(
                    io.BytesIO(chunk),
                    status_code=206,
                    headers=headers,
                    media_type=db_file.mime_type
                )
            
            except (ValueError, IndexError) as e:
                # In case of Range parsing error, return the complete file
                logger.warning(f"Invalid Range header: {range_header}, error: {str(e)}")
                headers["Content-Length"] = str(file_size)
                return StreamingResponse(
                    io.BytesIO(file_bytes),
                    headers=headers,
                    media_type=db_file.mime_type
                )
                
        except Exception as e:
            logger.error(f"Error previewing file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during file preview: {str(e)}")

    @router.post("/files/upload", response_model=StoredFileResponse)
    async def upload_file(
        file: UploadFile = File(...),
        provider_id: int = Form(...),
        folder_id: Optional[int] = Form(None),
        folder_path: Optional[str] = Form(None),
        description: str = Form(None),
        tags: str = Form(None),
        generate_thumbnails: bool = Form(False),
        optimize_images: bool = Form(False),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        request: Request = None
    ):
        """
        Upload a file to the configured storage
        """
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        # Optionally get the folder
        folder = None
        folder_prefix = ""
        if folder_id:
            folder = db.query(FileFolder).filter(FileFolder.id == folder_id).first()
            if not folder:
                raise HTTPException(status_code=404, detail=f"Folder with ID {folder_id} not found")
            folder_prefix = folder.name + "/"
        elif folder_path:
            folder_prefix = folder_path.strip("/") + "/"
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Prepare file content
            file_content = await file.read()
            
            # Sanitize the filename and add a unique identifier
            original_filename = file.filename
            sanitized_filename = re.sub(r'[^\w\-\.]', '_', original_filename)
            unique_id = uuid.uuid4().hex[:8]
            filename = f"{unique_id}_{sanitized_filename}"
            
            # Complete storage path including folder prefix
            storage_path = f"{folder_prefix}{filename}"
            
            # Create a BytesIO to store the file data (pour avoir un objet avec la méthode seek())
            file_data = io.BytesIO(file_content)
            
            # Upload the file to storage - correction de l'ordre des paramètres
            file_url = provider.upload_file(
                file_data,  # 1st parameter: file object with seek() method
                storage_path,  # 2nd parameter: destination path
                file.content_type  # 3rd parameter: content type
            )
            
            # Parse tags if provided
            tag_list = []
            if tags:
                tag_list = [tag.strip() for tag in tags.split(',')]
            
            # Create the file record
            db_file = StoredFile(
                provider_id=provider_id,
                filename=filename,
                original_filename=original_filename,
                storage_path=storage_path,
                file_size=len(file_content),
                mime_type=file.content_type or "application/octet-stream",
                file_metadata={
                    "description": description,
                    "tags": tag_list,
                    "url": file_url,  # Store the URL in the metadata
                    "folder_id": folder.id if folder else None  # Store the folder ID in the metadata
                }
            )
            
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
            
            # TODO: Add asynchronous thumbnail processing and optimization if necessary
            
            # Use our serialization function for the model
            file_data = serialize_sqlalchemy_model(db_file)
            
            # Log audit event for file upload
            log_audit_event(
                db=db, 
                user_id=current_user.id, 
                action="upload_file", 
                resource="file", 
                details=f"File ID: {db_file.id}, Name: {db_file.original_filename}"
            )
            
            # Return the response in the expected format by the schema
            return {"file": file_data, "message": "File uploaded successfully"}
            
        except StorageException as e:
            logger.error(f"Error during storage upload: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error during storage upload: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during storage upload: {str(e)}")
        finally:
            # Close the file
            await file.close()

    @router.delete("/files/{file_id}", response_model=dict)
    async def delete_file(
        file_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        request: Request = None
    ):
        """
        Delete a stored file and its metadata
        """
        db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get the provider
        provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
        if not provider_db:
            raise HTTPException(status_code=404, detail="Storage provider not found")
        
        try:
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Delete all thumbnails
            thumbnails = db.query(FileThumbnail).filter(FileThumbnail.original_file_id == file_id).all()
            for thumbnail in thumbnails:
                # Delete the thumbnail file from storage
                try:
                    provider.delete_file(thumbnail.storage_path)
                except Exception as e:
                    logger.warning(f"Unable to delete thumbnail {thumbnail.id}: {str(e)}")
                
                # Delete the thumbnail record
                db.delete(thumbnail)
            
            # Delete the file from storage
            provider.delete_file(db_file.storage_path)
            
            # Delete the file record
            db.delete(db_file)
            db.commit()
            
            # Log audit event for file deletion
            log_audit_event(
                db=db, 
                user_id=current_user.id, 
                action="delete_file", 
                resource="file", 
                details=f"File ID: {db_file.id}, Name: {db_file.original_filename}"
            )
            
            return {"message": "File deleted successfully"}
            
        except StorageException as e:
            db.rollback()
            logger.error(f"Storage error during file deletion: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error during file deletion: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error during file deletion: {str(e)}")

    # Implementations for folders, thumbnails, and image processing
    # will be added in separate modules to maintain code readability.


    return router

file_storage_router = get_router()
file_storage_public_router = get_public_router()