"""
Routes for managing workflows.

This module provides API endpoints for CRUD operations on workflows.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.workflow.models import Workflow
from app.plugins.workflow.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowDetail,
    PaginatedWorkflowResponse
)

router = APIRouter()


@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(
    workflow: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new workflow."""
    # Check if a default workflow already exists for this target type
    if workflow.is_default:
        existing_default = db.query(Workflow).filter(
            Workflow.target_type == workflow.target_type,
            Workflow.is_default == True
        ).first()
        if existing_default:
            existing_default.is_default = False
            db.add(existing_default)
    
    # Create new workflow
    workflow_data = workflow.dict()
    workflow_data["created_by"] = current_user["id"]
    workflow_data["updated_by"] = current_user["id"]
    db_workflow = Workflow(**workflow_data)
    
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    
    return db_workflow


@router.get("/workflows", response_model=PaginatedWorkflowResponse)
async def get_workflows(
    target_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get all workflows with optional filtering."""
    query = db.query(Workflow)
    
    # Apply filters
    if target_type:
        query = query.filter(Workflow.target_type == target_type)
    if is_active is not None:
        query = query.filter(Workflow.is_active == is_active)
    if search:
        query = query.filter(Workflow.name.ilike(f"%{search}%"))
    
    # Count total
    total = query.count()
    
    # Paginate
    workflows = query.order_by(Workflow.name).offset((page - 1) * page_size).limit(page_size).all()
    
    # Calculate total pages
    pages = (total + page_size - 1) // page_size
    
    return {
        "items": workflows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages
    }


@router.get("/workflows/{workflow_id}", response_model=WorkflowDetail)
async def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific workflow by ID including all related data."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    return workflow


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    workflow_update: WorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a workflow."""
    db_workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check default status
    if workflow_update.is_default:
        existing_defaults = db.query(Workflow).filter(
            Workflow.target_type == db_workflow.target_type,
            Workflow.is_default == True,
            Workflow.id != workflow_id
        ).all()
        for existing in existing_defaults:
            existing.is_default = False
            db.add(existing)
    
    # Update workflow
    update_data = workflow_update.dict(exclude_unset=True)
    update_data["updated_by"] = current_user["id"]
    
    for key, value in update_data.items():
        setattr(db_workflow, key, value)
    
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    
    return db_workflow


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_200_OK)
async def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    """Delete a workflow."""
    db_workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check if there are active instances
    # In a production system, you might want to keep workflows with instances
    # and just mark them as inactive instead of deleting
    
    db.delete(db_workflow)
    db.commit()
    
    return {"message": "Workflow deleted successfully"}
