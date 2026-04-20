"""
Workflow Engine implementation.

This module provides the core engine for executing and tracking workflows.
"""
import logging
from typing import Dict, Any, List, Optional, Type, Union, Callable
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

logger = logging.getLogger("kaapi.workflow.engine")


class WorkflowContext:
    """
    Base class for workflow context data.
    
    Workflow contexts hold the state and data necessary for workflow execution.
    """
    
    def __init__(self):
        self.status = "pending"
        self.result = None
        self.data = {}
        
    def update_data(self, data: Dict[str, Any]):
        """
        Update the context data.
        
        Args:
            data: Data to update
        """
        self.data.update(data)
        
    def get_data(self, key: str, default: Any = None) -> Any:
        """
        Get a data item from the context.
        
        Args:
            key: Data key
            default: Default value if key is not found
            
        Returns:
            The data value
        """
        return self.data.get(key, default)


class WorkflowStep(ABC):
    """
    Base class for workflow steps.
    
    Workflow steps represent a single task or action in a workflow.
    """
    
    @abstractmethod
    async def execute(self, context: WorkflowContext, db: Session) -> Union[bool, Dict[str, Any]]:
        """
        Execute the step.
        
        Args:
            context: Workflow context
            db: Database session
            
        Returns:
            True if the step was successful, False or error dict if failed
        """
        pass


class WorkflowDefinition(ABC):
    """
    Base class for workflow definitions.
    
    Workflow definitions define the structure and behavior of a workflow.
    """
    
    def __init__(self):
        self.name = "base_workflow"
        self.description = "Base workflow definition"
        self.steps = []
    
    @abstractmethod
    def initialize_workflow(self, context: WorkflowContext, db: Session):
        """
        Initialize the workflow steps based on context.
        
        Args:
            context: Workflow context
            db: Database session
        """
        pass
    
    @abstractmethod
    def on_complete(self, context: WorkflowContext, db: Session):
        """
        Handle workflow completion.
        
        Args:
            context: Workflow context
            db: Database session
        """
        pass
    
    @abstractmethod
    def on_failure(self, context: WorkflowContext, reason: Dict[str, Any], db: Session):
        """
        Handle workflow failure.
        
        Args:
            context: Workflow context
            reason: Failure reason
            db: Database session
        """
        pass


