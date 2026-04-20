"""
Workflow plugin for Kaapi.

This plugin provides a configurable workflow and approval system with state transitions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any

from app.core.security import get_current_user
from app.core.db import get_db
from app.plugins.workflow.routes.workflows import router as workflows_router
from app.plugins.workflow.routes.steps import router as steps_router
from app.plugins.workflow.routes.states import router as states_router
from app.plugins.workflow.routes.transitions import router as transitions_router
from app.plugins.workflow.routes.instances import router as instances_router
from app.plugins.workflow.routes.approvals import router as approvals_router

# Export workflow engine and classes
from .engine import (
    workflow_engine,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowContext,
    WorkflowEngine
)

def get_router() -> APIRouter:

    router = APIRouter()
    # Include all sub-routers
    router.include_router(workflows_router)
    router.include_router(steps_router)
    router.include_router(states_router)
    router.include_router(transitions_router)
    router.include_router(instances_router)
    router.include_router(approvals_router)


    @router.get("/", response_model=Dict[str, Any])
    async def plugin_info():
        """Get workflow plugin information."""
        return {
            "name": "Workflow & Approval System",
            "description": "Configurable workflow system with approval steps and state transitions",
            "version": "1.0.0",
            "features": [
                "Configurable workflow processes",
                "Multi-step approval workflows",
                "Role-based approval permissions",
                "State transitions with triggers",
                "Workflow history tracking"
            ]
        }


    def init_app(app):
        """Initialize the workflow plugin."""
        app.include_router(router)
        return {
            "name": "workflow",
            "description": "Workflow & Approval System",
            "version": "1.0.0"
        }

    return router

workflow_router = get_router()