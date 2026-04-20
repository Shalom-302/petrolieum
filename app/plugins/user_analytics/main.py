"""
Main entry point for the user analytics plugin.
Handles plugin initialization and router configuration.
"""
import logging
from fastapi import FastAPI, APIRouter
from typing import Dict, Any

from .routes import sessions_router, events_router, analytics_router

logger = logging.getLogger(__name__)

def get_router() -> APIRouter:
    """
    Creates and configures the main router for the user analytics plugin.
    
    Returns:
        APIRouter: Configured FastAPI router
    """
    router = APIRouter()
    
    # Include sub-routers
    router.include_router(
        sessions_router,
        prefix="/sessions"
    )
    
    router.include_router(
        events_router,
        prefix="/events"
    )
    
    router.include_router(
        analytics_router,
        prefix="/analytics"
    )
    
    return router

# Create router instance for legacy support
user_analytics_router = get_router()
