"""
File Handler for Messaging Service

This module implements file handling for message attachments,
including secure storage, validation, and retrieval.
"""
import logging
import os
import shutil
import uuid
import hashlib
import mimetypes
from typing import Dict, Any, List, Optional, BinaryIO, Tuple
from fastapi import UploadFile
from PIL import Image
import io

# Get messaging service instance to access security handler
from ..main import messaging_service

logger = logging.getLogger(__name__)


class MessageFileHandler:
    """
    File handler for message attachments, ensuring secure storage and
    validation following the standardized security approach.
    """
    
    def __init__(self, max_file_size_mb: int = 20, allowed_file_types: List[str] = None):
        """
        Initialize the file handler.
        
        Args:
            max_file_size_mb: Maximum file size in MB
            allowed_file_types: List of allowed MIME types
        """
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert to bytes
        self.allowed_file_types = allowed_file_types or [
            "image/jpeg", "image/png", "image/gif", "application/pdf", 
            "text/plain", "application/msword", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]
        self.base_upload_dir = os.path.join(os.getcwd(), "uploads", "messaging")
        self.security_handler = None
        
        # Create base directory if it doesn't exist
        os.makedirs(self.base_upload_dir, exist_ok=True)
    
    def set_security_handler(self, security_handler):
        """
        Set the security handler for secure file operations.
        
        Args:
            security_handler: Security handler from the messaging service
        """
        self.security_handler = security_handler
    
    async def save_attachment(self, file: UploadFile, user_id: str, 
                            conversation_id: str) -> Dict[str, Any]:
        """
        Save a file attachment securely.
        
        Args:
            file: File to save
            user_id: ID of the uploading user
            conversation_id: ID of the conversation
            
        Returns:
            Dictionary with attachment information
            
        Raises:
            ValueError: If file validation fails
        """
        # Validate the file using standardized approach
        await self._validate_file(file)
        
        # Generate a secure filename
        original_filename = file.filename
        filename = self._generate_secure_filename(original_filename, user_id)
        
        # Determine the storage path
        file_path = self._get_file_path(filename, conversation_id)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save the file
        file_size = await self._save_file(file, file_path)
        
        # Generate thumbnail if it's an image
        thumbnail_path = None
        is_image = file.content_type and file.content_type.startswith("image/")
        
        if is_image:
            thumbnail_path = await self._generate_thumbnail(file_path, filename, conversation_id)
        
        # Log the file upload using standardized security approach
        if self.security_handler:
            self.security_handler.secure_log(
                "File attachment saved",
                {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "file_size": file_size,
                    "file_type": file.content_type,
                    "is_image": is_image
                }
            )
        
        # Return attachment information
        return {
            "id": str(uuid.uuid4()),
            "file_name": original_filename,
            "file_type": file.content_type,
            "file_size": file_size,
            "file_path": file_path,
            "is_image": is_image,
            "thumbnail_path": thumbnail_path
        }
        
    async def delete_attachment(self, file_path: str, thumbnail_path: Optional[str] = None):
        """
        Delete a file attachment securely.
        
        Args:
            file_path: Path to the file to delete
            thumbnail_path: Optional path to thumbnail to delete
        """
        # Delete the main file
        if os.path.exists(file_path):
            os.unlink(file_path)
            
        # Delete the thumbnail if it exists
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.unlink(thumbnail_path)
            
        # Log the deletion using standardized security approach
        if self.security_handler:
            self.security_handler.secure_log(
                "File attachment deleted",
                {
                    "file_path": file_path
                }
            )
    
    async def _validate_file(self, file: UploadFile):
        """
        Validate a file using standardized security approach.
        
        Args:
            file: File to validate
            
        Raises:
            ValueError: If validation fails
        """
        # Check file size
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)  # Reset position
        
        if file_size > self.max_file_size:
            error_msg = f"File size exceeds maximum allowed ({file_size} > {self.max_file_size})"
            if self.security_handler:
                self.security_handler.secure_log(
                    "File validation failed - size",
                    {"error": error_msg},
                    "warning"
                )
            raise ValueError(error_msg)
        
        # Check file type
        content_type = file.content_type
        if content_type not in self.allowed_file_types:
            error_msg = f"File type not allowed: {content_type}"
            if self.security_handler:
                self.security_handler.secure_log(
                    "File validation failed - type",
                    {"error": error_msg},
                    "warning"
                )
            raise ValueError(error_msg)
        
        # Check file extension
        filename = file.filename
        extension = os.path.splitext(filename)[1].lower()
        allowed_extensions = self._get_allowed_extensions()
        
        if extension not in allowed_extensions:
            error_msg = f"File extension not allowed: {extension}"
            if self.security_handler:
                self.security_handler.secure_log(
                    "File validation failed - extension",
                    {"error": error_msg},
                    "warning"
                )
            raise ValueError(error_msg)
        
        # For security, we also verify the actual content matches the declared type
        # This is a simplified check, in a real system you might use libraries like python-magic
        content_sample = await file.read(2048)  # Read a sample
        file.file.seek(0)  # Reset position
        
        # Simplified detection for common file types
        if content_type.startswith("image/"):
            try:
                Image.open(io.BytesIO(content_sample))
            except Exception:
                error_msg = "File content doesn't match declared image type"
                if self.security_handler:
                    self.security_handler.secure_log(
                        "File validation failed - content mismatch",
                        {"error": error_msg},
                        "warning"
                    )
                raise ValueError(error_msg)
    
    def _get_allowed_extensions(self) -> List[str]:
        """
        Get list of allowed file extensions based on allowed MIME types.
        
        Returns:
            List of allowed extensions
        """
        allowed_extensions = []
        
        for mime_type in self.allowed_file_types:
            # Get all extensions for this MIME type
            extensions = mimetypes.guess_all_extensions(mime_type)
            allowed_extensions.extend(extensions)
        
        return allowed_extensions
    
    def _generate_secure_filename(self, original_filename: str, user_id: str) -> str:
        """
        Generate a secure filename using standardized security approach.
        
        Args:
            original_filename: Original filename
            user_id: ID of the uploading user
            
        Returns:
            Secure filename
        """
        # Get extension
        extension = os.path.splitext(original_filename)[1].lower()
        
        # Generate a secure base name using a UUID and a hash of user_id
        user_id_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
        timestamp = str(int(uuid.uuid1().time))
        random_component = str(uuid.uuid4())[:8]
        
        # Combine components
        secure_name = f"{user_id_hash}_{timestamp}_{random_component}{extension}"
        
        return secure_name
    
    def _get_file_path(self, filename: str, conversation_id: str) -> str:
        """
        Get the file path for an attachment.
        
        Args:
            filename: Filename
            conversation_id: ID of the conversation
            
        Returns:
            Full file path
        """
        # Create a directory structure based on conversation ID
        # This helps organize files and limit directory size
        conversation_hash = hashlib.md5(conversation_id.encode()).hexdigest()
        dir_path = os.path.join(
            self.base_upload_dir,
            conversation_hash[:2],
            conversation_hash[2:4],
            conversation_id
        )
        
        return os.path.join(dir_path, filename)
    
    async def _save_file(self, file: UploadFile, file_path: str) -> int:
        """
        Save a file to disk.
        
        Args:
            file: File to save
            file_path: Path to save to
            
        Returns:
            Size of the saved file in bytes
        """
        # Create a temporary file first
        temp_file_path = f"{file_path}.tmp"
        
        with open(temp_file_path, "wb") as buffer:
            # Save in chunks to handle large files efficiently
            chunk_size = 65536  # 64 KB
            file_size = 0
            
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                    
                buffer.write(chunk)
                file_size += len(chunk)
        
        # Now move the temp file to the final location
        # This ensures the operation is atomic
        shutil.move(temp_file_path, file_path)
        
        return file_size
    
    async def _generate_thumbnail(self, image_path: str, filename: str, 
                               conversation_id: str, size: Tuple[int, int] = (200, 200)) -> Optional[str]:
        """
        Generate a thumbnail for an image.
        
        Args:
            image_path: Path to the original image
            filename: Original secure filename
            conversation_id: ID of the conversation
            size: Thumbnail size
            
        Returns:
            Path to the thumbnail or None if generation fails
        """
        try:
            # Generate thumbnail path
            name, extension = os.path.splitext(filename)
            thumbnail_filename = f"{name}_thumb{extension}"
            thumbnail_path = self._get_file_path(thumbnail_filename, conversation_id)
            
            # Create thumbnail
            img = Image.open(image_path)
            img.thumbnail(size)
            
            # Save thumbnail
            img.save(thumbnail_path)
            
            return thumbnail_path
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            return None
