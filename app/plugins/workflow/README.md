# Workflow & Approval Plugin

A powerful and flexible workflow system for Kaapi that enables configurable approval processes with state transitions.

## Features

- **Configurable Workflows**: Create and customize workflows for different entity types
- **Multi-step Approvals**: Define sequential or parallel approval steps
- **Role-based Permissions**: Assign specific roles as approvers for each step
- **State Transitions**: Define states and transitions with custom triggers
- **Branching Logic**: Support for conditional paths based on approval decisions
- **History Tracking**: Complete audit trail of all workflow actions
- **API Integration**: Comprehensive REST API for all workflow operations

## Installation

1. Add the workflow plugin to your Kaapi application by including it in your `plugins.json` file:

```json
{
  "plugins": [
    "workflow"
  ]
}
```

2. Install the required dependencies:

```bash
pip install -r app/plugins/workflow/requirements.txt
```

3. Ensure database migrations are applied:

```bash
alembic upgrade head
```

## Core Concepts

### Workflows

A workflow is a template that defines the approval process for a specific entity type (content, user, document, etc.). Each workflow consists of:

- **Steps**: Actions that need to be performed (approvals, notifications, automations)
- **States**: Possible statuses an entity can have during the workflow
- **Transitions**: Rules for moving between states

### Workflow Instances

When a workflow is applied to a specific entity (e.g., a document), a workflow instance is created. This instance:

- Tracks the current state of the entity
- Manages active approval steps
- Records approval decisions
- Maintains a complete history of the workflow

## Configuration

### Creating a Basic Approval Workflow

This example shows how to create a simple two-step approval workflow:

```python
from app.plugins.workflow.utils.workflow_manager import WorkflowManager
from app.plugins.workflow.models import WorkflowTargetTypeEnum, WorkflowStepTypeEnum

# Create workflow
workflow = {
    "name": "Document Approval",
    "description": "Standard approval process for documents",
    "target_type": WorkflowTargetTypeEnum.DOCUMENT,
    "is_default": True
}

# Create workflow instance
workflow_id = create_workflow(db, workflow, user_id)

# Add states
draft_state = add_state(db, workflow_id, "Draft", is_initial=True)
pending_state = add_state(db, workflow_id, "Pending Approval")
approved_state = add_state(db, workflow_id, "Approved", is_final=True)
rejected_state = add_state(db, workflow_id, "Rejected", is_final=True)

# Add transitions
add_transition(db, workflow_id, draft_state, pending_state, "Submit for Review")
add_transition(db, workflow_id, pending_state, approved_state, "Approve")
add_transition(db, workflow_id, pending_state, rejected_state, "Reject")

# Add steps
reviewer_role_id = 2  # Example role ID for reviewers
approver_role_id = 3  # Example role ID for approvers

add_step(db, workflow_id, {
    "name": "Review Document",
    "step_type": WorkflowStepTypeEnum.APPROVAL,
    "step_order": 1,
    "role_ids": [reviewer_role_id]
})

add_step(db, workflow_id, {
    "name": "Final Approval",
    "step_type": WorkflowStepTypeEnum.APPROVAL,
    "step_order": 2,
    "role_ids": [approver_role_id]
})
```

### Starting a Workflow

```python
from app.plugins.workflow.utils.workflow_manager import WorkflowManager

# Find appropriate workflow for a document
workflow = WorkflowManager.get_workflow_for_target(
    db, 
    target_type=WorkflowTargetTypeEnum.DOCUMENT,
    target_id=document_id
)

# Start the workflow
if workflow:
    instance = WorkflowManager.start_workflow(
        db,
        workflow_id=workflow.id,
        target_type=WorkflowTargetTypeEnum.DOCUMENT,
        target_id=document_id,
        user_id=current_user_id,
        metadata={"title": document.title}
    )
```

## API Endpoints

### Workflow Management

- `POST /workflow/workflows`: Create a new workflow
- `GET /workflow/workflows`: List all workflows
- `GET /workflow/workflows/{workflow_id}`: Get workflow details
- `PUT /workflow/workflows/{workflow_id}`: Update a workflow
- `DELETE /workflow/workflows/{workflow_id}`: Delete a workflow

### Step Management

- `POST /workflow/workflows/{workflow_id}/steps`: Add a step to a workflow
- `GET /workflow/workflows/{workflow_id}/steps`: Get all steps for a workflow
- `GET /workflow/steps/{step_id}`: Get step details
- `PUT /workflow/steps/{step_id}`: Update a step
- `DELETE /workflow/steps/{step_id}`: Delete a step