class WorkflowEngine:
    """
    Workflow execution engine.
    
    This class is responsible for registering, executing, and managing workflows.
    """
    
    def __init__(self):
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.active_workflow_instances: Dict[str, Dict[str, Any]] = {}
    
    def register_workflow(self, name: str, workflow: WorkflowDefinition) -> None:
        """
        Register a workflow with the engine.
        
        Args:
            name: Workflow name
            workflow: Workflow definition
        """
        self.workflows[name] = workflow
        logger.info(f"Registered workflow: {name}")
    
    def get_workflow(self, name: str) -> Optional[WorkflowDefinition]:
        """
        Get a workflow by name.
        
        Args:
            name: Workflow name
            
        Returns:
            Workflow definition or None if not found
        """
        return self.workflows.get(name)
    
    def list_workflows(self) -> List[Dict[str, str]]:
        """
        List all registered workflows.
        
        Returns:
            List of workflow information
        """
        return [
            {"name": name, "description": workflow.description}
            for name, workflow in self.workflows.items()
        ]
    
    async def start_workflow(
        self, 
        workflow_name: str, 
        context: WorkflowContext, 
        db: Session,
        instance_id: str = None
    ) -> Dict[str, Any]:
        """
        Start a workflow execution.
        
        Args:
            workflow_name: Name of the workflow to start
            context: Workflow context
            db: Database session
            instance_id: Optional workflow instance ID
            
        Returns:
            Workflow execution information
            
        Raises:
            ValueError: If the workflow is not found
        """
        workflow = self.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_name}")
        
        # Generate an instance ID if not provided
        if not instance_id:
            import uuid
            instance_id = str(uuid.uuid4())
        
        # Initialize the workflow
        workflow.initialize_workflow(context, db)
        
        # Store workflow instance
        self.active_workflow_instances[instance_id] = {
            "workflow_name": workflow_name,
            "context": context,
            "current_step": 0,
            "status": "running"
        }
        
        logger.info(f"Started workflow {workflow_name} with instance ID {instance_id}")
        
        return {
            "instance_id": instance_id,
            "workflow_name": workflow_name,
            "status": "running"
        }
    
    async def execute_step(
        self, 
        instance_id: str, 
        step_index: int, 
        db: Session
    ) -> Dict[str, Any]:
        """
        Execute a specific step in a workflow.
        
        Args:
            instance_id: Workflow instance ID
            step_index: Step index to execute
            db: Database session
            
        Returns:
            Step execution result
            
        Raises:
            ValueError: If the instance is not found or the step is invalid
        """
        if instance_id not in self.active_workflow_instances:
            raise ValueError(f"Workflow instance not found: {instance_id}")
        
        instance = self.active_workflow_instances[instance_id]
        workflow_name = instance["workflow_name"]
        context = instance["context"]
        
        workflow = self.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_name}")
        
        if step_index < 0 or step_index >= len(workflow.steps):
            raise ValueError(f"Invalid step index: {step_index}")
        
        # Execute the step
        try:
            step = workflow.steps[step_index]
            result = await step.execute(context, db)
            
            if result is True:
                # Step completed successfully
                instance["current_step"] = step_index + 1
                
                # Check if the workflow is complete
                if instance["current_step"] >= len(workflow.steps):
                    instance["status"] = "completed"
                    workflow.on_complete(context, db)
                
                return {
                    "instance_id": instance_id,
                    "step_index": step_index,
                    "status": "success",
                    "workflow_status": instance["status"]
                }
            else:
                # Step failed
                instance["status"] = "failed"
                
                if isinstance(result, dict):
                    failure_reason = result
                else:
                    failure_reason = {"error": "Step execution failed"}
                
                workflow.on_failure(context, failure_reason, db)
                
                return {
                    "instance_id": instance_id,
                    "step_index": step_index,
                    "status": "failed",
                    "reason": failure_reason,
                    "workflow_status": "failed"
                }
        
        except Exception as e:
            # Handle exceptions during step execution
            logger.exception(f"Error executing workflow step: {str(e)}")
            
            instance["status"] = "failed"
            failure_reason = {"error": str(e)}
            
            workflow.on_failure(context, failure_reason, db)
            
            return {
                "instance_id": instance_id,
                "step_index": step_index,
                "status": "failed",
                "reason": failure_reason,
                "workflow_status": "failed"
            }
    
    async def execute_workflow(
        self, 
        instance_id: str, 
        db: Session
    ) -> Dict[str, Any]:
        """
        Execute all steps in a workflow.
        
        Args:
            instance_id: Workflow instance ID
            db: Database session
            
        Returns:
            Workflow execution result
            
        Raises:
            ValueError: If the instance is not found
        """
        if instance_id not in self.active_workflow_instances:
            raise ValueError(f"Workflow instance not found: {instance_id}")
        
        instance = self.active_workflow_instances[instance_id]
        workflow_name = instance["workflow_name"]
        context = instance["context"]
        
        workflow = self.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_name}")
        
        # Execute all remaining steps
        current_step = instance["current_step"]
        while current_step < len(workflow.steps) and instance["status"] == "running":
            result = await self.execute_step(instance_id, current_step, db)
            
            if result["status"] == "failed":
                return result
            
            current_step = instance["current_step"]
        
        return {
            "instance_id": instance_id,
            "status": instance["status"],
            "steps_executed": current_step
        }
    
    def get_workflow_status(self, instance_id: str) -> Dict[str, Any]:
        """
        Get the status of a workflow instance.
        
        Args:
            instance_id: Workflow instance ID
            
        Returns:
            Workflow status
            
        Raises:
            ValueError: If the instance is not found
        """
        if instance_id not in self.active_workflow_instances:
            raise ValueError(f"Workflow instance not found: {instance_id}")
        
        instance = self.active_workflow_instances[instance_id]
        
        return {
            "instance_id": instance_id,
            "workflow_name": instance["workflow_name"],
            "status": instance["status"],
            "current_step": instance["current_step"]
        }
    
    def list_active_workflows(self) -> List[Dict[str, Any]]:
        """
        List all active workflow instances.
        
        Returns:
            List of active workflow instance information
        """
        return [
            {
                "instance_id": instance_id,
                "workflow_name": instance["workflow_name"],
                "status": instance["status"],
                "current_step": instance["current_step"]
            }
            for instance_id, instance in self.active_workflow_instances.items()
        ]
    
    def cancel_workflow(self, instance_id: str) -> Dict[str, Any]:
        """
        Cancel a workflow instance.
        
        Args:
            instance_id: Workflow instance ID
            
        Returns:
            Cancellation result
            
        Raises:
            ValueError: If the instance is not found
        """
        if instance_id not in self.active_workflow_instances:
            raise ValueError(f"Workflow instance not found: {instance_id}")
        
        instance = self.active_workflow_instances[instance_id]
        instance["status"] = "cancelled"
        
        logger.info(f"Cancelled workflow instance: {instance_id}")
        
        return {
            "instance_id": instance_id,
            "status": "cancelled"
        }


# Create a singleton instance of the workflow engine
workflow_engine = WorkflowEngine()
