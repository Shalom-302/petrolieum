"""
Workflow plugin for Kaapi.

This plugin provides a configurable workflow and approval system with state transitions.
"""
from app.plugins.workflow.main import workflow_router

__all__ = ["workflow_router"]
