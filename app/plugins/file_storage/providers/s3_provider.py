"""
S3 storage provider
"""

import io
import os
import logging
from typing import BinaryIO, Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
import mimetypes
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

from .base import StorageProviderInterface, StorageException


class S3StorageProvider(StorageProviderInterface):
    """
    Implementation of StorageProviderInterface for Amazon S3
    """
    
    def __init__(self):
        self.client = None
        self.s3_resource = None
        self.bucket_name = None
        self.region = None
        self.logger = logging.getLogger(__name__)
    
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the S3 client with the provided configuration
        
        Args:
            config: Dictionary containing:
                    - access_key: AWS access key
                    - secret_key: AWS secret key
                    - bucket_name: Name of the bucket to use
                    - region: AWS region (optional, default: us-east-1)
                    - endpoint_url: Custom endpoint URL (optional)
        """
        try:
            access_key = config['access_key']
            secret_key = config['secret_key']
            self.bucket_name = config['bucket_name']
            self.region = config.get('region', 'us-east-1')
            endpoint_url = config.get('endpoint_url', None)
            
            # Configuration for presigned URLs
            s3_config = Config(
                signature_version='s3v4',
                region_name=self.region
            )
            
            # Create the S3 client
            session = boto3.session.Session()
            self.client = session.client(
                's3',
                region_name=self.region,
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=s3_config
            )
            
            # Create the S3 resource (for certain operations)
            self.s3_resource = session.resource(
                's3',
                region_name=self.region,
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key
            )
            
            # Check if the bucket exists
            try:
                self.client.head_bucket(Bucket=self.bucket_name)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    # Bucket does not exist, create it
                    if self.region == 'us-east-1':
                        self.client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    self.logger.info(f"Bucket S3 {self.bucket_name} créé avec succès")
                else:
                    # Other error
                    raise StorageException(f"Error checking S3 bucket: {str(e)}")
                
        except Exception as e:
            error_msg = f"Error initializing S3 provider: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def upload_file(self, 
                   file_obj: BinaryIO, 
                   destination_path: str, 
                   content_type: str = None, 
                   metadata: Dict[str, str] = None) -> str:
        """
        Upload a file to S3
        
        Args:
            file_obj: File object opened in binary mode
            destination_path: Destination path in S3
            content_type: MIME type of the file
            metadata: Metadata to associate with the file
            
        Returns:
            Access URL for the uploaded file
        """
        try:
            # Determine content type if not specified
            if not content_type:
                content_type, _ = mimetypes.guess_type(destination_path)
                content_type = content_type or 'application/octet-stream'
            
            # Prepare the ExtraArgs for the upload
            extra_args = {
                'ContentType': content_type
            }
            
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Upload the file
            self.client.upload_fileobj(
                Fileobj=file_obj,
                Bucket=self.bucket_name,
                Key=destination_path,
                ExtraArgs=extra_args
            )
            
            # Return the access URL
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error uploading file to S3: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def download_file(self, storage_path: str) -> BinaryIO:
        """
        Download a file from S3
        
        Args:
            storage_path: Path of the file in S3
            
        Returns:
            File object containing the data
        """
        try:
            # Create a BytesIO object to store the data
            file_data = io.BytesIO()
            
            # Download the file
            self.client.download_fileobj(
                Bucket=self.bucket_name,
                Key=storage_path,
                Fileobj=file_data
            )
            
            # Reset the cursor to the beginning of the file
            file_data.seek(0)
            
            return file_data
            
        except Exception as e:
            error_msg = f"Error downloading file from S3: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            storage_path: Path of the file in S3
            
        Returns:
            True if the deletion was successful, False otherwise
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            return True
            
        except Exception as e:
            error_msg = f"Error deleting file from S3: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def get_file_url(self, 
                    storage_path: str, 
                    expires: int = 3600, 
                    is_public: bool = False) -> str:
        """
        Get the access URL for a file in S3
        
        Args:
            storage_path: Path of the file in S3
            expires: Duration of validity in seconds (for temporary URLs)
            is_public: If the file is publicly accessible
            
        Returns:
            Access URL for the file
        """
        try:
            if is_public:
                # For public files, use the standard S3 URL
                return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{storage_path}"
            else:
                # Generate a presigned URL with expiration
                return self.client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': storage_path
                    },
                    ExpiresIn=expires
                )
                
        except Exception as e:
            error_msg = f"Error generating URL for S3 file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            storage_path: Path of the file in S3
            
        Returns:
            True if the file exists, False otherwise
        """
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            return True
            
        except ClientError:
            return False
    
    def get_file_metadata(self, storage_path: str) -> Dict[str, Any]:
        """
        Get the metadata of a file in S3
        
        Args:
            storage_path: Path of the file in S3
            
        Returns:
            Dictionary containing the file metadata
        """
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'content_type': response.get('ContentType'),
                'metadata': response.get('Metadata', {})
            }
            
        except Exception as e:
            error_msg = f"Error retrieving S3 file metadata: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def list_files(self, prefix: str = "", recursive: bool = True) -> List[Dict[str, Any]]:
        """
        List files in an S3 directory
        
        Args:
            prefix: Prefix to filter results
            recursive: If the search should be recursive
            
        Returns:
            List of dictionaries containing file information
        """
        try:
            # For S3, the recursive behavior is the default behavior
            # To avoid recursion, specify a delimiter
            delimiter = None if recursive else '/'
            
            paginator = self.client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter=delimiter
            )
            
            result = []
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        result.append({
                            'name': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'etag': obj['ETag'].strip('"'),
                            'is_dir': False
                        })
                
                # Handle CommonPrefixes (directories) if not recursive
                if not recursive and 'CommonPrefixes' in page:
                    for prefix_obj in page['CommonPrefixes']:
                        result.append({
                            'name': prefix_obj['Prefix'],
                            'size': 0,
                            'last_modified': None,
                            'etag': None,
                            'is_dir': True
                        })
                
            return result
            
        except Exception as e:
            error_msg = f"Error listing S3 files: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def update_file_metadata(self, storage_path: str, metadata: Dict[str, str]) -> bool:
        """
        Update the metadata of a file in S3
        
        Args:
            storage_path: Path of the file in S3
            metadata: New metadata
            
        Returns:
            True if the update was successful, False otherwise
        """
        try:
            # Get the current metadata
            current = self.get_file_metadata(storage_path)
            
            # Copy the object with the new metadata
            copy_source = {
                'Bucket': self.bucket_name,
                'Key': storage_path
            }
            
            # Merge current metadata with new metadata
            merged_metadata = {**current.get('metadata', {}), **metadata}
            
            self.client.copy_object(
                Bucket=self.bucket_name,
                Key=storage_path,
                CopySource=copy_source,
                Metadata=merged_metadata,
                MetadataDirective='REPLACE'
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Error updating S3 file metadata: {str(e)}"
            self.logger.error(error_msg)
            return False
    
    def copy_file(self, source_path: str, destination_path: str) -> str:
        """
        Copy a file in S3
        
        Args:
            source_path: Source file path
            destination_path: Destination path
            
        Returns:
            Access URL for the copied file
        """
        try:
            copy_source = {
                'Bucket': self.bucket_name,
                'Key': source_path
            }
            
            self.client.copy_object(
                Bucket=self.bucket_name,
                Key=destination_path,
                CopySource=copy_source
            )
            
            return self.get_file_url(destination_path)
            
        except Exception as e:
            error_msg = f"Error copying S3 file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
    
    def move_file(self, source_path: str, destination_path: str) -> str:
        """
        Move a file in S3
        
        Args:
            source_path: Source file path
            destination_path: Destination path
            
        Returns:
            Access URL for the moved file
        """
        try:
            # Copy the file first
            url = self.copy_file(source_path, destination_path)
            
            # Then delete the original
            self.delete_file(source_path)
            
            return url
            
        except Exception as e:
            error_msg = f"Error moving S3 file: {str(e)}"
            self.logger.error(error_msg)
            raise StorageException(error_msg)
