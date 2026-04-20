"""
MinIO storage provider
"""

import io
import os
import uuid
import logging
from typing import BinaryIO, Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
import mimetypes

from minio import Minio
from minio.error import S3Error
from minio.commonconfig import ComposeSource

from .base import StorageProviderInterface, StorageException


class MinioStorageProvider(StorageProviderInterface):
    """
    Implementation of StorageProviderInterface for MinIO
    """
    
    def __init__(self):
        self.client = None
        self.bucket = None
        self.endpoint = None
        self.logger = logging.getLogger(__name__)
        self.public_endpoint_url = None
    
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the provider with configuration options
        
        Args:
            config: Configuration options
                - endpoint_url: MinIO server endpoint URL
                - bucket_name: Bucket name
                - access_key: MinIO access key
                - secret_key: MinIO secret key
                - region: Region (optional)
                - secure: Whether to use HTTPS
                - public_endpoint_url: Public endpoint URL for direct file access (optional)
        
        Raises:
            StorageException: If the initialization fails
        """
        try:
            # Get configuration options
            endpoint_url = config.get("endpoint_url")
            bucket_name = config.get("bucket_name")
            access_key = config.get("access_key")
            secret_key = config.get("secret_key")
            region = config.get("region")
            secure = config.get("secure", False)
            self.public_endpoint_url = config.get("public_endpoint_url")
            
            # Validate required options
            if not all([endpoint_url, bucket_name, access_key, secret_key]):
                raise StorageException("MinIO provider requires 'endpoint_url', 'bucket_name', 'access_key', and 'secret_key'")
            
            # Save configuration
            self.endpoint = endpoint_url
            self.bucket = bucket_name
            self.secure = secure
            
            # Initialize MinIO client
            self.client = Minio(
                endpoint_url.replace('http://', '').replace('https://', ''),
                access_key=access_key,
                secret_key=secret_key,
                region=region,
                secure=secure
            )
            
            # Create bucket if it doesn't exist
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                
            self.logger.info(f"MinIO provider initialized with bucket '{bucket_name}'")
            
        except Exception as e:
            error_msg = f"Error initializing MinIO provider: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def upload_file(self, 
                   file_obj: BinaryIO, 
                   destination_path: str, 
                   content_type: str = None, 
                   metadata: Dict[str, str] = None) -> str:
        """
        Upload a file to MinIO
        
        Args:
            file_obj: File object opened in binary mode
            destination_path: Destination path in MinIO
            content_type: MIME type of the file
            metadata: Métadonnées à associer au fichier
            
        Returns:
            URL of the uploaded file
        """
        try:
            # Determine content type if not specified
            if not content_type:
                content_type, _ = mimetypes.guess_type(destination_path)
                content_type = content_type or 'application/octet-stream'
            
            # Determine file size
            file_size = file_obj.seek(0, os.SEEK_END)
            file_obj.seek(0)
            
            # Upload the file
            result = self.client.put_object(
                bucket_name=self.bucket,
                object_name=destination_path,
                data=file_obj,
                length=file_size,
                content_type=content_type,
                metadata=metadata
            )
            
            # Construct the access URL
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error uploading file to MinIO: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def download_file(self, storage_path: str) -> BinaryIO:
        """
        Download a file from MinIO
        
        Args:
            storage_path: Path of the file in MinIO
            
        Returns:
            File object containing the data
        """
        try:
            response = self.client.get_object(
                bucket_name=self.bucket,
                object_name=storage_path
            )
            
            # Create a BytesIO object to store the data
            file_data = io.BytesIO()
            for data in response.stream(32*1024):
                file_data.write(data)
            
            # Reset the cursor to the beginning of the file
            file_data.seek(0)
            
            return file_data
            
        except Exception as e:
            error_msg = f"Error downloading file from MinIO: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from MinIO
        
        Args:
            storage_path: Path of the file in MinIO
            
        Returns:
            True if the deletion was successful, False otherwise
        """
        try:
            self.client.remove_object(
                bucket_name=self.bucket,
                object_name=storage_path
            )
            return True
            
        except Exception as e:
            error_msg = f"Error deleting file from MinIO: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def get_file_url(self, 
                    storage_path: str, 
                    expires: int = 3600, 
                    is_public: bool = False,
                    request=None) -> str:
        """
        Génère une URL pour accéder au fichier (présignée ou publique)
        
        Args:
            storage_path: Chemin du fichier dans le stockage
            expires: Durée de validité de l'URL en secondes
            is_public: Si vrai, retourne une URL publique non présignée
            request: Requête HTTP (utilisée pour générer des URLs absolues si nécessaire)
            
        Returns:
            URL d'accès au fichier
        """
        try:
            # Si nous avons un endpoint public configuré, retourner l'URL publique
            if self.public_endpoint_url:
                # Pour un accès depuis le navigateur, nous devons utiliser localhost ou une URL publique
                # au lieu de 'minio' qui est le nom du service dans le réseau Docker
                public_url = f"{self.public_endpoint_url.rstrip('/')}/{storage_path}"
                
                # Remplacer 'minio:9000' par 'localhost:9000' si l'URL contient minio
                if 'minio:9000' in public_url:
                    public_url = public_url.replace('minio:9000', 'localhost:9000')
                
                return public_url
            
            # Convert expiry from seconds (int) to timedelta
            expiry_delta = timedelta(seconds=expires)
            
            # Sinon, générer une URL présignée
            url = self.client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=storage_path,
                expires=expiry_delta
            )
            
            # Always replace minio:9000 with localhost:9000 for browser access
            if 'minio:9000' in url:
                url = url.replace('minio:9000', 'localhost:9000')
                
            return url
            
        except Exception as e:
            self.logger.error(f"Error generating file URL: {str(e)}")
            return ""
    
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in MinIO
        
        Args:
            storage_path: Path of the file in MinIO
            
        Returns:
            True if the file exists, False otherwise
        """
        try:
            self.client.stat_object(
                bucket_name=self.bucket,
                object_name=storage_path
            )
            return True
            
        except Exception:
            return False
    
    def get_file_metadata(self, storage_path: str) -> Dict[str, Any]:
        """
        Get the metadata of a file in MinIO
        
        Args:
            storage_path: Path of the file in MinIO
            
        Returns:
            Dictionary containing the metadata
        """
        try:
            stat = self.client.stat_object(
                bucket_name=self.bucket,
                object_name=storage_path
            )
            
            return {
                "size": stat.size,
                "last_modified": stat.last_modified,
                "etag": stat.etag,
                "metadata": stat.metadata
            }
            
        except Exception as e:
            error_msg = f"Error getting file metadata from MinIO: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def generate_presigned_url(self, storage_path: str, expiry: int = 3600, extra_params: Dict[str, str] = None) -> str:
        """
        Generate a presigned URL with custom response parameters for streaming and preview
        
        Args:
            storage_path: Path of the file in MinIO
            expiry: Expiry time in seconds
            extra_params: Additional response parameters for the S3 GetObject operation
                - ResponseContentDisposition: Content-Disposition header
                - ResponseContentType: Content-Type header
                - ResponseCacheControl: Cache-Control header
                
        Returns:
            Presigned URL with custom response parameters
        """
        try:
            # Default to empty dict if extra_params is None
            params = extra_params or {}
            
            # Check if we should use the public endpoint
            if self.public_endpoint_url and len(params) == 0:
                # For browser access, we need to use localhost or a public URL
                # instead of 'minio' which is the service name in the Docker network
                public_url = f"{self.public_endpoint_url.rstrip('/')}/{storage_path}"
                
                # Replace 'minio:9000' with 'localhost:9000' if the URL contains minio
                if 'minio:9000' in public_url:
                    public_url = public_url.replace('minio:9000', 'localhost:9000')
                
                return public_url
            
            # Convert expiry from seconds (int) to timedelta
            expiry_delta = timedelta(seconds=expiry)
            
            # Generate a presigned URL with custom response parameters
            url = self.client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=storage_path,
                expires=expiry_delta,
                response_headers=params
            )
            
            # Always replace minio:9000 with localhost:9000 for browser access
            if 'minio:9000' in url:
                url = url.replace('minio:9000', 'localhost:9000')
                
            return url
            
        except Exception as e:
            error_msg = f"Error generating presigned URL: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def get_file_content(self, storage_path: str) -> bytes:
        """
        Download the content of a file from MinIO
        
        Args:
            storage_path: Path of the file in MinIO
            
        Returns:
            File content as bytes
        """
        try:
            response = self.client.get_object(
                bucket_name=self.bucket,
                object_name=storage_path
            )
            
            # Read the data from the response
            data = response.read()
            
            return data
            
        except Exception as e:
            error_msg = f"Error downloading file content from MinIO: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def list_files(self, prefix: str = "", recursive: bool = True) -> List[Dict[str, Any]]:
        """
        List files in a MinIO directory
        
        Args:
            prefix: Prefix to filter results
            recursive: If the search should be recursive
            
        Returns:
            List of dictionaries containing file information
        """
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket,
                prefix=prefix,
                recursive=recursive
            )
            
            result = []
            for obj in objects:
                result.append({
                    'name': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified,
                    'etag': obj.etag,
                    'is_dir': obj.is_dir
                })
                
            return result
            
        except Exception as e:
            error_msg = f"Error listing files: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def update_file_metadata(self, storage_path: str, metadata: Dict[str, str]) -> bool:
        """
        Update the metadata of a file in MinIO
        Note: MinIO does not allow updating metadata directly,
        it must copy the file with the new metadata
        
        Args:
            storage_path: Path of the file in MinIO
            metadata: New metadata
            
        Returns:
            True if the update was successful, False otherwise
        """
        try:
            # Get the current metadata
            current_metadata = self.get_file_metadata(storage_path)
            
            # Create a temporary name for the copy
            temp_path = f"{storage_path}.temp-{uuid.uuid4()}"
            
            # Copy the object with the new metadata
            copy_source = ComposeSource(
                bucket_name=self.bucket,
                object_name=storage_path
            )
            
            # Merge the current metadata with the new metadata
            merged_metadata = {**current_metadata.get('metadata', {}), **metadata}
            
            # Copy the object with the new metadata
            self.client.copy_object(
                bucket_name=self.bucket,
                object_name=temp_path,
                source=copy_source,
                metadata=merged_metadata,
                metadata_directive="REPLACE"
            )
            
            # Delete the original
            self.client.remove_object(
                bucket_name=self.bucket,
                object_name=storage_path
            )
            
            # Rename the copy to the original name
            copy_source = ComposeSource(
                bucket_name=self.bucket,
                object_name=temp_path
            )
            
            self.client.copy_object(
                bucket_name=self.bucket,
                object_name=storage_path,
                source=copy_source
            )
            
            # Delete the temporary copy
            self.client.remove_object(
                bucket_name=self.bucket,
                object_name=temp_path
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Error updating metadata: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def copy_file(self, source_path: str, destination_path: str) -> str:
        """
        Copy a file in MinIO
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            Access URL for the copied file
        """
        try:
            copy_source = ComposeSource(
                bucket_name=self.bucket,
                object_name=source_path
            )
            
            self.client.copy_object(
                bucket_name=self.bucket,
                object_name=destination_path,
                source=copy_source
            )
            
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error copying file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def move_file(self, source_path: str, destination_path: str) -> str:
        """
        Move a file in MinIO
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            Access URL for the moved file
        """
        try:
            # Copy the file first
            copy_source = ComposeSource(
                bucket_name=self.bucket,
                object_name=source_path
            )
            
            self.client.copy_object(
                bucket_name=self.bucket,
                object_name=destination_path,
                source=copy_source
            )
            
            # Then delete the original
            self.client.remove_object(
                bucket_name=self.bucket,
                object_name=source_path
            )
            
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error moving file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
