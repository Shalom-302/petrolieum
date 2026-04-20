"""
Local storage provider (file system)
"""

import io
import os
import shutil
import logging
import hashlib
import mimetypes
from typing import BinaryIO, Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import Request
from starlette.datastructures import URL

from .base import StorageProviderInterface, StorageException


class LocalStorageProvider(StorageProviderInterface):
    """
    Implementation of StorageProviderInterface for local storage
    Useful for development and testing without external services
    """
    
    def __init__(self):
        self.storage_path = None
        self.media_url_path = None
        self.request = None
        self.public_base_url = None
        self.logger = logging.getLogger(__name__)
    
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the local storage provider with the provided configuration
        
        Args:
            config: Dictionary containing:
                    - storage_path: Absolute path of the storage directory
                    - media_url_path: URL path to access files (e.g., /media)
                    - request: FastAPI Request object (optional, for generating complete URLs)
                    - public_base_url: Base public URL (optional, e.g., https://example.com)
        """
        try:
            self.storage_path = os.path.abspath(config['storage_path'])
            self.media_url_path = config.get('media_url_path', '/media')
            self.request = config.get('request')
            self.public_base_url = config.get('public_base_url')
            
            # Normalize paths
            if not self.media_url_path.startswith('/'):
                self.media_url_path = '/' + self.media_url_path
                
            if self.media_url_path.endswith('/'):
                self.media_url_path = self.media_url_path[:-1]
            
            # Create the storage directory if it doesn't exist
            if not os.path.exists(self.storage_path):
                os.makedirs(self.storage_path)
                self.logger.info(f"Storage directory created: {self.storage_path}")
                
        except Exception as e:
            error_msg = f"Error initializing local storage provider: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def _get_absolute_path(self, storage_path: str) -> str:
        """
        Convert a relative storage path to an absolute path
        """
        return os.path.join(self.storage_path, storage_path)
    
    def _ensure_directory_exists(self, storage_path: str) -> None:
        """
        Ensure the parent directory exists
        """
        directory = os.path.dirname(self._get_absolute_path(storage_path))
        os.makedirs(directory, exist_ok=True)
    
    def _get_base_url(self) -> str:
        """
        Get the base URL for files
        """
        if self.public_base_url:
            base_url = self.public_base_url
            if base_url.endswith('/'):
                base_url = base_url[:-1]
            return base_url
        elif self.request:
            base_url = str(URL(scope=self.request.scope).replace(path=""))
            return base_url
        else:
            # URL relative to the server
            return ""
    
    def upload_file(self, 
                   file_obj: BinaryIO, 
                   destination_path: str, 
                   content_type: str = None, 
                   metadata: Dict[str, str] = None) -> str:
        """
        Upload a file to local storage
        
        Args:
            file_obj: File object opened in binary mode
            destination_path: Destination path in the storage
            content_type: MIME type of the file (ignored for local storage)
            metadata: Metadata to associate with the file (stored in a .meta file)
            
        Returns:
            URL of the uploaded file
        """
        try:
            # Ensure the parent directory exists
            self._ensure_directory_exists(destination_path)
            
            # Absolute path of the file
            absolute_path = self._get_absolute_path(destination_path)
            
            # Write the file
            with open(absolute_path, 'wb') as dest_file:
                # Read in chunks to save memory
                while True:
                    chunk = file_obj.read(8192)
                    if not chunk:
                        break
                    dest_file.write(chunk)
            
            # Save metadata if provided
            if metadata:
                meta_path = absolute_path + '.meta'
                with open(meta_path, 'w') as meta_file:
                    for key, value in metadata.items():
                        meta_file.write(f"{key}={value}\n")
            
            # Return the access URL
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error uploading file to local storage: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def download_file(self, storage_path: str) -> BinaryIO:
        """
        Download a file from local storage
        
        Args:
            storage_path: Path of the file in the storage
            
        Returns:
            File object containing the data
        """
        try:
            # Absolute path of the file
            absolute_path = self._get_absolute_path(storage_path)
            
            # Check if the file exists
            if not os.path.exists(absolute_path):
                raise StorageException(f"File does not exist: {storage_path}")
            
            # Read the file into a BytesIO
            file_data = io.BytesIO()
            with open(absolute_path, 'rb') as src_file:
                file_data.write(src_file.read())
            
            # Reset the cursor to the beginning of the file
            file_data.seek(0)
            
            return file_data
            
        except Exception as e:
            error_msg = f"Error downloading file from local storage: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from local storage
        
        Args:
            storage_path: Path of the file in the storage
            
        Returns:
            True if the deletion was successful, False otherwise
        """
        try:
            # Absolute path of the file
            absolute_path = self._get_absolute_path(storage_path)
            
            # Check if the file exists
            if not os.path.exists(absolute_path):
                return False
            
            # Delete the file
            os.remove(absolute_path)
            
            # Delete the metadata file if it exists
            meta_path = absolute_path + '.meta'
            if os.path.exists(meta_path):
                os.remove(meta_path)
            
            return True
            
        except Exception as e:
            error_msg = f"Error deleting file from local storage: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def get_file_url(self, 
                    storage_path: str, 
                    expires: int = 3600, 
                    is_public: bool = False) -> str:
        """
        Get the URL for accessing a file in local storage
        
        Args:
            storage_path: Path of the file in the storage
            expires: Duration of validity in seconds (ignored for local storage)
            is_public: If the file is publicly accessible (ignored for local storage)
            
        Returns:
            URL of the file
        """
        try:
            # Encode the path for the URL
            encoded_path = quote(storage_path)
            
            # Get the base URL
            base_url = self._get_base_url()
            
            if base_url:
                return f"{base_url}{self.media_url_path}/{encoded_path}"
            else:
                return f"{self.media_url_path}/{encoded_path}"
                
        except Exception as e:
            error_msg = f"Error generating URL for local file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in local storage
        
        Args:
            storage_path: Path of the file in the storage
            
        Returns:
            True if the file exists, False otherwise
        """
        absolute_path = self._get_absolute_path(storage_path)
        return os.path.exists(absolute_path) and os.path.isfile(absolute_path)
    
    def get_file_metadata(self, storage_path: str) -> Dict[str, Any]:
        """
        Get the metadata of a file in local storage
        
        Args:
            storage_path: Path of the file in the storage
            
        Returns:
            Dictionary containing the file metadata
        """
        try:
            # Absolute path of the file
            absolute_path = self._get_absolute_path(storage_path)
            
            # Check if the file exists
            if not os.path.exists(absolute_path):
                raise StorageException(f"File does not exist: {storage_path}")
            
            # Get file statistics
            file_stat = os.stat(absolute_path)
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(absolute_path)
            content_type = content_type or 'application/octet-stream'
            
            # Load custom metadata if it exists
            metadata = {}
            meta_path = absolute_path + '.meta'
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as meta_file:
                    for line in meta_file:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            metadata[key] = value
            
            # Calculate file hash (SHA-256)
            file_hash = ''
            with open(absolute_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            return {
                'size': file_stat.st_size,
                'last_modified': datetime.fromtimestamp(file_stat.st_mtime),
                'created': datetime.fromtimestamp(file_stat.st_ctime),
                'etag': file_hash,
                'content_type': content_type,
                'metadata': metadata
            }
            
        except Exception as e:
            error_msg = f"Error retrieving metadata: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def list_files(self, prefix: str = "", recursive: bool = True) -> List[Dict[str, Any]]:
        """
        List files in a directory of local storage
        
        Args:
            prefix: Prefix to filter results
            recursive: If the search should be recursive
            
        Returns:
            List of dictionaries containing file information
        """
        try:
            result = []
            root_path = self.storage_path
            prefix_path = os.path.join(root_path, prefix) if prefix else root_path
            
            if not os.path.exists(prefix_path):
                return result
            
            if recursive:
                # Recursive search
                for root, dirs, files in os.walk(prefix_path):
                    for file in files:
                        # Ignore metadata files
                        if file.endswith('.meta'):
                            continue
                            
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, root_path)
                        
                        # Get file statistics
                        file_stat = os.stat(abs_path)
                        
                        result.append({
                            'name': rel_path,
                            'size': file_stat.st_size,
                            'last_modified': datetime.fromtimestamp(file_stat.st_mtime),
                            'etag': hashlib.md5(rel_path.encode()).hexdigest(),
                            'is_dir': False
                        })
            else:
                # Non-recursive search
                for item in os.listdir(prefix_path):
                    abs_path = os.path.join(prefix_path, item)
                    rel_path = os.path.relpath(abs_path, root_path)
                    
                    if os.path.isfile(abs_path) and not item.endswith('.meta'):
                        # File
                        file_stat = os.stat(abs_path)
                        
                        result.append({
                            'name': rel_path,
                            'size': file_stat.st_size,
                            'last_modified': datetime.fromtimestamp(file_stat.st_mtime),
                            'etag': hashlib.md5(rel_path.encode()).hexdigest(),
                            'is_dir': False
                        })
                    elif os.path.isdir(abs_path):
                        # Directory
                        result.append({
                            'name': rel_path + '/',  # Add a slash to indicate a directory
                            'size': 0,
                            'last_modified': datetime.fromtimestamp(os.path.getmtime(abs_path)),
                            'etag': hashlib.md5(rel_path.encode()).hexdigest(),
                            'is_dir': True
                        })
                
            return result
            
        except Exception as e:
            error_msg = f"Error listing files: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def update_file_metadata(self, storage_path: str, metadata: Dict[str, str]) -> bool:
        """
        Update the metadata of a file in local storage
        
        Args:
            storage_path: Path of the file in the storage
            metadata: New metadata
            
        Returns:
            True if the update was successful, False otherwise
        """
        try:
            # Absolute path of the file
            absolute_path = self._get_absolute_path(storage_path)
            
            # Check if the file exists
            if not os.path.exists(absolute_path):
                return False
            
            # Path of the metadata file
            meta_path = absolute_path + '.meta'
            
            # Load existing metadata if it exists
            current_metadata = {}
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as meta_file:
                    for line in meta_file:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            current_metadata[key] = value
            
            # Merge with new metadata
            merged_metadata = {**current_metadata, **metadata}
            
            # Save metadata
            with open(meta_path, 'w') as meta_file:
                for key, value in merged_metadata.items():
                    meta_file.write(f"{key}={value}\n")
            
            return True
            
        except Exception as e:
            error_msg = f"Error updating metadata: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def copy_file(self, source_path: str, destination_path: str) -> str:
        """
        Copy a file to local storage
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            URL of the copied file
        """
        try:
            # Absolute paths of the files
            source_absolute_path = self._get_absolute_path(source_path)
            destination_absolute_path = self._get_absolute_path(destination_path)
            
            # Check if the source file exists
            if not os.path.exists(source_absolute_path):
                raise StorageException(f"The source file does not exist: {source_path}")
            
            # Create the destination directory if necessary
            self._ensure_directory_exists(destination_path)
            
            # Copy the file
            shutil.copy2(source_absolute_path, destination_absolute_path)
            
            # Copy the metadata if it exists
            source_meta_path = source_absolute_path + '.meta'
            destination_meta_path = destination_absolute_path + '.meta'
            
            if os.path.exists(source_meta_path):
                shutil.copy2(source_meta_path, destination_meta_path)
            
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error copying file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def move_file(self, source_path: str, destination_path: str) -> str:
        """
        Move a file to local storage
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            URL of the moved file
        """
        try:
            # Absolute paths of the files
            source_absolute_path = self._get_absolute_path(source_path)
            destination_absolute_path = self._get_absolute_path(destination_path)
            
            # Check if the source file exists
            if not os.path.exists(source_absolute_path):
                raise StorageException(f"The source file does not exist: {source_path}")
            
            # Create the destination directory if necessary
            self._ensure_directory_exists(destination_path)
            
            # Move the file
            shutil.move(source_absolute_path, destination_absolute_path)
            
            # Move the metadata if it exists
            source_meta_path = source_absolute_path + '.meta'
            destination_meta_path = destination_absolute_path + '.meta'
            
            if os.path.exists(source_meta_path):
                shutil.move(source_meta_path, destination_meta_path)
            
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error moving file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
