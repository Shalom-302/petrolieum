"""
Routes for managing workflow instances.

This module provides API endpoints for creating and managing workflow instances.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.workflow.models import (
    Workflow, WorkflowState, WorkflowInstance, 
    WorkflowStep, StepApproval, WorkflowHistory
)
from app.plugins.workflow.schemas import (
    WorkflowInstanceCreate,
    WorkflowInstanceResponse,
    PaginatedResponse
)

router = APIRouter()


@router.post("/instances", response_model=WorkflowInstanceResponse)
async def create_workflow_instance(
    instance: WorkflowInstanceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new workflow instance for a specific entity."""
    # Verify workflow exists
    workflow = db.query(Workflow).filter(
        Workflow.id == instance.workflow_id,
        Workflow.is_active == True
    ).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workflow not found"
        )
    
    # Get initial state
    initial_state = db.query(WorkflowState).filter(
        WorkflowState.workflow_id == instance.workflow_id,
        WorkflowState.is_initial == True
    ).first()
    if not initial_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow has no initial state defined"
        )
    
    # Create workflow instance
    instance_data = instance.dict()
    instance_data["current_state_id"] = initial_state.id
    
    db_instance = WorkflowInstance(**instance_data)
    db.add(db_instance)
    db.flush()
    
    # Create history record for instance creation
    history_record = WorkflowHistory(
        instance_id=db_instance.id,
        action_type="instance_created",
        to_state_id=initial_state.id,
        user_id=current_user["id"],
        details={
            "created_by": current_user["id"],
            "target_type": instance.target_type,
            "target_id": instance.target_id
        }
    )
    db.add(history_record)
    
    # Create initial approval records for first steps
    first_steps = db.query(WorkflowStep).filter(
        WorkflowStep.workflow_id == instance.workflow_id,
        WorkflowStep.step_order == 1
    ).all()
    
    for step in first_steps:
        approval = StepApproval(
            instance_id=db_instance.id,
            step_id=step.id,
            status="pending"
        )
        db.add(approval)
    
    db.commit()
    db.refresh(db_instance)
    
    return db_instance


@router.get("/instances", response_model=PaginatedResponse)
async def get_workflow_instances(
    workflow_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    current_state_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get workflow instances with optional filtering."""
    query = db.query(WorkflowInstance)
    
    # Apply filters
    if workflow_id:
        query = query.filter(WorkflowInstance.workflow_id == workflow_id)
    if target_type:
        query = query.filter(WorkflowInstance.target_type == target_type)
    if target_id:
        query = query.filter(WorkflowInstance.target_id == target_id)
    if is_active is not None:
        query = query.filter(WorkflowInstance.is_active == is_active)
    if current_state_id:
        query = query.filter(WorkflowInstance.current_state_id == current_state_id)
    
    # Count total
    total = query.count()
    
    # Paginate
    instances = query.order_by(WorkflowInstance.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    # Calculate total pages
    pages = (total + page_size - 1) // page_size
    
    return {
        "items": instances,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages
    }


@router.get("/instances/{instance_id}", response_model=WorkflowInstanceResponse)
async def get_workflow_instance(
    instance_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific workflow instance by ID."""
    instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow instance not found"
        )
    
    return instance


@router.put("/instances/{instance_id}/transition/{state_id}", response_model=WorkflowInstanceResponse)
async def transition_workflow_instance(
    instance_id: int,
    state_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Transition a workflow instance to a new state manually."""
    # Get instance
    instance = db.query(WorkflowInstance).filter(
        WorkflowInstance.id == instance_id,
        WorkflowInstance.is_active == True
    ).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workflow instance not found"
        )
    
    # Verify new state exists and belongs to the workflow
    new_state = db.query(WorkflowState).filter(
        WorkflowState.id == state_id,
        WorkflowState.workflow_id == instance.workflow_id
    ).first()
    if not new_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target state not found or doesn't belong to this workflow"
        )
    
    # Check if a valid transition exists
    if instance.current_state_id:
        valid_transition = db.query(WorkflowTransition).filter(
            WorkflowTransition.workflow_id == instance.workflow_id,
            WorkflowTransition.from_state_id == instance.current_state_id,
            WorkflowTransition.to_state_id == state_id
        ).first()
        
        if not valid_transition:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid transition exists between current state and target state"
            )
    
    # Record old state for history
    old_state_id = instance.current_state_id
    
    # Update instance state
    instance.current_state_id = state_id
    
    # If new state is a final state, mark instance as completed
    if new_state.is_final:
        instance.is_active = False
        instance.completed_at = datetime.utcnow()
    
    # Add history record
    history_record = WorkflowHistory(
        instance_id=instance_id,
        action_type="state_transition",
        from_state_id=old_state_id,
        to_state_id=state_id,
        user_id=current_user["id"],
        details={
            "transition_by": current_user["id"],
            "manual": True
        }
    )
    db.add(history_record)
    
    db.add(instance)
    db.commit()
    db.refresh(instance)
    
    return instance


@router.get("/instances/{instance_id}/history", response_model=List[Dict[str, Any]])
async def get_workflow_instance_history(
    instance_id: int,
    db: Session = Depends(get_db)
):
    """Get the history of a workflow instance."""
    # Verify instance exists
    instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow instance not found"
        )
    
    # Get history records
    history = db.query(WorkflowHistory).filter(
        WorkflowHistory.instance_id == instance_id
    ).order_by(WorkflowHistory.created_at).all()
    
    # Format the response
    formatted_history = []
    for record in history:
        item = {
            "id": record.id,
            "action_type": record.action_type,
            "created_at": record.created_at,
            "details": record.details
        }
        
        # Add state information if present
        if record.from_state_id:
            from_state = db.query(WorkflowState).filter(WorkflowState.id == record.from_state_id).first()
            if from_state:
                item["from_state"] = {"id": from_state.id, "name": from_state.name}
        
        if record.to_state_id:
            to_state = db.query(WorkflowState).filter(WorkflowState.id == record.to_state_id).first()
            if to_state:
                item["to_state"] = {"id": to_state.id, "name": to_state.name}
        
        # Add user information
        if record.user_id:
            # In a real app, you would get more user details here
            item["user"] = {"id": record.user_id}
        
        formatted_history.append(item)
    
    return formatted_history


@router.delete("/instances/{instance_id}", status_code=status.HTTP_200_OK)
async def cancel_workflow_instance(
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Cancel (deactivate) a workflow instance."""
    instance = db.query(WorkflowInstance).filter(
        WorkflowInstance.id == instance_id,
        WorkflowInstance.is_active == True
    ).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workflow instance not found"
        )
    
    # Update instance
    instance.is_active = False
    
    # Add history record
    history_record = WorkflowHistory(
        instance_id=instance_id,
        action_type="instance_cancelled",
        from_state_id=instance.current_state_id,
        user_id=current_user["id"],
        details={
            "cancelled_by": current_user["id"]
        }
    )
    db.add(history_record)
    
    db.add(instance)
    db.commit()
    
    return {"message": "Workflow instance cancelled successfully"}
