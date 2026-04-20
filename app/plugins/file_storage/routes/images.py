"""
Routes for image processing
"""

import io
import os
import uuid
import logging
from typing import Dict, List, Optional, Any, BinaryIO, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.advanced_auth.models import User

from ..models import StoredFile, FileThumbnail, StorageProvider, get_provider_instance
from ..schemas import FileThumbnailCreate, FileThumbnailResponse
from ..utils.image_processor import ImageProcessor
from ..providers import StorageException

router = APIRouter(prefix="/images")

logger = logging.getLogger(__name__)

@router.post("/{file_id}/thumbnails", response_model=Dict[str, FileThumbnailResponse])
async def generate_thumbnails(
    file_id: int,
    sizes: Optional[List[str]] = Query(["sm", "md", "lg"]),
    format: Optional[str] = None,
    quality: int = 85,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Generate thumbnails for an existing image
    
    Args:
        file_id: ID of the image file
        sizes: Sizes of thumbnails to generate (xs, sm, md, lg or dimensions AxB)
        format: Output format (jpeg, png, webp)
        quality: Output compression quality (1-100)
        
    Returns:
        Dictionary of generated thumbnails with their metadata
    """
    # Retrieve the file
    db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if it's an image
    if not db_file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail=f"The file is not an image (type: {db_file.content_type})"
        )
    
    # Get the storage provider
    provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
    if not provider_db:
        raise HTTPException(status_code=404, detail="Storage provider not found")
    
    try:
        # Get the provider instance
        provider = get_provider_instance(provider_db, request)
        
        # Download the file from storage
        file_data = provider.download_file(db_file.storage_path)
        
        # Determine the output format
        if not format:
            # Use the original image format
            if db_file.content_type == "image/jpeg":
                format = "jpeg"
            elif db_file.content_type == "image/png":
                format = "png"
            elif db_file.content_type == "image/webp":
                format = "webp"
            else:
                # Default to JPEG
                format = "jpeg"
        
        # Generate thumbnails
        thumbnails_result = ImageProcessor.generate_thumbnails(
            file_data, 
            sizes=sizes, 
            format=format, 
            quality=quality
        )
        
        # Store the thumbnails and create database records
        result = {}
        
        for size_key, (thumbnail_data, metadata) in thumbnails_result.items():
            # Thumbnail filename
            ext = metadata["format"]
            thumbnail_filename = f"{os.path.splitext(db_file.storage_path)[0]}_thumb_{size_key}.{ext}"
            
            # Upload the thumbnail
            content_type = f"image/{ext}"
            if ext == "jpg":
                content_type = "image/jpeg"
                
            thumbnail_url = provider.upload_file(
                thumbnail_data, 
                thumbnail_filename, 
                content_type=content_type
            )
            
            # Check if a thumbnail with this name already exists
            existing_thumbnail = db.query(FileThumbnail).filter(
                FileThumbnail.file_id == file_id,
                FileThumbnail.size == size_key
            ).first()
            
            if existing_thumbnail:
                # Update the existing thumbnail
                existing_thumbnail.storage_path = thumbnail_filename
                existing_thumbnail.file_url = thumbnail_url
                existing_thumbnail.width = metadata["width"]
                existing_thumbnail.height = metadata["height"]
                existing_thumbnail.file_size = metadata["file_size"]
                db.commit()
                db.refresh(existing_thumbnail)
                thumbnail_record = existing_thumbnail
            else:
                # Create a new thumbnail record
                thumbnail_record = FileThumbnail(
                    file_id=file_id,
                    size=size_key,
                    storage_path=thumbnail_filename,
                    file_url=thumbnail_url,
                    width=metadata["width"],
                    height=metadata["height"],
                    file_size=metadata["file_size"],
                    created_by=current_user.id
                )
                db.add(thumbnail_record)
                db.commit()
                db.refresh(thumbnail_record)
            
            # Add to result
            result[size_key] = thumbnail_record
        
        return result
        
    except StorageException as e:
        logger.error(f"Error storing thumbnails: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during thumbnail generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/transform", response_model=Dict[str, Any])
async def transform_image(
    image: UploadFile = File(...),
    operations: str = Form(...),  # JSON with list of operations
    output_format: str = Form("jpeg"),
    output_quality: int = Form(85),
    save_result: bool = Form(False),
    provider_id: Optional[int] = Form(None),
    folder_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Transform an image according to a list of operations
    
    Args:
        image: Image file to transform
        operations: List of transformation operations (JSON)
        output_format: Output format (jpeg, png, webp)
        output_quality: Output compression quality (1-100)
        save_result: If the result should be saved
        provider_id: Storage provider ID (for saving)
        folder_path: Destination folder path (for saving)
        
    Returns:
        Metadata of the transformed image and URL if saved
    """
    try:
        # Read the image content
        content = await image.read()
        image_data = io.BytesIO(content)
        
        # Interpret the list of operations JSON
        import json
        try:
            operations_list = json.loads(operations)
            if not isinstance(operations_list, list):
                operations_list = [operations_list]
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid JSON format for operations"
            )
        
        # Transform the image
        transformed_data, metadata = ImageProcessor.transform_image(
            image_data,
            operations_list,
            output_format=output_format,
            output_quality=output_quality
        )
        
        # If save_result is True, save the transformed image
        result_url = None
        db_file = None
        
        if save_result and provider_id:
            # Get the provider
            provider_db = db.query(StorageProvider).filter(StorageProvider.id == provider_id).first()
            if not provider_db:
                raise HTTPException(status_code=404, detail="Storage provider not found")
            
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Prepare the destination path
            filename = image.filename
            base_name, _ = os.path.splitext(filename)
            file_extension = f".{output_format.lower()}"
            if output_format.lower() == "jpeg":
                file_extension = ".jpg"
                
            storage_path = f"{folder_path or ''}/{base_name}_transformed_{uuid.uuid4().hex[:8]}{file_extension}"
            storage_path = storage_path.replace('//', '/')
            if storage_path.startswith('/'):
                storage_path = storage_path[1:]
            
            # Create base metadata
            file_metadata = {
                "original_filename": filename,
                "transformed": "true",
                "operations": operations,
                "uploaded_by": str(current_user.id)
            }
            
            # Upload the transformed file
            content_type = f"image/{output_format.lower()}"
            if output_format.lower() == "jpeg":
                content_type = "image/jpeg"
                
            result_url = provider.upload_file(
                transformed_data, 
                storage_path, 
                content_type=content_type, 
                metadata=file_metadata
            )
            
            # Create database record
            file_size = transformed_data.getbuffer().nbytes
            
            db_file = StoredFile(
                provider_id=provider_id,
                storage_path=storage_path,
                original_filename=f"{base_name}_transformed{file_extension}",
                file_url=result_url,
                file_size=file_size,
                content_type=content_type,
                description=f"Image transformed from {filename}",
                tags=["transformed"],
                created_by=current_user.id
            )
            
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
        
        # If save_result is False, return the transformed image directly
        if not save_result:
            # Reset the cursor to the start of the file
            transformed_data.seek(0)
            
            # Determine the MIME type
            content_type = f"image/{output_format.lower()}"
            if output_format.lower() == "jpeg":
                content_type = "image/jpeg"
                
            # Return the transformed image
            return StreamingResponse(
                iter([transformed_data.getvalue()]), 
                media_type=content_type
            )
        
        # Otherwise, return the metadata and URL
        return {
            "metadata": metadata,
            "file_url": result_url,
            "file_id": db_file.id if db_file else None,
            "storage_path": db_file.storage_path if db_file else None
        }
        
    except Exception as e:
        logger.error(f"Error during image transformation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        # Close the file
        await image.close()

@router.post("/optimize", response_model=Dict[str, Any])
async def optimize_image(
    image: UploadFile = File(...),
    output_format: Optional[str] = Form(None),
    quality: int = Form(85),
    max_width: Optional[int] = Form(None),
    max_height: Optional[int] = Form(None),
    save_result: bool = Form(False),
    provider_id: Optional[int] = Form(None),
    folder_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Optimize an image for the web
    
    Args:
        image: Image file to optimize
        output_format: Output format (jpeg, png, webp)
        quality: Compression quality (1-100)
        max_width: Maximum width
        max_height: Maximum height
        save_result: If the result should be saved
        provider_id: Storage provider ID (for saving)
        folder_path: Destination folder path (for saving)
        
    Returns:
        Metadata of the optimized image and URL if saved
    """
    try:
        # Read the image content
        content = await image.read()
        image_data = io.BytesIO(content)
        
        # Determine the maximum size
        max_size = None
        if max_width or max_height:
            max_width = max_width or 10000
            max_height = max_height or 10000
            max_size = (max_width, max_height)
        
        # Optimize the image
        optimized_data, metadata = ImageProcessor.optimize_image(
            image_data,
            output_format=output_format,
            quality=quality,
            max_size=max_size
        )
        
        # If save_result is True, save the optimized image
        result_url = None
        db_file = None
        
        if save_result and provider_id:
            # Get the provider
            provider_db = db.query(StorageProvider).filter(StorageProvider.id == provider_id).first()
            if not provider_db:
                raise HTTPException(status_code=404, detail="Storage provider not found")
            
            # Get the provider instance
            provider = get_provider_instance(provider_db, request)
            
            # Prepare the destination path
            filename = image.filename
            base_name, _ = os.path.splitext(filename)
            file_extension = f".{metadata['format']}"
            if metadata['format'] == "jpeg":
                file_extension = ".jpg"
                
            storage_path = f"{folder_path or ''}/{base_name}_optimized_{uuid.uuid4().hex[:8]}{file_extension}"
            storage_path = storage_path.replace('//', '/')
            if storage_path.startswith('/'):
                storage_path = storage_path[1:]
            
            # Create base metadata
            file_metadata = {
                "original_filename": filename,
                "optimized": "true",
                "original_size": str(metadata.get("original_size")),
                "compression_ratio": str(metadata.get("compression_ratio")),
                "uploaded_by": str(current_user.id)
            }
            
            # Upload the optimized file
            content_type = f"image/{metadata['format']}"
            if metadata['format'] == "jpeg":
                content_type = "image/jpeg"
                
            result_url = provider.upload_file(
                optimized_data, 
                storage_path, 
                content_type=content_type, 
                metadata=file_metadata
            )
            
            # Create database record
            file_size = optimized_data.getbuffer().nbytes
            
            db_file = StoredFile(
                provider_id=provider_id,
                storage_path=storage_path,
                original_filename=f"{base_name}_optimized{file_extension}",
                file_url=result_url,
                file_size=file_size,
                content_type=content_type,
                description=f"Image optimized from {filename}",
                tags=["optimized"],
                created_by=current_user.id
            )
            
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
        
        # If save_result is False, return the optimized image directly
        if not save_result:
            # Reset the cursor to the start of the file
            optimized_data.seek(0)
            
            # Determine the MIME type
            content_type = f"image/{metadata['format']}"
            if metadata['format'] == "jpeg":
                content_type = "image/jpeg"
                
            # Return the optimized image
            return StreamingResponse(
                iter([optimized_data.getvalue()]), 
                media_type=content_type
            )
        
        # Otherwise, return the metadata and URL
        return {
            "metadata": metadata,
            "file_url": result_url,
            "file_id": db_file.id if db_file else None,
            "storage_path": db_file.storage_path if db_file else None,
            "compression_ratio": metadata.get("compression_ratio")
        }
        
    except Exception as e:
        logger.error(f"Error during image optimization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        # Close the file
        await image.close()

@router.get("/{file_id}/info", response_model=Dict[str, Any])
async def get_image_info(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Get detailed information about an image
    
    Args:
        file_id: ID of the image file
        
    Returns:
        Detailed information about the image (dimensions, format, etc.)
    """
    # Get the file
    db_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if it's an image
    if not db_file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail=f"The file is not an image (type: {db_file.content_type})"
        )
    
    # Get the provider
    provider_db = db.query(StorageProvider).filter(StorageProvider.id == db_file.provider_id).first()
    if not provider_db:
        raise HTTPException(status_code=404, detail="Storage provider not found")
    
    try:
        # Get the provider instance
        provider = get_provider_instance(provider_db, request)
        
        # Download the file from storage
        file_data = provider.download_file(db_file.storage_path)
        
        # Get image information
        image_info = ImageProcessor.get_image_info(file_data)
        
        # Get thumbnails
        thumbnails = db.query(FileThumbnail).filter(FileThumbnail.file_id == file_id).all()
        thumbnail_info = {
            thumbnail.size: {
                "url": thumbnail.file_url,
                "width": thumbnail.width,
                "height": thumbnail.height,
                "size": thumbnail.file_size
            }
            for thumbnail in thumbnails
        }
        
        # Add file information
        result = {
            "file_id": db_file.id,
            "original_filename": db_file.original_filename,
            "content_type": db_file.content_type,
            "file_size": db_file.file_size,
            "created_at": db_file.created_at,
            "storage_path": db_file.storage_path,
            "image": image_info,
            "thumbnails": thumbnail_info
        }
        
        return result
        
    except StorageException as e:
        logger.error(f"Storage error while retrieving information: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error while retrieving information: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
