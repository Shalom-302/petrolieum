"""
Tests for the workflow plugin.

This file contains both unit tests and integration tests for the workflow plugin.
- Unit tests: Test individual components without external dependencies
- Integration tests: Test the full functionality with an actual database
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.workflow import router
from app.plugins.workflow.models import (
    Workflow, WorkflowStep, WorkflowState, 
    WorkflowTransition, WorkflowInstance,
    StepApproval, WorkflowHistory,
    WorkflowStepTypeEnum, WorkflowTargetTypeEnum
)
from app.plugins.workflow.schemas import (
    WorkflowCreate, WorkflowStepCreate, 
    WorkflowStateCreate, WorkflowTransitionCreate,
    WorkflowInstanceCreate, StepApprovalCreate
)
from app.plugins.workflow.utils.workflow_manager import WorkflowManager


# Sample test user data
TEST_USER = {"id": 1, "username": "test_user", "email": "test@example.com"}

# Sample workflow data
TEST_WORKFLOW_DATA = {
    "name": "Document Approval",
    "description": "Standard approval process for documents",
    "target_type": WorkflowTargetTypeEnum.DOCUMENT,
    "is_default": True,
    "is_active": True
}


# ---- Fixtures ----

@pytest.fixture
def app():
    """Create a test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    
    # Override authentication dependency
    async def mock_get_current_user():
        return TEST_USER
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def mock_db(app, db_session):
    """Override the database dependency."""
    app.dependency_overrides[get_db] = lambda: db_session
    return db_session


