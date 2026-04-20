"""
Pydantic schemas for the workflow plugin.

This module defines the request and response schemas for the workflow API endpoints.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

from .models import WorkflowStepTypeEnum, WorkflowTargetTypeEnum


# Base schemas
class WorkflowBase(BaseModel):
    """Base schema for workflow data."""
    name: str
    description: Optional[str] = None
    target_type: WorkflowTargetTypeEnum
    target_filter: Optional[Dict[str, Any]] = None
    is_active: bool = True
    is_default: bool = False


class WorkflowStepBase(BaseModel):
    """Base schema for workflow step data."""
    name: str
    description: Optional[str] = None
    step_type: WorkflowStepTypeEnum
    step_order: int
    is_required: bool = True
    config: Optional[Dict[str, Any]] = None
    next_step_on_approve: Optional[int] = None
    next_step_on_reject: Optional[int] = None


class WorkflowStateBase(BaseModel):
    """Base schema for workflow state data."""
    name: str
    description: Optional[str] = None
    is_initial: bool = False
    is_final: bool = False
    color: Optional[str] = None


class WorkflowTransitionBase(BaseModel):
    """Base schema for workflow transition data."""
    from_state_id: int
    to_state_id: int
    name: str
    description: Optional[str] = None
    triggers: Optional[List[Dict[str, Any]]] = None


class StepApprovalBase(BaseModel):
    """Base schema for step approval data."""
    status: str = "pending"
    comments: Optional[str] = None


# Create schemas
class WorkflowCreate(WorkflowBase):
    """Schema for creating a new workflow."""
    created_by: Optional[int] = None


class WorkflowStepCreate(WorkflowStepBase):
    """Schema for creating a new workflow step."""
    workflow_id: int
    role_ids: Optional[List[int]] = None  # IDs of roles that can approve this step


class WorkflowStateCreate(WorkflowStateBase):
    """Schema for creating a new workflow state."""
    workflow_id: int


class WorkflowTransitionCreate(WorkflowTransitionBase):
    """Schema for creating a new workflow transition."""
    workflow_id: int


class WorkflowInstanceCreate(BaseModel):
    """Schema for creating a new workflow instance."""
    workflow_id: int
    target_type: WorkflowTargetTypeEnum
    target_id: int
    metadata: Optional[Dict[str, Any]] = None


class StepApprovalCreate(StepApprovalBase):
    """Schema for creating a new step approval."""
    instance_id: int
    step_id: int


# Update schemas
class WorkflowUpdate(BaseModel):
    """Schema for updating an existing workflow."""
    name: Optional[str] = None
    description: Optional[str] = None
    target_filter: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    updated_by: Optional[int] = None


class WorkflowStepUpdate(BaseModel):
    """Schema for updating an existing workflow step."""
    name: Optional[str] = None
    description: Optional[str] = None
    step_type: Optional[WorkflowStepTypeEnum] = None
    step_order: Optional[int] = None
    is_required: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    next_step_on_approve: Optional[int] = None
    next_step_on_reject: Optional[int] = None
    role_ids: Optional[List[int]] = None


class WorkflowStateUpdate(BaseModel):
    """Schema for updating an existing workflow state."""
    name: Optional[str] = None
    description: Optional[str] = None
    is_initial: Optional[bool] = None
    is_final: Optional[bool] = None
    color: Optional[str] = None


class WorkflowTransitionUpdate(BaseModel):
    """Schema for updating an existing workflow transition."""
    name: Optional[str] = None
    description: Optional[str] = None
    triggers: Optional[List[Dict[str, Any]]] = None


class StepApprovalUpdate(StepApprovalBase):
    """Schema for updating an existing step approval."""
    pass


# Response schemas
class RoleResponse(BaseModel):
    """Response schema for roles."""
    id: int
    name: str
    
    class Config:
        from_attributes = True


class WorkflowStepResponse(BaseModel):
    """Response schema for workflow steps."""
    id: int
    workflow_id: int
    name: str
    description: Optional[str] = None
    step_type: WorkflowStepTypeEnum
    step_order: int
    is_required: bool
    config: Optional[Dict[str, Any]] = None
    next_step_on_approve: Optional[int] = None
    next_step_on_reject: Optional[int] = None
    approvers: List[RoleResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkflowStateResponse(BaseModel):
    """Response schema for workflow states."""
    id: int
    workflow_id: int
    name: str
    description: Optional[str] = None
    is_initial: bool
    is_final: bool
    color: Optional[str] = None
    
    class Config:
        from_attributes = True


class WorkflowTransitionResponse(BaseModel):
    """Response schema for workflow transitions."""
    id: int
    workflow_id: int
    from_state_id: int
    to_state_id: int
    name: str
    description: Optional[str] = None
    triggers: Optional[List[Dict[str, Any]]] = None
    from_state: WorkflowStateResponse
    to_state: WorkflowStateResponse
    
    class Config:
        from_attributes = True


class StepApprovalResponse(BaseModel):
    """Response schema for step approvals."""
    id: int
    instance_id: int
    step_id: int
    user_id: Optional[int] = None
    status: str
    decision_at: Optional[datetime] = None
    comments: Optional[str] = None
    created_at: datetime
    user: Optional[Dict[str, Any]] = None
    step: WorkflowStepResponse
    
    class Config:
        from_attributes = True


class WorkflowInstanceResponse(BaseModel):
    """Response schema for workflow instances."""
    id: int
    workflow_id: int
    target_type: WorkflowTargetTypeEnum
    target_id: int
    current_state_id: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    is_active: bool
    metadata: Optional[Dict[str, Any]] = None
    current_state: Optional[WorkflowStateResponse] = None
    approvals: List[StepApprovalResponse] = []
    
    class Config:
        from_attributes = True


class WorkflowHistoryResponse(BaseModel):
    """Response schema for workflow history records."""
    id: int
    instance_id: int
    action_type: str
    from_state_id: Optional[int] = None
    to_state_id: Optional[int] = None
    step_id: Optional[int] = None
    user_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
    from_state: Optional[WorkflowStateResponse] = None
    to_state: Optional[WorkflowStateResponse] = None
    
    class Config:
        from_attributes = True


class WorkflowResponse(BaseModel):
    """Response schema for workflows."""
    id: int
    name: str
    description: Optional[str] = None
    target_type: WorkflowTargetTypeEnum
    target_filter: Optional[Dict[str, Any]] = None
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    steps: List[WorkflowStepResponse] = []
    
    class Config:
        from_attributes = True


class WorkflowDetail(WorkflowResponse):
    """Detailed response schema for workflows, including states and transitions."""
    states: List[WorkflowStateResponse] = []
    transitions: List[WorkflowTransitionResponse] = []
    
    class Config:
        from_attributes = True


# Pagination schemas
class PaginatedResponse(BaseModel):
    """Response schema for paginated results."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int


class PaginatedWorkflowResponse(BaseModel):
    """Response schema for paginated workflow results."""
    items: List[WorkflowResponse]
    total: int
    page: int
    page_size: int
    pages: int
