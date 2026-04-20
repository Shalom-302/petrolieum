"""
Routes for managing workflow transitions.

This module provides API endpoints for CRUD operations on workflow transitions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.workflow.models import Workflow, WorkflowState, WorkflowTransition
from app.plugins.workflow.schemas import (
    WorkflowTransitionCreate,
    WorkflowTransitionUpdate,
    WorkflowTransitionResponse
)

router = APIRouter()


@router.post("/workflows/{workflow_id}/transitions", response_model=WorkflowTransitionResponse)
async def create_workflow_transition(
    workflow_id: int,
    transition: WorkflowTransitionCreate,
    db: Session = Depends(get_db)
):
    """Create a new workflow transition between states."""
    # Verify workflow exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Verify from_state exists and belongs to this workflow
    from_state = db.query(WorkflowState).filter(
        WorkflowState.id == transition.from_state_id,
        WorkflowState.workflow_id == workflow_id
    ).first()
    if not from_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="From state not found or does not belong to this workflow"
        )
    
    # Verify to_state exists and belongs to this workflow
    to_state = db.query(WorkflowState).filter(
        WorkflowState.id == transition.to_state_id,
        WorkflowState.workflow_id == workflow_id
    ).first()
    if not to_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="To state not found or does not belong to this workflow"
        )
    
    # Verify this transition doesn't already exist
    existing = db.query(WorkflowTransition).filter(
        WorkflowTransition.workflow_id == workflow_id,
        WorkflowTransition.from_state_id == transition.from_state_id,
        WorkflowTransition.to_state_id == transition.to_state_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A transition between these states already exists"
        )
    
    # Create transition
    transition_data = transition.dict()
    db_transition = WorkflowTransition(**transition_data)
    
    db.add(db_transition)
    db.commit()
    db.refresh(db_transition)
    
    return db_transition


@router.get("/workflows/{workflow_id}/transitions", response_model=List[WorkflowTransitionResponse])
async def get_workflow_transitions(
    workflow_id: int,
    from_state_id: Optional[int] = None,
    to_state_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get all transitions for a specific workflow, optionally filtered by from/to states."""
    # Verify workflow exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Build query
    query = db.query(WorkflowTransition).filter(WorkflowTransition.workflow_id == workflow_id)
    
    # Apply filters if provided
    if from_state_id:
        query = query.filter(WorkflowTransition.from_state_id == from_state_id)
    if to_state_id:
        query = query.filter(WorkflowTransition.to_state_id == to_state_id)
    
    transitions = query.all()
    
    return transitions


@router.get("/transitions/{transition_id}", response_model=WorkflowTransitionResponse)
async def get_workflow_transition(
    transition_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific workflow transition by ID."""
    transition = db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).first()
    if not transition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow transition not found"
        )
    
    return transition


@router.put("/transitions/{transition_id}", response_model=WorkflowTransitionResponse)
async def update_workflow_transition(
    transition_id: int,
    transition_update: WorkflowTransitionUpdate,
    db: Session = Depends(get_db)
):
    """Update a workflow transition."""
    db_transition = db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).first()
    if not db_transition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow transition not found"
        )
    
    # Update transition fields
    update_data = transition_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_transition, key, value)
    
    db.add(db_transition)
    db.commit()
    db.refresh(db_transition)
    
    return db_transition


@router.delete("/transitions/{transition_id}", status_code=status.HTTP_200_OK)
async def delete_workflow_transition(
    transition_id: int,
    db: Session = Depends(get_db)
):
    """Delete a workflow transition."""
    db_transition = db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).first()
    if not db_transition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow transition not found"
        )
    
    # Delete the transition
    db.delete(db_transition)
    db.commit()
    
    return {"message": "Workflow transition deleted successfully"}