@pytest.fixture
def sample_workflow():
    """Create a sample workflow object."""
    return Workflow(
        id=1,
        name=TEST_WORKFLOW_DATA["name"],
        description=TEST_WORKFLOW_DATA["description"],
        target_type=TEST_WORKFLOW_DATA["target_type"],
        is_default=TEST_WORKFLOW_DATA["is_default"],
        is_active=TEST_WORKFLOW_DATA["is_active"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        created_by=TEST_USER["id"],
        updated_by=TEST_USER["id"]
    )


@pytest.fixture
def sample_workflow_states(sample_workflow):
    """Create sample workflow states."""
    states = [
        WorkflowState(
            id=1,
            workflow_id=sample_workflow.id,
            name="Draft",
            is_initial=True,
            is_final=False,
            color="#808080"
        ),
        WorkflowState(
            id=2,
            workflow_id=sample_workflow.id,
            name="Pending Review",
            is_initial=False,
            is_final=False,
            color="#FFA500"
        ),
        WorkflowState(
            id=3,
            workflow_id=sample_workflow.id,
            name="Approved",
            is_initial=False,
            is_final=True,
            color="#008000"
        ),
        WorkflowState(
            id=4,
            workflow_id=sample_workflow.id,
            name="Rejected",
            is_initial=False,
            is_final=True,
            color="#FF0000"
        )
    ]
    return states


@pytest.fixture
def sample_workflow_steps(sample_workflow):
    """Create sample workflow steps."""
    steps = [
        WorkflowStep(
            id=1,
            workflow_id=sample_workflow.id,
            name="Review Document",
            step_type=WorkflowStepTypeEnum.APPROVAL,
            step_order=1,
            is_required=True,
            next_step_on_approve=2,
            next_step_on_reject=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),
        WorkflowStep(
            id=2,
            workflow_id=sample_workflow.id,
            name="Final Approval",
            step_type=WorkflowStepTypeEnum.APPROVAL,
            step_order=2,
            is_required=True,
            next_step_on_approve=None,
            next_step_on_reject=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    ]
    return steps


@pytest.fixture
def sample_workflow_transitions(sample_workflow, sample_workflow_states):
    """Create sample workflow transitions."""
    transitions = [
        WorkflowTransition(
            id=1,
            workflow_id=sample_workflow.id,
            from_state_id=sample_workflow_states[0].id,  # Draft
            to_state_id=sample_workflow_states[1].id,    # Pending Review
            name="Submit for Review",
            triggers=[{"type": "manual"}]
        ),
        WorkflowTransition(
            id=2,
            workflow_id=sample_workflow.id,
            from_state_id=sample_workflow_states[1].id,  # Pending Review
            to_state_id=sample_workflow_states[2].id,    # Approved
            name="Approve",
            triggers=[{"type": "approval_complete", "step_order": 2}]
        ),
        WorkflowTransition(
            id=3,
            workflow_id=sample_workflow.id,
            from_state_id=sample_workflow_states[1].id,  # Pending Review
            to_state_id=sample_workflow_states[3].id,    # Rejected
            name="Reject",
            triggers=[{"type": "rejection", "step_order": 2}]
        )
    ]
    return transitions


@pytest.fixture
def sample_workflow_instance(sample_workflow, sample_workflow_states):
    """Create a sample workflow instance."""
    return WorkflowInstance(
        id=1,
        workflow_id=sample_workflow.id,
        target_type=sample_workflow.target_type,
        target_id=123,  # Example document ID
        current_state_id=sample_workflow_states[0].id,  # Draft
        started_at=datetime.utcnow(),
        is_active=True
    )


@pytest.fixture
def sample_approvals(sample_workflow_instance, sample_workflow_steps):
    """Create sample approval records."""
    return [
        StepApproval(
            id=1,
            instance_id=sample_workflow_instance.id,
            step_id=sample_workflow_steps[0].id,
            status="pending",
            created_at=datetime.utcnow()
        )
    ]


# ---- Unit Tests ----

class TestWorkflows:
    """Tests for workflow CRUD operations."""
    
    def test_create_workflow(self, client, mock_db, sample_workflow):
        """Test creating a new workflow."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        response = client.post("/workflow/workflows", json={
            "name": TEST_WORKFLOW_DATA["name"],
            "description": TEST_WORKFLOW_DATA["description"],
            "target_type": TEST_WORKFLOW_DATA["target_type"],
            "is_default": TEST_WORKFLOW_DATA["is_default"]
        })
        
        assert response.status_code == 200
        assert response.json()["name"] == TEST_WORKFLOW_DATA["name"]
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_get_workflows(self, client, mock_db, sample_workflow):
        """Test getting all workflows."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset \
            .return_value.limit.return_value.all.return_value = [sample_workflow]
        mock_db.query.return_value.count.return_value = 1
        
        response = client.get("/workflow/workflows")
        
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["name"] == TEST_WORKFLOW_DATA["name"]
    
    def test_get_workflow(self, client, mock_db, sample_workflow):
        """Test getting a specific workflow."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_workflow
        
        response = client.get("/workflow/workflows/1")
        
        assert response.status_code == 200
        assert response.json()["id"] == sample_workflow.id
        assert response.json()["name"] == sample_workflow.name
    
    def test_update_workflow(self, client, mock_db, sample_workflow):
        """Test updating a workflow."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_workflow
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        response = client.put("/workflow/workflows/1", json={
            "name": "Updated Workflow Name"
        })
        
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Workflow Name"
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_delete_workflow(self, client, mock_db, sample_workflow):
        """Test deleting a workflow."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_workflow
        mock_db.delete.return_value = None
        mock_db.commit.return_value = None
        
        response = client.delete("/workflow/workflows/1")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Workflow deleted successfully"
        assert mock_db.delete.called
        assert mock_db.commit.called


class TestWorkflowSteps:
    """Tests for workflow step operations."""
    
    def test_create_workflow_step(self, client, mock_db, sample_workflow):
        """Test creating a new workflow step."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_workflow
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.flush.return_value = None
        
        step = WorkflowStep(
            id=1,
            workflow_id=sample_workflow.id,
            name="Test Step",
            step_type=WorkflowStepTypeEnum.APPROVAL,
            step_order=1,
            is_required=True
        )
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        response = client.post(f"/workflow/workflows/{sample_workflow.id}/steps", json={
            "name": "Test Step",
            "step_type": WorkflowStepTypeEnum.APPROVAL,
            "step_order": 1,
            "workflow_id": sample_workflow.id
        })
        
        assert response.status_code == 200
        assert response.json()["name"] == "Test Step"
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_get_workflow_steps(self, client, mock_db, sample_workflow, sample_workflow_steps):
        """Test getting all steps for a workflow."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_workflow
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_workflow_steps
        
        response = client.get(f"/workflow/workflows/{sample_workflow.id}/steps")
        
        assert response.status_code == 200
        assert len(response.json()) == len(sample_workflow_steps)
        assert response.json()[0]["name"] == sample_workflow_steps[0].name


class TestWorkflowStates:
    """Tests for workflow state operations."""
    
    def test_create_workflow_state(self, client, mock_db, sample_workflow):
        """Test creating a new workflow state."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_workflow
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        
        state = WorkflowState(
            id=1,
            workflow_id=sample_workflow.id,
            name="Test State",
            is_initial=True,
            is_final=False
        )
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        response = client.post(f"/workflow/workflows/{sample_workflow.id}/states", json={
            "name": "Test State",
            "is_initial": True,
            "workflow_id": sample_workflow.id
        })
        
        assert response.status_code == 200
        assert response.json()["name"] == "Test State"
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_get_workflow_states(self, client, mock_db, sample_workflow, sample_workflow_states):
        """Test getting all states for a workflow."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_workflow
        mock_db.query.return_value.filter.return_value.all.return_value = sample_workflow_states
        
        response = client.get(f"/workflow/workflows/{sample_workflow.id}/states")
        
        assert response.status_code == 200
        assert len(response.json()) == len(sample_workflow_states)
        assert response.json()[0]["name"] == sample_workflow_states[0].name


class TestWorkflowTransitions:
    """Tests for workflow transition operations."""
    
    def test_create_workflow_transition(self, client, mock_db, sample_workflow, sample_workflow_states):
        """Test creating a new workflow transition."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_workflow,  # First query: workflow
            sample_workflow_states[0],  # Second query: from_state
            sample_workflow_states[1],  # Third query: to_state
            None  # Fourth query: existing transition
        ]
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        
        transition = WorkflowTransition(
            id=1,
            workflow_id=sample_workflow.id,
            from_state_id=sample_workflow_states[0].id,
            to_state_id=sample_workflow_states[1].id,
            name="Test Transition"
        )
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        response = client.post(f"/workflow/workflows/{sample_workflow.id}/transitions", json={
            "from_state_id": sample_workflow_states[0].id,
            "to_state_id": sample_workflow_states[1].id,
            "name": "Test Transition",
            "workflow_id": sample_workflow.id
        })
        
        assert response.status_code == 200
        assert response.json()["name"] == "Test Transition"
        assert mock_db.add.called
        assert mock_db.commit.called


class TestWorkflowInstances:
    """Tests for workflow instance operations."""
    
    def test_create_workflow_instance(self, client, mock_db, sample_workflow, sample_workflow_states):
        """Test creating a new workflow instance."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_workflow,  # First query: workflow
            sample_workflow_states[0]  # Second query: initial state
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.flush.return_value = None
        
        instance = WorkflowInstance(
            id=1,
            workflow_id=sample_workflow.id,
            target_type=sample_workflow.target_type,
            target_id=123,
            current_state_id=sample_workflow_states[0].id,
            is_active=True
        )
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        response = client.post("/workflow/instances", json={
            "workflow_id": sample_workflow.id,
            "target_type": sample_workflow.target_type,
            "target_id": 123
        })
        
        assert response.status_code == 200
        assert response.json()["workflow_id"] == sample_workflow.id
        assert response.json()["target_id"] == 123
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_get_workflow_instances(self, client, mock_db, sample_workflow_instance):
        """Test getting workflow instances."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset \
            .return_value.limit.return_value.all.return_value = [sample_workflow_instance]
        mock_db.query.return_value.count.return_value = 1
        
        response = client.get("/workflow/instances")
        
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["id"] == sample_workflow_instance.id


class TestApprovals:
    """Tests for workflow approval operations."""
    
    def test_get_instance_approvals(self, client, mock_db, sample_workflow_instance, sample_approvals):
        """Test getting approvals for an instance."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_workflow_instance
        mock_db.query.return_value.filter.return_value.all.return_value = sample_approvals
        
        response = client.get(f"/workflow/instances/{sample_workflow_instance.id}/approvals")
        
        assert response.status_code == 200
        assert len(response.json()) == len(sample_approvals)
        assert response.json()[0]["id"] == sample_approvals[0].id


class TestWorkflowManager:
    """Tests for the WorkflowManager utility class."""
    
    def test_get_workflow_for_target(self, db_session, sample_workflow):
        """Test getting a workflow for a target entity."""
        db_session.query.return_value.filter.return_value.first.return_value = sample_workflow
        
        result = WorkflowManager.get_workflow_for_target(
            db_session,
            target_type=sample_workflow.target_type,
            target_id=123
        )
        
        assert result == sample_workflow
    
    def test_start_workflow(self, db_session, sample_workflow, sample_workflow_states, sample_workflow_steps):
        """Test starting a workflow instance."""
        db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_workflow,
            sample_workflow_states[0],
            *sample_workflow_steps
        ]
        db_session.add.return_value = None
        db_session.commit.return_value = None
        db_session.flush.return_value = None
        
        # Create a mock instance to be returned
        instance = WorkflowInstance(
            id=1,
            workflow_id=sample_workflow.id,
            target_type=sample_workflow.target_type,
            target_id=123,
            current_state_id=sample_workflow_states[0].id,
            is_active=True
        )
        db_session.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        result = WorkflowManager.start_workflow(
            db_session,
            workflow_id=sample_workflow.id,
            target_type=sample_workflow.target_type,
            target_id=123,
            user_id=TEST_USER["id"]
        )
        
        # Since we mock the database calls, we can't directly compare the result
        # We just verify that we got an instance back and the DB operations were called
        assert result is not None
        assert db_session.add.called
        assert db_session.commit.called


# ---- Integration Tests ----
# Note: These tests would require an actual database connection
# They are marked with 'integration' so they can be skipped with pytest -k "not integration"

@pytest.mark.integration
class TestWorkflowIntegration:
    """Integration tests for the workflow plugin."""
    
    # These tests would be implemented in a real application
    # to test end-to-end workflows with a real database
    
    def test_complete_workflow_cycle(self):
        """Test a complete workflow cycle from creation to completion."""
        # This would create a real workflow, add states, steps, transitions,
        # start an instance, and walk through the approvals
        pass
