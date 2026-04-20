"""
Workflow manager utility functions.

This module provides helper functions for managing workflows and workflow instances.
"""
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session

from app.plugins.workflow.models import (
    Workflow, WorkflowStep, WorkflowState, 
    WorkflowTransition, WorkflowInstance,
    StepApproval, WorkflowHistory, WorkflowTargetTypeEnum
)


class WorkflowManager:
    """Utility class for workflow operations."""
    
    @staticmethod
    def get_workflow_for_target(
        db: Session, 
        target_type: WorkflowTargetTypeEnum, 
        target_id: int,
        target_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Workflow]:
        """
        Find the most appropriate workflow for a given target.
        
        Args:
            db: Database session
            target_type: Type of the target entity
            target_id: ID of the target entity
            target_metadata: Additional metadata about the target for matching
            
        Returns:
            The most appropriate workflow or None if no matching workflow found
        """
        # First try to find a specific workflow that matches target metadata
        if target_metadata:
            # This would be a more complex matching logic in a real app
            # For demo purposes, we'll just find workflows with the target type
            pass
        
        # If no specific match, use the default workflow for this target type
        default_workflow = db.query(Workflow).filter(
            Workflow.target_type == target_type,
            Workflow.is_default == True,
            Workflow.is_active == True
        ).first()
        
        if default_workflow:
            return default_workflow
        
        # If no default, return any active workflow for this target type
        return db.query(Workflow).filter(
            Workflow.target_type == target_type,
            Workflow.is_active == True
        ).first()
    
    @staticmethod
    def start_workflow(
        db: Session,
        workflow_id: int,
        target_type: WorkflowTargetTypeEnum,
        target_id: int,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[WorkflowInstance]:
        """
        Start a new workflow instance.
        
        Args:
            db: Database session
            workflow_id: ID of the workflow to start
            target_type: Type of the target entity
            target_id: ID of the target entity
            user_id: ID of the user starting the workflow
            metadata: Additional metadata for the workflow instance
            
        Returns:
            Newly created workflow instance or None if creation failed
        """
        # Get the workflow
        workflow = db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.is_active == True
        ).first()
        
        if not workflow:
            return None
        
        # Get initial state
        initial_state = db.query(WorkflowState).filter(
            WorkflowState.workflow_id == workflow_id,
            WorkflowState.is_initial == True
        ).first()
        
        if not initial_state:
            return None
        
        # Create instance
        instance = WorkflowInstance(
            workflow_id=workflow_id,
            target_type=target_type,
            target_id=target_id,
            current_state_id=initial_state.id,
            metadata=metadata or {}
        )
        
        db.add(instance)
        db.flush()
        
        # Create history record
        history = WorkflowHistory(
            instance_id=instance.id,
            action_type="instance_created",
            to_state_id=initial_state.id,
            user_id=user_id,
            details={
                "created_by": user_id,
                "target_type": target_type,
                "target_id": target_id
            }
        )
        db.add(history)
        
        # Create approval records for first steps
        first_steps = db.query(WorkflowStep).filter(
            WorkflowStep.workflow_id == workflow_id,
            WorkflowStep.step_order == 1
        ).all()
        
        for step in first_steps:
            approval = StepApproval(
                instance_id=instance.id,
                step_id=step.id,
                status="pending"
            )
            db.add(approval)
        
        db.commit()
        db.refresh(instance)
        
        return instance
    
    @staticmethod
    def transition_state(
        db: Session,
        instance_id: int,
        to_state_id: int,
        user_id: int,
        reason: str = "manual"
    ) -> Optional[WorkflowInstance]:
        """
        Transition a workflow instance to a new state.
        
        Args:
            db: Database session
            instance_id: ID of the workflow instance
            to_state_id: ID of the target state
            user_id: ID of the user performing the transition
            reason: Reason for the transition
            
        Returns:
            Updated workflow instance or None if transition failed
        """
        # Get instance
        instance = db.query(WorkflowInstance).filter(
            WorkflowInstance.id == instance_id,
            WorkflowInstance.is_active == True
        ).first()
        
        if not instance:
            return None
        
        # Get target state
        target_state = db.query(WorkflowState).filter(
            WorkflowState.id == to_state_id,
            WorkflowState.workflow_id == instance.workflow_id
        ).first()
        
        if not target_state:
            return None
        
        # Verify transition is valid
        valid_transition = True
        if instance.current_state_id:
            transition = db.query(WorkflowTransition).filter(
                WorkflowTransition.from_state_id == instance.current_state_id,
                WorkflowTransition.to_state_id == to_state_id
            ).first()
            valid_transition = transition is not None
        
        if not valid_transition:
            return None
        
        # Store current state for history
        from_state_id = instance.current_state_id
        
        # Update instance
        instance.current_state_id = to_state_id
        
        # If target state is final, mark instance as completed
        if target_state.is_final:
            from datetime import datetime
            instance.is_active = False
            instance.completed_at = datetime.utcnow()
        
        # Add history record
        history = WorkflowHistory(
            instance_id=instance_id,
            action_type="state_transition",
            from_state_id=from_state_id,
            to_state_id=to_state_id,
            user_id=user_id,
            details={
                "reason": reason,
                "transition_by": user_id
            }
        )
        db.add(history)
        
        db.add(instance)
        db.commit()
        db.refresh(instance)
        
        return instance
    
    @staticmethod
    def get_pending_approvals_for_user(
        db: Session,
        user_id: int,
        role_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        Get pending approvals for a user based on their roles.
        
        Args:
            db: Database session
            user_id: ID of the user
            role_ids: List of role IDs the user has
            
        Returns:
            List of pending approvals the user can act on
        """
        # This is a simplified implementation
        # In a real app, you would join with roles and check permissions
        
        # Get all pending approvals
        approvals = db.query(StepApproval).filter(
            StepApproval.status == "pending"
        ).join(
            WorkflowInstance, WorkflowInstance.id == StepApproval.instance_id
        ).filter(
            WorkflowInstance.is_active == True
        ).all()
        
        # Filter for approvals the user can act on
        user_approvals = []
        for approval in approvals:
            step = db.query(WorkflowStep).filter(WorkflowStep.id == approval.step_id).first()
            if not step:
                continue
            
            # Check if user's roles intersect with approver roles
            # In a real app, this would be a database join
            user_can_approve = False
            
            # Simplified for demo: user can approve any step they have a role for
            user_can_approve = True
            
            if user_can_approve:
                instance = db.query(WorkflowInstance).filter(
                    WorkflowInstance.id == approval.instance_id
                ).first()
                
                if instance:
                    user_approvals.append({
                        "approval_id": approval.id,
                        "step_id": step.id,
                        "step_name": step.name,
                        "instance_id": instance.id,
                        "workflow_id": instance.workflow_id,
                        "target_type": instance.target_type,
                        "target_id": instance.target_id,
                        "created_at": approval.created_at
                    })
        
        return user_approvals
    
    @staticmethod
    def clone_workflow(
        db: Session,
        workflow_id: int,
        new_name: str,
        user_id: int
    ) -> Optional[Workflow]:
        """
        Clone an existing workflow with all its steps, states, and transitions.
        
        Args:
            db: Database session
            workflow_id: ID of the workflow to clone
            new_name: Name for the cloned workflow
            user_id: ID of the user cloning the workflow
            
        Returns:
            Newly created workflow or None if cloning failed
        """
        # Get original workflow
        original = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not original:
            return None
        
        # Create new workflow
        new_workflow = Workflow(
            name=new_name,
            description=f"Cloned from {original.name}",
            target_type=original.target_type,
            target_filter=original.target_filter,
            is_active=True,
            is_default=False,
            created_by=user_id,
            updated_by=user_id
        )
        
        db.add(new_workflow)
        db.flush()
        
        # Clone states
        state_map = {}  # Maps original state IDs to new state IDs
        
        original_states = db.query(WorkflowState).filter(
            WorkflowState.workflow_id == workflow_id
        ).all()
        
        for state in original_states:
            new_state = WorkflowState(
                workflow_id=new_workflow.id,
                name=state.name,
                description=state.description,
                is_initial=state.is_initial,
                is_final=state.is_final,
                color=state.color
            )
            
            db.add(new_state)
            db.flush()
            
            state_map[state.id] = new_state.id
        
        # Clone steps
        step_map = {}  # Maps original step IDs to new step IDs
        
        original_steps = db.query(WorkflowStep).filter(
            WorkflowStep.workflow_id == workflow_id
        ).all()
        
        for step in original_steps:
            new_step = WorkflowStep(
                workflow_id=new_workflow.id,
                name=step.name,
                description=step.description,
                step_type=step.step_type,
                step_order=step.step_order,
                is_required=step.is_required,
                config=step.config
            )
            
            db.add(new_step)
            db.flush()
            
            step_map[step.id] = new_step.id
            
            # Clone step approver roles
            for role in step.approvers:
                new_step.approvers.append(role)
        
        # Update step next references
        for step in original_steps:
            if step.next_step_on_approve and step.next_step_on_approve in step_map:
                new_step_id = step_map[step.id]
                new_next_step_id = step_map[step.next_step_on_approve]
                
                new_step = db.query(WorkflowStep).filter(WorkflowStep.id == new_step_id).first()
                if new_step:
                    new_step.next_step_on_approve = new_next_step_id
                    db.add(new_step)
            
            if step.next_step_on_reject and step.next_step_on_reject in step_map:
                new_step_id = step_map[step.id]
                new_next_step_id = step_map[step.next_step_on_reject]
                
                new_step = db.query(WorkflowStep).filter(WorkflowStep.id == new_step_id).first()
                if new_step:
                    new_step.next_step_on_reject = new_next_step_id
                    db.add(new_step)
        
        # Clone transitions
        original_transitions = db.query(WorkflowTransition).filter(
            WorkflowTransition.workflow_id == workflow_id
        ).all()
        
        for transition in original_transitions:
            if transition.from_state_id in state_map and transition.to_state_id in state_map:
                new_transition = WorkflowTransition(
                    workflow_id=new_workflow.id,
                    from_state_id=state_map[transition.from_state_id],
                    to_state_id=state_map[transition.to_state_id],
                    name=transition.name,
                    description=transition.description,
                    triggers=transition.triggers
                )
                
                db.add(new_transition)
        
        db.commit()
        db.refresh(new_workflow)
        
        return new_workflow
