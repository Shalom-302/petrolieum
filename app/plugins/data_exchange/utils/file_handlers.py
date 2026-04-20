"""
Utility functions for handling file operations.
"""

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import UploadFile


# Define base directories for uploaded and exported files
UPLOADS_DIR = Path("./uploads")
EXPORTS_DIR = Path("./exports")
TEMP_DIR = Path("./temp")


async def save_uploaded_file(file: UploadFile, user_id: int, is_temp: bool = False) -> str:
    """
    Save an uploaded file to the file system.
    
    Args:
        file: The uploaded file
        user_id: The ID of the user uploading the file
        is_temp: Whether this is a temporary file
        
    Returns:
        The path to the saved file
    """
    # Create directories if they don't exist
    base_dir = TEMP_DIR if is_temp else UPLOADS_DIR
    user_dir = base_dir / str(user_id)
    date_dir = user_dir / datetime.now().strftime('%Y/%m/%d')
    os.makedirs(date_dir, exist_ok=True)
    
    # Generate a unique filename
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = date_dir / unique_filename
    
    # Write the file
    with open(file_path, "wb") as f:
        # Read the file in chunks to avoid loading large files into memory
        CHUNK_SIZE = 1024 * 1024  # 1MB
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            f.write(chunk)
    
    return str(file_path)


def create_export_file_path(user_id: int, format_type: str, filename: Optional[str] = None) -> str:
    """
    Create a file path for an exported file.
    
    Args:
        user_id: The ID of the user exporting the file
        format_type: The file format (e.g., 'csv', 'json', 'excel')
        filename: Optional filename to use
        
    Returns:
        The path to the export file
    """
    # Create directories if they don't exist
    user_dir = EXPORTS_DIR / str(user_id)
    date_dir = user_dir / datetime.now().strftime('%Y/%m/%d')
    os.makedirs(date_dir, exist_ok=True)
    
    # Generate a filename
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"export_{timestamp}.{format_type.lower()}"
    
    # Return the full path
    return str(date_dir / filename)


def delete_file(file_path: str) -> bool:
    """
    Delete a file.
    
    Args:
        file_path: The path to the file to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        print(f"Error deleting file {file_path}: {str(e)}")
        return False


def clear_temp_files(user_id: Optional[int] = None, max_age_hours: int = 24) -> int:
    """
    Clear temporary files that are older than a specified age.
    
    Args:
        user_id: Optional user ID to only clear files for a specific user
        max_age_hours: Maximum age of files to keep in hours
        
    Returns:
        Number of files deleted
    """
    base_dir = TEMP_DIR
    
    # If user_id is specified, only clear files for that user
    if user_id:
        base_dir = base_dir / str(user_id)
    
    # Calculate the cutoff timestamp
    cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
    
    # Count deleted files
    deleted_count = 0
    
    # Walk through the directory and delete old files
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.getmtime(file_path) < cutoff:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting temp file {file_path}: {str(e)}")
    
    # Clean up empty directories
    for root, dirs, files in os.walk(base_dir, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                except Exception as e:
                    print(f"Error removing empty directory {dir_path}: {str(e)}")
    
    return deleted_count


def list_files(directory: str, extensions: Optional[List[str]] = None) -> List[str]:
    """
    List files in a directory, optionally filtered by extension.
    
    Args:
        directory: The directory to list files from
        extensions: Optional list of file extensions to filter by (without the dot)
        
    Returns:
        List of file paths
    """
    files = []
    
    # Check if directory exists
    if not os.path.exists(directory):
        return files
    
    # Walk through the directory and collect files
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if extensions:
                ext = os.path.splitext(filename)[1].lower()[1:]  # Remove leading dot
                if ext in extensions:
                    files.append(os.path.join(root, filename))
            else:
                files.append(os.path.join(root, filename))
    
    return files
