"""
Payment approval workflows.

This module provides workflow definitions for payment approvals with multi-user
authorization requirements.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.plugins.advanced_auth.models import User
from app.plugins.workflow.main import workflow_engine, WorkflowDefinition, WorkflowStep, WorkflowContext
from ..models.payment import PaymentDB, PaymentApprovalStepDB, ApprovalStatus, PaymentStatus

logger = logging.getLogger("kaapi.payment.workflow")

class PaymentApprovalContext(WorkflowContext):
    """Context for payment approval workflows."""
    
    def __init__(
        self, 
        payment_id: int, 
        payment: Optional[PaymentDB] = None,
        approvers: Optional[List[int]] = None,
        current_step: int = 0,
        initiated_by: Optional[int] = None
    ):
        self.payment_id = payment_id
        self.payment = payment
        self.approvers = approvers or []
        self.current_step = current_step
        self.initiated_by = initiated_by
        self.status = "pending"
        self.result = None

class ApprovalStep(WorkflowStep):
    """A single step in the payment approval workflow."""
    
    def __init__(self, step_index: int, approver_id: int = None, role: str = None):
        self.step_index = step_index
        self.approver_id = approver_id
        self.role = role
        
    async def execute(self, context: PaymentApprovalContext, db: Session) -> Union[bool, Dict[str, Any]]:
        """Execute the approval step."""
        # This is usually triggered by an external action (approve/reject API call)
        # In the actual step execution, we just check if this step has been completed
        if not context.payment:
            # Load the payment if not already loaded
            payment = db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
            if not payment:
                return {
                    "success": False,
                    "message": "Payment not found"
                }
            context.payment = payment
        
        # Find the approval step for this index
        approval_step = db.query(PaymentApprovalStepDB).filter(
            PaymentApprovalStepDB.payment_id == context.payment_id,
            PaymentApprovalStepDB.step_order == self.step_index
        ).first()
        
        if not approval_step:
            return {
                "success": False,
                "message": f"Approval step {self.step_index} not found"
            }
        
        # Check if the step has been completed
        if approval_step.status == ApprovalStatus.APPROVED.value:
            return True
        elif approval_step.status == ApprovalStatus.REJECTED.value:
            return {
                "success": False,
                "message": "Approval rejected",
                "rejection_reason": approval_step.comments
            }
        
        # Step is still pending
        return {
            "success": False,
            "message": "Approval step is still pending"
        }

class StandardApprovalWorkflow(WorkflowDefinition):
    """
    Standard sequential approval workflow.
    
    This workflow requires sequential approval from a list of approvers.
    """
    
    def __init__(self):
        self.name = "standard_payment_approval"
        self.description = "Standard sequential payment approval workflow"
    
    def initialize_workflow(self, context: PaymentApprovalContext, db: Session) -> List[WorkflowStep]:
        """Initialize the workflow steps based on context."""
        steps = []
        
        # Create steps for each approver
        for i, approver_id in enumerate(context.approvers):
            steps.append(ApprovalStep(step_index=i, approver_id=approver_id))
        
        # Create approval steps in the database
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Set payment status to pending approval
        payment.status = PaymentStatus.PENDING_APPROVAL.value
        
        # Create approval step records
        for i, approver_id in enumerate(context.approvers):
            approval_step = PaymentApprovalStepDB(
                payment_id=payment.id,
                approver_id=approver_id,
                status=ApprovalStatus.PENDING.value,
                step_order=i
            )
            db.add(approval_step)
        
        db.commit()
        
        return steps
    
    async def on_complete(self, context: PaymentApprovalContext, db: Session) -> Dict[str, Any]:
        """Handle workflow completion."""
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            return {
                "success": False,
                "message": "Payment not found"
            }
        
        # Update payment status
        payment.status = PaymentStatus.APPROVED.value
        payment.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Payment approved successfully",
            "payment_id": payment.id,
            "status": payment.status
        }
    
    async def on_failure(self, context: PaymentApprovalContext, reason: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Handle workflow failure."""
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            return {
                "success": False,
                "message": "Payment not found"
            }
        
        # Update payment status
        payment.status = PaymentStatus.CANCELLED.value
        payment.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": False,
            "message": "Payment approval workflow failed",
            "payment_id": payment.id,
            "status": payment.status,
            "reason": reason.get("message", "Unknown reason")
        }

