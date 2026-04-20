"""
Routes for managing file folders
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.advanced_auth.models import User

from ..models import FileFolder, StorageProvider, StoredFile
from ..schemas import FileFolderCreate, FileFolderResponse, FileFolderDetailResponse

router = APIRouter(prefix="/folders")

logger = logging.getLogger(__name__)

def folder_to_dict(folder):
    """
    Convert FileFolder SQLAlchemy object to a dictionary suitable for Pydantic models
    """
    result = {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": folder.created_at,
        "updated_at": folder.updated_at,
        "metadata": folder.file_metadata if folder.file_metadata else {}
    }
    return result

@router.post("", response_model=FileFolderResponse)
async def create_folder(
    folder_data: FileFolderCreate,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)
):
    """
    Create a new file folder
    """
    # Check if a folder with the same path already exists
    existing_folder = db.query(FileFolder).filter(
        FileFolder.name == folder_data.name
    ).first()
    
    if existing_folder:
        raise HTTPException(
            status_code=400, 
            detail="A folder with this name already exists"
        )
    
    # Create the folder
    folder = FileFolder(
        name=folder_data.name,
        parent_id=folder_data.parent_id,
        file_metadata=folder_data.metadata if hasattr(folder_data, 'metadata') else None
    )
    
    try:
        db.add(folder)
        db.commit()
        db.refresh(folder)
        return {"folder": folder_to_dict(folder), "message": "Folder created successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating folder: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=List[FileFolderResponse])
async def list_folders(
    parent_folder_id: Optional[int] = None,
    path_prefix: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)
):
    """
    List folders with optional filtering
    """
    query = db.query(FileFolder)
    
    # Apply filters
    if parent_folder_id is not None:
        query = query.filter(FileFolder.parent_id == parent_folder_id)
    
    if path_prefix:
        query = query.filter(FileFolder.name.startswith(path_prefix))
    
    # Execute the query with pagination
    folders = query.order_by(FileFolder.name).offset(skip).limit(limit).all()
    
    # Return formatted response
    return [{"folder": folder_to_dict(folder), "message": "Folder retrieved successfully"} for folder in folders]

@router.get("/{folder_id}", response_model=FileFolderDetailResponse)
async def get_folder_details(
    folder_id: int,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)
):
    """
    Get folder details, including the number of files
    """
    folder = db.query(FileFolder).filter(FileFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Calculate the number of files in this folder
    file_count = db.query(func.count(StoredFile.id)).filter(
        StoredFile.storage_path.startswith(folder.name + "/")
    ).scalar()
    
    # Get the direct subfolders
    subfolders = db.query(FileFolder).filter(
        FileFolder.parent_id == folder_id
    ).all()
    
    # Convert subfolders to dicts
    subfolder_dicts = [folder_to_dict(subfolder) for subfolder in subfolders]
    
    # Build the response
    folder_dict = folder_to_dict(folder)
    folder_dict["children"] = subfolder_dicts
    folder_dict["files_count"] = file_count
    
    return {
        "folder": folder_dict,
        "message": "Folder details retrieved successfully"
    }

@router.put("/{folder_id}", response_model=FileFolderResponse)
async def update_folder(
    folder_id: int,
    folder_data: FileFolderCreate,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)
):
    """
    Update an existing folder
    """
    # Check if folder exists
    folder = db.query(FileFolder).filter(FileFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Check if another folder with the same path already exists
    existing_folder = db.query(FileFolder).filter(
        FileFolder.name == folder_data.name,
        FileFolder.id != folder_id
    ).first()
    
    if existing_folder:
        raise HTTPException(
            status_code=400, 
            detail="Another folder with this name already exists"
        )
    
    # Update the fields
    folder.name = folder_data.name
    folder.parent_id = folder_data.parent_id
    if hasattr(folder_data, 'metadata'):
        folder.file_metadata = folder_data.metadata
    
    try:
        db.commit()
        db.refresh(folder)
        return {"folder": folder_to_dict(folder), "message": "Folder updated successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating folder: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{folder_id}", response_model=dict)
async def delete_folder(
    folder_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a folder
    
    By default, the deletion fails if the folder contains files or subfolders.
    Use force=True to delete a folder and all its contents.
    """
    folder = db.query(FileFolder).filter(FileFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Check if there are subfolders
    subfolders_count = db.query(func.count(FileFolder.id)).filter(
        FileFolder.parent_id == folder_id
    ).scalar()
    
    # Check if there are files in this folder
    files_count = db.query(func.count(StoredFile.id)).filter(
        StoredFile.storage_path.startswith(folder.name + "/")
    ).scalar()
    
    # If the folder is not empty and force=False, do not delete
    if not force and (subfolders_count > 0 or files_count > 0):
        raise HTTPException(
            status_code=400, 
            detail=f"The folder contains {subfolders_count} subfolders and {files_count} files. " 
                   f"Use force=True to delete the folder and all its contents."
        )
    
    try:
        # If force=True, also delete the subfolders
        if force and subfolders_count > 0:
            # Get all subfolders recursively
            all_subfolders = []
            
            def get_subfolder_ids(parent_id):
                subfolders = db.query(FileFolder).filter(
                    FileFolder.parent_id == parent_id
                ).all()
                
                for subfolder in subfolders:
                    all_subfolders.append(subfolder.id)
                    get_subfolder_ids(subfolder.id)
            
            get_subfolder_ids(folder_id)
            
            # Delete the subfolders (from bottom to top)
            for subfolder_id in reversed(all_subfolders):
                db.query(FileFolder).filter(FileFolder.id == subfolder_id).delete()
        
        # If force=True, also delete all files in the folder
        if force and files_count > 0:
            # Note: Files in the storage are not deleted here.
            # This should be handled by a cleanup task or additional logic.
            files = db.query(StoredFile).filter(
                StoredFile.storage_path.startswith(folder.name + "/")
            ).all()
            
            for file in files:
                db.delete(file)
        
        # Delete the folder
        db.delete(folder)
        db.commit()
        
        return {
            "folder": {
                "id": folder_id,
                "name": folder.name,
                "parent_id": folder.parent_id,
                "created_at": folder.created_at,
                "updated_at": folder.updated_at,
                "metadata": folder.file_metadata if folder.file_metadata else {}
            },
            "message": f"Folder deleted successfully with {subfolders_count if force else 0} subfolders and {files_count if force else 0} files"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting folder: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