### State Management

- `POST /workflow/workflows/{workflow_id}/states`: Add a state to a workflow
- `GET /workflow/workflows/{workflow_id}/states`: Get all states for a workflow
- `GET /workflow/states/{state_id}`: Get state details
- `PUT /workflow/states/{state_id}`: Update a state
- `DELETE /workflow/states/{state_id}`: Delete a state

### Transition Management

- `POST /workflow/workflows/{workflow_id}/transitions`: Create a transition
- `GET /workflow/workflows/{workflow_id}/transitions`: List transitions
- `GET /workflow/transitions/{transition_id}`: Get transition details
- `PUT /workflow/transitions/{transition_id}`: Update a transition
- `DELETE /workflow/transitions/{transition_id}`: Delete a transition

### Workflow Instances

- `POST /workflow/instances`: Start a new workflow instance
- `GET /workflow/instances`: List workflow instances
- `GET /workflow/instances/{instance_id}`: Get instance details
- `PUT /workflow/instances/{instance_id}/transition/{state_id}`: Transition to new state
- `GET /workflow/instances/{instance_id}/history`: Get instance history
- `DELETE /workflow/instances/{instance_id}`: Cancel a workflow instance

### Approvals

- `GET /workflow/instances/{instance_id}/approvals`: Get approvals for an instance
- `GET /workflow/users/me/pending-approvals`: Get current user's pending approvals
- `POST /workflow/approvals/{approval_id}/approve`: Approve a step
- `POST /workflow/approvals/{approval_id}/reject`: Reject a step

## Frontend Integration

The workflow plugin provides a complete REST API that can be integrated with your frontend application. Here's a simple example using fetch:

```javascript
// Get user's pending approvals
async function getPendingApprovals() {
  const response = await fetch('/workflow/users/me/pending-approvals', {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  });
  return await response.json();
}

// Approve a workflow step
async function approveStep(approvalId, comments) {
  const response = await fetch(`/workflow/approvals/${approvalId}/approve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    },
    body: JSON.stringify({
      comments: comments
    })
  });
  return await response.json();
}
```

## Advanced Usage

### Custom Workflow Triggers

The workflow system supports custom triggers for state transitions:

```python
# Create a transition with a time-based trigger
transition = {
    "from_state_id": pending_state_id,
    "to_state_id": expired_state_id,
    "name": "Expiration",
    "triggers": [
        {
            "type": "time",
            "config": {
                "days": 7,  # Transition after 7 days
                "action": "timeout"
            }
        }
    ]
}
```

### Branching Workflows

Create conditional paths based on approval decisions:

```python
# Add steps with branching logic
review_step = add_step(db, workflow_id, {
    "name": "Initial Review",
    "step_type": WorkflowStepTypeEnum.APPROVAL,
    "step_order": 1,
    "role_ids": [reviewer_role_id]
})

revision_step = add_step(db, workflow_id, {
    "name": "Revision Required",
    "step_type": WorkflowStepTypeEnum.NOTIFICATION,
    "step_order": 2
})

approval_step = add_step(db, workflow_id, {
    "name": "Final Approval",
    "step_type": WorkflowStepTypeEnum.APPROVAL,
    "step_order": 2,
    "role_ids": [approver_role_id]
})

# Set branching logic
update_step(db, review_step.id, {
    "next_step_on_approve": approval_step.id,
    "next_step_on_reject": revision_step.id
})
```

## AI/ML Integration

The workflow plugin can be enhanced with AI/ML capabilities for more intelligent processes:

- **Integration with AI services**:
  - Connect to OpenAI, Azure AI, or other AI service providers
  - Leverage large language models for content analysis and decision support
  - Implement AI-assisted document processing

- **Text Analysis and Sentiment**:
  - Automatic content classification for routing to appropriate workflows
  - Sentiment analysis for prioritizing urgent approvals
  - Detect potential compliance issues in submitted content

- **Recommendations and Personalization**:
  - AI-powered suggestions for workflow improvements
  - Smart assignment of approvers based on expertise and workload
  - Personalized dashboards showing most relevant pending approvals
  - Predictive analytics for workflow bottlenecks and optimization

## License

This plugin is licensed under the same license as the Kaapi project.
