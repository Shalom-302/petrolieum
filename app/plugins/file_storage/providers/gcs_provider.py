"""
Google Cloud Storage provider
"""

import io
import os
import logging
from typing import BinaryIO, Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
import mimetypes
import json

from google.cloud import storage
from google.oauth2 import service_account

from .base import StorageProviderInterface, StorageException


class GCSStorageProvider(StorageProviderInterface):
    """
    Implementation of StorageProviderInterface for Google Cloud Storage
    """
    
    def __init__(self):
        self.client = None
        self.bucket = None
        self.bucket_name = None
        self.logger = logging.getLogger(__name__)
    
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the GCS client with the provided configuration
        
        Args:
            config: Dictionary containing:
                    - bucket_name: Name of the bucket to use
                    - credentials_json: JSON content of service account credentials (or path to file)
                    - project_id: ID of the Google Cloud project (optional, can be included in credentials_json)
                    - location: Location for bucket creation (optional, default: us-central1)
        """
        try:
            self.bucket_name = config['bucket_name']
            credentials_json = config.get('credentials_json')
            project_id = config.get('project_id')
            location = config.get('location', 'us-central1')
            
            # Initialize identifiers
            if credentials_json:
                if isinstance(credentials_json, str) and os.path.isfile(credentials_json):
                    # If it's a path to a file
                    credentials = service_account.Credentials.from_service_account_file(credentials_json)
                else:
                    # If it's the JSON content directly
                    if isinstance(credentials_json, str):
                        credentials_dict = json.loads(credentials_json)
                    else:
                        credentials_dict = credentials_json
                    
                    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
                    
                # Extract project_id from credentials if not specified
                if not project_id and hasattr(credentials, 'project_id'):
                    project_id = credentials.project_id
                
                # Create client with credentials
                self.client = storage.Client(project=project_id, credentials=credentials)
            else:
                # Use default credentials (useful for GCP environments)
                self.client = storage.Client(project=project_id)
            
            # Check if the bucket exists, create if not
            try:
                self.bucket = self.client.get_bucket(self.bucket_name)
            except Exception:
                # The bucket does not exist, create it
                self.bucket = self.client.create_bucket(self.bucket_name, location=location)
                self.logger.info(f"Bucket GCS {self.bucket_name} created successfully in {location}")
                
        except Exception as e:
            error_msg = f"Error initializing GCS provider: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def upload_file(self, 
                   file_obj: BinaryIO, 
                   destination_path: str, 
                   content_type: str = None, 
                   metadata: Dict[str, str] = None) -> str:
        """
        Upload a file to GCS
        
        Args:
            file_obj: File object opened in binary mode
            destination_path: Destination path in GCS
            content_type: MIME type of the file
            metadata: Metadata to associate with the file
            
        Returns:
            URL of the uploaded file
        """
        try:
            # Determine content type if not specified
            if not content_type:
                content_type, _ = mimetypes.guess_type(destination_path)
                content_type = content_type or 'application/octet-stream'
            
            # Create a blob object
            blob = self.bucket.blob(destination_path)
            
            # Set content type
            blob.content_type = content_type
            
            # Set metadata
            if metadata:
                blob.metadata = metadata
            
            # Upload the file
            blob.upload_from_file(file_obj, content_type=content_type)
            
            # Return the access URL
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error during file upload to GCS: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def download_file(self, storage_path: str) -> BinaryIO:
        """
        Download a file from GCS
        
        Args:
            storage_path: Path of the file in GCS
            
        Returns:
            File object containing the data
        """
        try:
            # Get the blob
            blob = self.bucket.blob(storage_path)
            
            # Create a BytesIO object to store the data
            file_data = io.BytesIO()
            
            # Download the file
            blob.download_to_file(file_data)
            
            # Reset cursor to the beginning of the file
            file_data.seek(0)
            
            return file_data
            
        except Exception as e:
            error_msg = f"Error downloading file from GCS: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from GCS
        
        Args:
            storage_path: Path of the file in GCS
            
        Returns:
            True if the deletion was successful, False otherwise
        """
        try:
            # Get the blob
            blob = self.bucket.blob(storage_path)
            
            # Delete the blob
            blob.delete()
            
            return True
            
        except Exception as e:
            error_msg = f"Error deleting file from GCS: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def get_file_url(self, 
                    storage_path: str, 
                    expires: int = 3600, 
                    is_public: bool = False) -> str:
        """
        Get the URL of a file in GCS
        
        Args:
            storage_path: Path of the file in GCS
            expires: Duration of validity in seconds (for temporary URLs)
            is_public: If the file is public
            
        Returns:
            URL of the file
        """
        try:
            # Get the blob
            blob = self.bucket.blob(storage_path)
            
            if is_public:
                # Make the object public if necessary
                blob.make_public()
                return blob.public_url
            else:
                # Generate a temporary signed URL
                return blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.utcnow() + timedelta(seconds=expires),
                    method="GET"
                )
                
        except Exception as e:
            error_msg = f"Error generating URL for GCS file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in GCS
        
        Args:
            storage_path: Path of the file in GCS
            
        Returns:
            True if the file exists, False otherwise
        """
        try:
            # Get the blob
            blob = self.bucket.blob(storage_path)
            
            # Check if the blob exists
            return blob.exists()
            
        except Exception:
            return False
    
    def get_file_metadata(self, storage_path: str) -> Dict[str, Any]:
        """
        Get the metadata of a file in GCS
        
        Args:
            storage_path: Path of the file in GCS
            
        Returns:
            Dictionary containing the file metadata
        """
        try:
            # Get the blob
            blob = self.bucket.blob(storage_path)
            
            # Reload the metadata
            blob.reload()
            
            return {
                'size': blob.size,
                'last_modified': blob.updated,
                'etag': blob.etag,
                'content_type': blob.content_type,
                'metadata': blob.metadata or {}
            }
            
        except Exception as e:
            error_msg = f"Error retrieving GCS file metadata: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def list_files(self, prefix: str = "", recursive: bool = True) -> List[Dict[str, Any]]:
        """
        List files in a GCS directory
        
        Args:
            prefix: Prefix to filter results
            recursive: If the search should be recursive
            
        Returns:
            List of dictionaries containing file information
        """
        try:
            # For GCS, the recursive behavior is the default behavior
            # To avoid recursion, simulate with a delimiter and process prefixes
            delimiter = None if recursive else '/'
            
            # List the blobs
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=prefix,
                delimiter=delimiter
            )
            
            result = []
            
            # Process blobs (files)
            for blob in blobs:
                result.append({
                    'name': blob.name,
                    'size': blob.size,
                    'last_modified': blob.updated,
                    'etag': blob.etag,
                    'is_dir': False
                })
            
            # Process prefixes (directories) if not recursive
            if not recursive and delimiter:
                for prefix_obj in blobs.prefixes:
                    result.append({
                        'name': prefix_obj,
                        'size': 0,
                        'last_modified': None,
                        'etag': None,
                        'is_dir': True
                    })
                
            return result
            
        except Exception as e:
            error_msg = f"Error listing GCS files: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def update_file_metadata(self, storage_path: str, metadata: Dict[str, str]) -> bool:
        """
        Update the metadata of a file in GCS
        
        Args:
            storage_path: Path of the file in GCS
            metadata: New metadata
            
        Returns:
            True if the update was successful, False otherwise
        """
        try:
            # Get the blob
            blob = self.bucket.blob(storage_path)
            
            # Reload the metadata
            blob.reload()
            
            # Merge current metadata with new metadata
            current_metadata = blob.metadata or {}
            merged_metadata = {**current_metadata, **metadata}
            
            # Update the metadata
            blob.metadata = merged_metadata
            blob.patch()
            
            return True
            
        except Exception as e:
            error_msg = f"Error updating GCS file metadata: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def copy_file(self, source_path: str, destination_path: str) -> str:
        """
        Copy a file in GCS
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            URL of the copied file
        """
        try:
            # Get the source blob
            source_blob = self.bucket.blob(source_path)
            
            # Create a copy
            destination_blob = self.bucket.copy_blob(
                source_blob,
                self.bucket,
                destination_path
            )
            
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error copying GCS file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def move_file(self, source_path: str, destination_path: str) -> str:
        """
        Move a file in GCS
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            URL of the moved file
        """
        try:
            # First copy the file
            url = self.copy_file(source_path, destination_path)
            
            # Then delete the original
            self.delete_file(source_path)
            
            return url
            
        except Exception as e:
            error_msg = f"Error moving GCS file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
