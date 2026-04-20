"""
Routes for managing workflow step approvals.

This module provides API endpoints for handling step approvals in workflow instances.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.workflow.models import (
    WorkflowInstance, WorkflowStep, StepApproval, 
    WorkflowHistory, WorkflowState, WorkflowTransition
)
from app.plugins.workflow.schemas import StepApprovalCreate, StepApprovalUpdate, StepApprovalResponse

router = APIRouter()


@router.get("/instances/{instance_id}/approvals", response_model=List[StepApprovalResponse])
async def get_instance_approvals(
    instance_id: int,
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get all approvals for a workflow instance."""
    # Verify instance exists
    instance = db.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow instance not found"
        )
    
    # Build query
    query = db.query(StepApproval).filter(StepApproval.instance_id == instance_id)
    
    # Filter by status if provided
    if status:
        query = query.filter(StepApproval.status == status)
    
    approvals = query.all()
    
    return approvals


@router.get("/users/me/pending-approvals", response_model=List[Dict[str, Any]])
async def get_my_pending_approvals(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all pending approvals for the current user based on their roles."""
    # In a real application, we would need to get user's roles
    # For demo purposes, we'll assume current_user has a roles attribute
    
    # Sample implementation
    pending_approvals = []
    
    # Get all pending approval records
    approval_records = db.query(StepApproval).filter(
        StepApproval.status == "pending"
    ).join(
        WorkflowInstance, WorkflowInstance.id == StepApproval.instance_id
    ).filter(
        WorkflowInstance.is_active == True
    ).all()
    
    for approval in approval_records:
        # Get the step to check if user has permission to approve
        step = db.query(WorkflowStep).filter(WorkflowStep.id == approval.step_id).first()
        
        if step:
            # Check if user has any of the roles required for this step
            # This would be more complex in a real application
            user_can_approve = False
            
            # For demo, we'll assume the user can approve all steps
            # In a real app, you would check against step.approvers
            user_can_approve = True
            
            if user_can_approve:
                # Get instance details
                instance = db.query(WorkflowInstance).filter(
                    WorkflowInstance.id == approval.instance_id
                ).first()
                
                if instance:
                    # Format the response
                    pending_approvals.append({
                        "approval_id": approval.id,
                        "instance_id": instance.id,
                        "step_id": step.id,
                        "step_name": step.name,
                        "workflow_id": instance.workflow_id,
                        "target_type": instance.target_type,
                        "target_id": instance.target_id,
                        "created_at": approval.created_at
                    })
    
    return pending_approvals


@router.post("/approvals/{approval_id}/approve", response_model=StepApprovalResponse)
async def approve_step(
    approval_id: int,
    approval_update: StepApprovalUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Approve a workflow step."""
    return await _process_approval(
        approval_id, "approved", approval_update, db, current_user
    )


@router.post("/approvals/{approval_id}/reject", response_model=StepApprovalResponse)
async def reject_step(
    approval_id: int,
    approval_update: StepApprovalUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Reject a workflow step."""
    return await _process_approval(
        approval_id, "rejected", approval_update, db, current_user
    )


async def _process_approval(
    approval_id: int,
    decision: str,
    approval_update: StepApprovalUpdate,
    db: Session,
    current_user: dict
):
    """Process a step approval or rejection."""
    # Get the approval record
    approval = db.query(StepApproval).filter(StepApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval record not found"
        )
    
    # Check if already processed
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This step has already been {approval.status}"
        )
    
    # Get the workflow instance
    instance = db.query(WorkflowInstance).filter(
        WorkflowInstance.id == approval.instance_id,
        WorkflowInstance.is_active == True
    ).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workflow instance not found"
        )
    
    # Get the step
    step = db.query(WorkflowStep).filter(WorkflowStep.id == approval.step_id).first()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow step not found"
        )
    
    # Check user authorization (simplified for demo)
    # In a real app, check if the user has the right role
    # user_can_approve = any(role.id in [r.id for r in step.approvers] for role in current_user.roles)
    user_can_approve = True  # Simplified for demo
    
    if not user_can_approve:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to approve this step"
        )
    
    # Update approval record
    approval.status = decision
    approval.decision_at = datetime.utcnow()
    approval.user_id = current_user["id"]
    if approval_update.comments:
        approval.comments = approval_update.comments
    
    db.add(approval)
    
    # Add history record
    history_record = WorkflowHistory(
        instance_id=instance.id,
        action_type=f"step_{decision}",
        step_id=step.id,
        user_id=current_user["id"],
        from_state_id=instance.current_state_id,
        details={
            f"{decision}_by": current_user["id"],
            "comments": approval_update.comments
        }
    )
    db.add(history_record)
    
    # Process next steps based on decision
    await _process_next_steps(db, instance, step, decision, current_user)
    
    db.commit()
    db.refresh(approval)
    
    return approval


async def _process_next_steps(
    db: Session, 
    instance: WorkflowInstance, 
    current_step: WorkflowStep,
    decision: str,
    current_user: dict
):
    """Process next steps after a decision has been made."""
    # Get next step ID based on the decision
    next_step_id = None
    if decision == "approved" and current_step.next_step_on_approve:
        next_step_id = current_step.next_step_on_approve
    elif decision == "rejected" and current_step.next_step_on_reject:
        next_step_id = current_step.next_step_on_reject
    
    # If there's a direct next step, create approval record for it
    if next_step_id:
        next_step = db.query(WorkflowStep).filter(WorkflowStep.id == next_step_id).first()
        if next_step:
            approval = StepApproval(
                instance_id=instance.id,
                step_id=next_step.id,
                status="pending"
            )
            db.add(approval)
            return
    
    # If no direct next step, check if we need to transition to a new state
    # Count other pending approvals at the same step level
    pending_count = db.query(StepApproval).filter(
        StepApproval.instance_id == instance.id,
        StepApproval.status == "pending",
        StepApproval.step_id.in_(
            db.query(WorkflowStep.id).filter(
                WorkflowStep.workflow_id == current_step.workflow_id,
                WorkflowStep.step_order == current_step.step_order
            )
        )
    ).count()
    
    # If no more pending approvals at this step level
    if pending_count == 0:
        # If approved, move to next step order
        if decision == "approved":
            next_order_steps = db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == current_step.workflow_id,
                WorkflowStep.step_order == current_step.step_order + 1
            ).all()
            
            # If there are next order steps, create approval records
            if next_order_steps:
                for step in next_order_steps:
                    approval = StepApproval(
                        instance_id=instance.id,
                        step_id=step.id,
                        status="pending"
                    )
                    db.add(approval)
                return
            
            # If no next steps, try to find appropriate state transition
            if instance.current_state_id:
                # Look for transitions triggered by approval completion
                transitions = db.query(WorkflowTransition).filter(
                    WorkflowTransition.workflow_id == instance.workflow_id,
                    WorkflowTransition.from_state_id == instance.current_state_id
                ).all()
                
                for transition in transitions:
                    # Check if this transition is triggered by approvals
                    # In a real app, you would have more complex logic here
                    if transition.triggers and "approval_complete" in str(transition.triggers):
                        # Transition to the new state
                        old_state_id = instance.current_state_id
                        instance.current_state_id = transition.to_state_id
                        
                        # Check if new state is final
                        new_state = db.query(WorkflowState).filter(
                            WorkflowState.id == transition.to_state_id
                        ).first()
                        
                        if new_state and new_state.is_final:
                            instance.is_active = False
                            instance.completed_at = datetime.utcnow()
                        
                        # Add history record for the transition
                        history_record = WorkflowHistory(
                            instance_id=instance.id,
                            action_type="state_transition",
                            from_state_id=old_state_id,
                            to_state_id=transition.to_state_id,
                            user_id=current_user["id"],
                            details={
                                "transition_trigger": "approval_complete",
                                "transition_by": current_user["id"]
                            }
                        )
                        db.add(history_record)
                        db.add(instance)
                        return
        
        # If rejected and no more pending approvals, mark workflow as failed
        elif decision == "rejected":
            # Look for rejection transition
            if instance.current_state_id:
                # Look for transitions triggered by rejection
                transitions = db.query(WorkflowTransition).filter(
                    WorkflowTransition.workflow_id == instance.workflow_id,
                    WorkflowTransition.from_state_id == instance.current_state_id
                ).all()
                
                for transition in transitions:
                    # Check if this transition is triggered by rejection
                    if transition.triggers and "rejection" in str(transition.triggers):
                        # Transition to the new state
                        old_state_id = instance.current_state_id
                        instance.current_state_id = transition.to_state_id
                        
                        # Check if new state is final
                        new_state = db.query(WorkflowState).filter(
                            WorkflowState.id == transition.to_state_id
                        ).first()
                        
                        if new_state and new_state.is_final:
                            instance.is_active = False
                            instance.completed_at = datetime.utcnow()
                        
                        # Add history record for the transition
                        history_record = WorkflowHistory(
                            instance_id=instance.id,
                            action_type="state_transition",
                            from_state_id=old_state_id,
                            to_state_id=transition.to_state_id,
                            user_id=current_user["id"],
                            details={
                                "transition_trigger": "rejection",
                                "transition_by": current_user["id"]
                            }
                        )
                        db.add(history_record)
                        db.add(instance)
                        return
