"""
Routes for managing workflow states.

This module provides API endpoints for CRUD operations on workflow states.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.workflow.models import Workflow, WorkflowState
from app.plugins.workflow.schemas import (
    WorkflowStateCreate,
    WorkflowStateUpdate,
    WorkflowStateResponse
)

router = APIRouter()


@router.post("/workflows/{workflow_id}/states", response_model=WorkflowStateResponse)
async def create_workflow_state(
    workflow_id: int,
    state: WorkflowStateCreate,
    db: Session = Depends(get_db)
):
    """Create a new workflow state for a specific workflow."""
    # Verify workflow exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check if this is set as initial state
    if state.is_initial:
        # Ensure there's only one initial state per workflow
        existing_initial = db.query(WorkflowState).filter(
            WorkflowState.workflow_id == workflow_id,
            WorkflowState.is_initial == True
        ).first()
        
        if existing_initial:
            # Update existing initial state to be non-initial
            existing_initial.is_initial = False
            db.add(existing_initial)
    
    # Create state
    state_data = state.dict()
    db_state = WorkflowState(**state_data)
    
    db.add(db_state)
    db.commit()
    db.refresh(db_state)
    
    return db_state


@router.get("/workflows/{workflow_id}/states", response_model=List[WorkflowStateResponse])
async def get_workflow_states(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """Get all states for a specific workflow."""
    # Verify workflow exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    states = db.query(WorkflowState).filter(
        WorkflowState.workflow_id == workflow_id
    ).all()
    
    return states


@router.get("/states/{state_id}", response_model=WorkflowStateResponse)
async def get_workflow_state(
    state_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific workflow state by ID."""
    state = db.query(WorkflowState).filter(WorkflowState.id == state_id).first()
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow state not found"
        )
    
    return state


@router.put("/states/{state_id}", response_model=WorkflowStateResponse)
async def update_workflow_state(
    state_id: int,
    state_update: WorkflowStateUpdate,
    db: Session = Depends(get_db)
):
    """Update a workflow state."""
    db_state = db.query(WorkflowState).filter(WorkflowState.id == state_id).first()
    if not db_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow state not found"
        )
    
    # Check if initial state is being changed
    if state_update.is_initial is not None and state_update.is_initial != db_state.is_initial and state_update.is_initial:
        # If changing to initial, ensure there's only one initial state
        existing_initial = db.query(WorkflowState).filter(
            WorkflowState.workflow_id == db_state.workflow_id,
            WorkflowState.is_initial == True,
            WorkflowState.id != state_id
        ).first()
        
        if existing_initial:
            # Update existing initial state to be non-initial
            existing_initial.is_initial = False
            db.add(existing_initial)
    
    # Update state fields
    update_data = state_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_state, key, value)
    
    db.add(db_state)
    db.commit()
    db.refresh(db_state)
    
    return db_state


@router.delete("/states/{state_id}", status_code=status.HTTP_200_OK)
async def delete_workflow_state(
    state_id: int,
    db: Session = Depends(get_db)
):
    """Delete a workflow state."""
    db_state = db.query(WorkflowState).filter(WorkflowState.id == state_id).first()
    if not db_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow state not found"
        )
    
    # Check if state has any transitions
    # In a production system, you might want to check for transitions and prevent deletion or cascade
    
    # Delete the state
    db.delete(db_state)
    db.commit()
    
    return {"message": "Workflow state deleted successfully"}
