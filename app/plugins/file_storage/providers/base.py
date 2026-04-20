"""
Basic interface for storage providers
"""

import abc
from typing import BinaryIO, Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta


class StorageException(Exception):
    """Exception specific to storage operations"""
    pass


class StorageProviderInterface(abc.ABC):
    """
    Abstract interface that all storage providers must implement
    """
    
    @abc.abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the storage provider with the given configuration
        
        Args:
            config: Configuration dictionary for the provider
        """
        pass
    
    @abc.abstractmethod
    def upload_file(self, 
                   file_obj: BinaryIO, 
                   destination_path: str, 
                   content_type: str = None, 
                   metadata: Dict[str, str] = None) -> str:
        """
        Upload a file to the storage
        
        Args:
            file_obj: File object opened in binary mode
            destination_path: Destination path in the storage
            content_type: MIME type of the file
            metadata: Metadata to associate with the file
            
        Returns:
            URL of the uploaded file
        """
        pass
    
    @abc.abstractmethod
    def download_file(self, storage_path: str) -> BinaryIO:
        """
        Download a file from the storage
        
        Args:
            storage_path: Path of the file in the storage
            
        Returns:
            File object containing the data
        """
        pass
    
    @abc.abstractmethod
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from the storage
        
        Args:
            storage_path: Path of the file in the storage
            
        Returns:
            True if the deletion was successful, False otherwise
        """
        pass
    
    @abc.abstractmethod
    def get_file_url(self, 
                    storage_path: str, 
                    expires: int = 3600, 
                    is_public: bool = False) -> str:
        """
        Get the URL of a file
        
        Args:
            storage_path: Path of the file in the storage
            expires: Duration of validity in seconds (for temporary URLs)
            is_public: If the file is public
            
        Returns:
            URL of the file
        """
        pass
    
    @abc.abstractmethod
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in the storage
        
        Args:
            storage_path: Path of the file in the storage
            
        Returns:
            True if the file exists, False otherwise
        """
        pass
    
    @abc.abstractmethod
    def get_file_metadata(self, storage_path: str) -> Dict[str, Any]:
        """
        Get the metadata of a file
        
        Args:
            storage_path: Path of the file in the storage
            
        Returns:
            Dictionary containing the file metadata
        """
        pass
    
    @abc.abstractmethod
    def list_files(self, prefix: str = "", recursive: bool = True) -> List[Dict[str, Any]]:
        """
        List files in a directory
        
        Args:
            prefix: Prefix to filter results
            recursive: If the search should be recursive
            
        Returns:
            List of dictionaries containing file information
        """
        pass
    
    @abc.abstractmethod
    def update_file_metadata(self, storage_path: str, metadata: Dict[str, str]) -> bool:
        """
        Update the metadata of a file
        
        Args:
            storage_path: Path of the file in the storage
            metadata: New metadata
            
        Returns:
            True if the update was successful, False otherwise
        """
        pass
    
    @abc.abstractmethod
    def copy_file(self, source_path: str, destination_path: str) -> str:
        """
        Copy a file in the storage
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            URL of the copied file
        """
        pass
    
    @abc.abstractmethod
    def move_file(self, source_path: str, destination_path: str) -> str:
        """
        Move a file in the storage
        
        Args:
            source_path: Source file path
            destination_path: Destination file path
            
        Returns:
            URL of the moved file
        """
        pass