class HierarchicalApprovalWorkflow(WorkflowDefinition):
    """
    Hierarchical approval workflow.
    
    This workflow requires approval from users in different roles,
    such as department manager, finance manager, and CFO.
    """
    
    def __init__(self):
        self.name = "hierarchical_payment_approval"
        self.description = "Hierarchical payment approval workflow with role-based approvals"
    
    def initialize_workflow(self, context: PaymentApprovalContext, db: Session) -> List[WorkflowStep]:
        """Initialize the workflow steps based on context."""
        # In a real implementation, you would configure this with roles
        # For simplicity, we'll use the same sequential approval steps
        steps = []
        
        # Create steps for each approver
        for i, approver_id in enumerate(context.approvers):
            steps.append(ApprovalStep(step_index=i, approver_id=approver_id))
        
        # Create approval steps in the database
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Set payment status to pending approval
        payment.status = PaymentStatus.PENDING_APPROVAL.value
        
        # Create approval step records
        for i, approver_id in enumerate(context.approvers):
            approval_step = PaymentApprovalStepDB(
                payment_id=payment.id,
                approver_id=approver_id,
                status=ApprovalStatus.PENDING.value,
                step_order=i
            )
            db.add(approval_step)
        
        db.commit()
        
        return steps
    
    async def on_complete(self, context: PaymentApprovalContext, db: Session) -> Dict[str, Any]:
        """Handle workflow completion."""
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            return {
                "success": False,
                "message": "Payment not found"
            }
        
        # Update payment status
        payment.status = PaymentStatus.APPROVED.value
        payment.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Payment approved successfully through hierarchical workflow",
            "payment_id": payment.id,
            "status": payment.status
        }
    
    async def on_failure(self, context: PaymentApprovalContext, reason: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Handle workflow failure."""
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            return {
                "success": False,
                "message": "Payment not found"
            }
        
        # Update payment status
        payment.status = PaymentStatus.CANCELLED.value
        payment.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": False,
            "message": "Payment approval workflow failed",
            "payment_id": payment.id,
            "status": payment.status,
            "reason": reason.get("message", "Unknown reason")
        }

class AmountBasedApprovalWorkflow(WorkflowDefinition):
    """
    Amount-based approval workflow.
    
    This workflow determines the required approvals based on the payment amount.
    Different thresholds require different levels of approval.
    """
    
    def __init__(self):
        self.name = "amount_based_payment_approval"
        self.description = "Amount-based payment approval workflow with different thresholds"
        
        # Define thresholds and required approvals
        self.thresholds = [
            {"amount": 1000, "approvers": ["team_lead"]},
            {"amount": 10000, "approvers": ["team_lead", "department_manager"]},
            {"amount": 50000, "approvers": ["team_lead", "department_manager", "finance_manager"]},
            {"amount": float('inf'), "approvers": ["team_lead", "department_manager", "finance_manager", "cfo"]}
        ]
    
    def get_required_roles(self, amount: float) -> List[str]:
        """Get the required roles for approval based on the amount."""
        for threshold in self.thresholds:
            if amount <= threshold["amount"]:
                return threshold["approvers"]
        
        # Fallback to the highest threshold
        return self.thresholds[-1]["approvers"]
    
    def get_users_for_roles(self, roles: List[str], db: Session) -> List[int]:
        """Get users for the specified roles."""
        # In a real implementation, this would query users with specific roles
        # For this example, we'll use a simple mapping for demonstration
        
        # This would be fetched from the database in a real application
        role_to_user_map = {
            "team_lead": 2,
            "department_manager": 3,
            "finance_manager": 4,
            "cfo": 5
        }
        
        return [role_to_user_map.get(role) for role in roles if role in role_to_user_map]
    
    def initialize_workflow(self, context: PaymentApprovalContext, db: Session) -> List[WorkflowStep]:
        """Initialize the workflow steps based on context."""
        steps = []
        
        # Load the payment if not already loaded
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Determine required roles based on amount
        required_roles = self.get_required_roles(payment.amount)
        
        # Get users for the roles
        approvers = self.get_users_for_roles(required_roles, db)
        
        # If approvers are explicitly specified, use those instead
        if context.approvers:
            approvers = context.approvers
        
        # Create steps for each approver
        for i, approver_id in enumerate(approvers):
            steps.append(ApprovalStep(step_index=i, approver_id=approver_id))
        
        # Set payment status to pending approval
        payment.status = PaymentStatus.PENDING_APPROVAL.value
        
        # Create approval step records
        for i, approver_id in enumerate(approvers):
            approval_step = PaymentApprovalStepDB(
                payment_id=payment.id,
                approver_id=approver_id,
                status=ApprovalStatus.PENDING.value,
                step_order=i
            )
            db.add(approval_step)
        
        db.commit()
        
        return steps
    
    async def on_complete(self, context: PaymentApprovalContext, db: Session) -> Dict[str, Any]:
        """Handle workflow completion."""
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            return {
                "success": False,
                "message": "Payment not found"
            }
        
        # Update payment status
        payment.status = PaymentStatus.APPROVED.value
        payment.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Payment approved successfully through amount-based workflow",
            "payment_id": payment.id,
            "status": payment.status
        }
    
    async def on_failure(self, context: PaymentApprovalContext, reason: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Handle workflow failure."""
        payment = context.payment or db.query(PaymentDB).filter(PaymentDB.id == context.payment_id).first()
        if not payment:
            return {
                "success": False,
                "message": "Payment not found"
            }
        
        # Update payment status
        payment.status = PaymentStatus.CANCELLED.value
        payment.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": False,
            "message": "Payment approval workflow failed",
            "payment_id": payment.id,
            "status": payment.status,
            "reason": reason.get("message", "Unknown reason")
        }

