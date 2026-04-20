"""
Database models for the workflow plugin.

This module defines SQLAlchemy models for workflows, workflow steps, approvals,
and state transitions.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Table
from sqlalchemy.dialects.postgresql import UUID
import enum
import uuid

from app.core.db import Base


class WorkflowStepTypeEnum(str, enum.Enum):
    """Types of workflow steps."""
    APPROVAL = "approval"
    NOTIFICATION = "notification"
    AUTOMATION = "automation"
    CONDITION = "condition"


class WorkflowTargetTypeEnum(str, enum.Enum):
    """Types of workflow targets (what entity the workflow applies to)."""
    CONTENT = "content"
    USER = "user"
    DOCUMENT = "document"
    TASK = "task"
    CUSTOM = "custom"


# Association table for workflow step permissions (which roles can approve)
workflow_step_roles = Table(
    "workflow_step_roles",
    Base.metadata,
    Column("workflow_step_id", Integer, ForeignKey("workflow_steps.id"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("auth_role.id"), primary_key=True)
)


class Workflow(Base):
    """Workflow model defining a configurable approval process."""
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    description = Column(Text)
    target_type = Column(Enum(WorkflowTargetTypeEnum), index=True, nullable=False)
    target_filter = Column(JSON)  # JSON for storing filters that determine what this workflow applies to
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # If true, this is the default workflow for the target type
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("user.id"))
    updated_by = Column(UUID(as_uuid=True), ForeignKey("user.id"))

    # Relationships
    steps = relationship("WorkflowStep", back_populates="workflow", cascade="all, delete-orphan")
    instances = relationship("WorkflowInstance", back_populates="workflow")


class WorkflowStep(Base):
    """Step in a workflow process."""
    __tablename__ = "workflow_steps"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    step_type = Column(Enum(WorkflowStepTypeEnum), nullable=False)
    step_order = Column(Integer, nullable=False)  # Order of execution in the workflow
    is_required = Column(Boolean, default=True)
    config = Column(JSON)  # Configuration for notifications, automations, or conditions
    
    # For branching workflows - next step depends on approval decision
    next_step_on_approve = Column(Integer, ForeignKey("workflow_steps.id"))
    next_step_on_reject = Column(Integer, ForeignKey("workflow_steps.id"))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    workflow = relationship("Workflow", back_populates="steps")
    approvers = relationship("Role", secondary=workflow_step_roles, backref="approver_for_steps")
    approvals = relationship("StepApproval", back_populates="step")
    
    # Self-referential relationships for branching
    approve_next = relationship("WorkflowStep", foreign_keys=[next_step_on_approve], remote_side=[id])
    reject_next = relationship("WorkflowStep", foreign_keys=[next_step_on_reject], remote_side=[id])


class WorkflowState(Base):
    """Possible states within a workflow."""
    __tablename__ = "workflow_states"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_initial = Column(Boolean, default=False)
    is_final = Column(Boolean, default=False)
    color = Column(String(50))  # For UI representation
    
    # Relationships
    workflow = relationship("Workflow")
    transitions_from = relationship("WorkflowTransition", back_populates="from_state", 
                                    foreign_keys="WorkflowTransition.from_state_id")
    transitions_to = relationship("WorkflowTransition", back_populates="to_state", 
                                  foreign_keys="WorkflowTransition.to_state_id")


class WorkflowTransition(Base):
    """Transition between workflow states."""
    __tablename__ = "workflow_transitions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    from_state_id = Column(Integer, ForeignKey("workflow_states.id", ondelete="CASCADE"), nullable=False)
    to_state_id = Column(Integer, ForeignKey("workflow_states.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    triggers = Column(JSON)  # JSON array of trigger types (approval, time-based, etc.)
    
    # Relationships
    workflow = relationship("Workflow")
    from_state = relationship("WorkflowState", foreign_keys=[from_state_id], back_populates="transitions_from")
    to_state = relationship("WorkflowState", foreign_keys=[to_state_id], back_populates="transitions_to")


class WorkflowInstance(Base):
    """Instance of a workflow for a specific entity."""
    __tablename__ = "workflow_instances"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    target_type = Column(Enum(WorkflowTargetTypeEnum), nullable=False)
    target_id = Column(Integer, nullable=False)  # ID of the entity this workflow applies to
    current_state_id = Column(Integer, ForeignKey("workflow_states.id"))
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    instance_metadata = Column(JSON)  # Additional metadata about this instance
    
    # Relationships
    workflow = relationship("Workflow", back_populates="instances")
    current_state = relationship("WorkflowState")
    approvals = relationship("StepApproval", back_populates="instance")


class StepApproval(Base):
    """Approval record for a workflow step."""
    __tablename__ = "step_approvals"

    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(Integer, ForeignKey("workflow_steps.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"))
    status = Column(String(50), index=True)  # pending, approved, rejected
    decision_at = Column(DateTime)
    comments = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    instance = relationship("WorkflowInstance", back_populates="approvals")
    step = relationship("WorkflowStep", back_populates="approvals")
    user = relationship("User")


class WorkflowHistory(Base):
    """History of workflow state changes and actions."""
    __tablename__ = "workflow_history"

    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(50), nullable=False)  # state_change, approval, comment, etc.
    from_state_id = Column(Integer, ForeignKey("workflow_states.id"))
    to_state_id = Column(Integer, ForeignKey("workflow_states.id"))
    step_id = Column(Integer, ForeignKey("workflow_steps.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"))
    details = Column(JSON)  # Additional details about the action
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    instance = relationship("WorkflowInstance")
    from_state = relationship("WorkflowState", foreign_keys=[from_state_id])
    to_state = relationship("WorkflowState", foreign_keys=[to_state_id])
    step = relationship("WorkflowStep")
    user = relationship("User")
