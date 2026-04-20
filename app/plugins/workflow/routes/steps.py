"""
Routes for managing workflow steps.

This module provides API endpoints for CRUD operations on workflow steps.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.workflow.models import Workflow, WorkflowStep
from app.plugins.advanced_auth.models import Role
from app.plugins.workflow.schemas import (
    WorkflowStepCreate,
    WorkflowStepUpdate,
    WorkflowStepResponse
)

router = APIRouter()


@router.post("/workflows/{workflow_id}/steps", response_model=WorkflowStepResponse)
async def create_workflow_step(
    workflow_id: int,
    step: WorkflowStepCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new workflow step for a specific workflow."""
    # Verify workflow exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Verify the step order is valid
    if step.step_order <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Step order must be greater than 0"
        )
    
    # Create step
    step_data = step.dict(exclude={"workflow_id", "role_ids"})
    db_step = WorkflowStep(workflow_id=workflow_id, **step_data)
    db.add(db_step)
    db.flush()  # Flush to get the ID without committing
    
    # Add approver roles if provided
    if step.role_ids:
        for role_id in step.role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                db_step.approvers.append(role)
    
    db.commit()
    db.refresh(db_step)
    
    return db_step


@router.get("/workflows/{workflow_id}/steps", response_model=List[WorkflowStepResponse])
async def get_workflow_steps(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """Get all steps for a specific workflow."""
    # Verify workflow exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    steps = db.query(WorkflowStep).filter(
        WorkflowStep.workflow_id == workflow_id
    ).order_by(WorkflowStep.step_order).all()
    
    return steps


@router.get("/steps/{step_id}", response_model=WorkflowStepResponse)
async def get_workflow_step(
    step_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific workflow step by ID."""
    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow step not found"
        )
    
    return step


@router.put("/steps/{step_id}", response_model=WorkflowStepResponse)
async def update_workflow_step(
    step_id: int,
    step_update: WorkflowStepUpdate,
    db: Session = Depends(get_db)
):
    """Update a workflow step."""
    db_step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    if not db_step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow step not found"
        )
    
    # Update fields
    update_data = step_update.dict(exclude_unset=True, exclude={"role_ids"})
    for key, value in update_data.items():
        setattr(db_step, key, value)
    
    # Update approver roles if provided
    if step_update.role_ids is not None:
        # Clear existing approvers
        db_step.approvers = []
        
        # Add new approvers
        for role_id in step_update.role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                db_step.approvers.append(role)
    
    db.add(db_step)
    db.commit()
    db.refresh(db_step)
    
    return db_step


@router.delete("/steps/{step_id}", status_code=status.HTTP_200_OK)
async def delete_workflow_step(
    step_id: int,
    db: Session = Depends(get_db)
):
    """Delete a workflow step."""
    db_step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    if not db_step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow step not found"
        )
    
    # Delete the step
    db.delete(db_step)
    db.commit()
    
    return {"message": "Workflow step deleted successfully"}