# Register workflows
workflow_engine.register_workflow("standard_payment_approval", StandardApprovalWorkflow())
workflow_engine.register_workflow("hierarchical_payment_approval", HierarchicalApprovalWorkflow())
workflow_engine.register_workflow("amount_based_payment_approval", AmountBasedApprovalWorkflow())

# Functions for working with payment approval workflows

async def start_payment_approval_workflow(
    db: Session,
    payment_id: int,
    workflow_name: str = "standard_payment_approval",
    approvers: List[int] = None,
    initiated_by: int = None
) -> Dict[str, Any]:
    """Start a payment approval workflow."""
    # Load the payment
    payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Check if there's already an approval workflow
    existing_steps = db.query(PaymentApprovalStepDB).filter(
        PaymentApprovalStepDB.payment_id == payment_id
    ).count()
    
    if existing_steps > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment approval workflow already started"
        )
    
    # Create workflow context
    context = PaymentApprovalContext(
        payment_id=payment_id,
        payment=payment,
        approvers=approvers,
        initiated_by=initiated_by
    )
    
    # Start the workflow
    result = await workflow_engine.start_workflow(workflow_name, context, db)
    
    return result

async def approve_payment_step(
    db: Session,
    payment_id: int,
    user_id: int,
    comments: Optional[str] = None
) -> Dict[str, Any]:
    """Approve a payment step."""
    # Find the payment
    payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Find the approval step for this user
    approval_step = db.query(PaymentApprovalStepDB).filter(
        PaymentApprovalStepDB.payment_id == payment_id,
        PaymentApprovalStepDB.approver_id == user_id,
        PaymentApprovalStepDB.status == ApprovalStatus.PENDING.value
    ).first()
    
    if not approval_step:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending approval step found for this user"
        )
    
    # Update the approval step
    approval_step.status = ApprovalStatus.APPROVED.value
    approval_step.comments = comments
    approval_step.updated_at = datetime.utcnow()
    
    # Find the associated workflow instance
    context = PaymentApprovalContext(payment_id=payment_id, payment=payment)
    
    # Progress the workflow
    try:
        workflow_result = await workflow_engine.continue_workflow(
            "standard_payment_approval",  # This should be fetched from the stored workflow
            context,
            approval_step.step_order,
            db
        )
        
        # Check if all steps are approved
        all_approved = True
        next_pending_step = None
        
        steps = db.query(PaymentApprovalStepDB).filter(
            PaymentApprovalStepDB.payment_id == payment_id
        ).order_by(PaymentApprovalStepDB.step_order).all()
        
        for step in steps:
            if step.status != ApprovalStatus.APPROVED.value:
                all_approved = False
                if step.status == ApprovalStatus.PENDING.value:
                    next_pending_step = step
                break
        
        # If all steps are approved, update payment status
        if all_approved:
            # The workflow's on_complete should handle this
            pass
        
        db.commit()
        
        return {
            "success": True,
            "message": "Payment step approved successfully",
            "payment_id": payment_id,
            "step_order": approval_step.step_order,
            "all_approved": all_approved,
            "next_pending_approver": next_pending_step.approver_id if next_pending_step else None,
            "workflow_result": workflow_result
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error approving payment step: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving payment step: {str(e)}"
        )

async def reject_payment_step(
    db: Session,
    payment_id: int,
    user_id: int,
    reason: str
) -> Dict[str, Any]:
    """Reject a payment step."""
    # Find the payment
    payment = db.query(PaymentDB).filter(PaymentDB.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Find the approval step for this user
    approval_step = db.query(PaymentApprovalStepDB).filter(
        PaymentApprovalStepDB.payment_id == payment_id,
        PaymentApprovalStepDB.approver_id == user_id,
        PaymentApprovalStepDB.status == ApprovalStatus.PENDING.value
    ).first()
    
    if not approval_step:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending approval step found for this user"
        )
    
    # Update the approval step
    approval_step.status = ApprovalStatus.REJECTED.value
    approval_step.comments = reason
    approval_step.updated_at = datetime.utcnow()
    
    # Update payment status
    payment.status = PaymentStatus.CANCELLED.value
    payment.updated_at = datetime.utcnow()
    
    # Find the associated workflow instance
    context = PaymentApprovalContext(payment_id=payment_id, payment=payment)
    
    # Fail the workflow
    try:
        workflow_result = await workflow_engine.fail_workflow(
            "standard_payment_approval",  # This should be fetched from the stored workflow
            context,
            {"message": reason},
            db
        )
        
        db.commit()
        
        return {
            "success": True,
            "message": "Payment rejected successfully",
            "payment_id": payment_id,
            "reason": reason,
            "workflow_result": workflow_result
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting payment: {str(e)}"
        )

# Single entry point for payment approval workflow
payment_approval_workflow = {
    "start": start_payment_approval_workflow,
    "approve": approve_payment_step,
    "reject": reject_payment_step
}
