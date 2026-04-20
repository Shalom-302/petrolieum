"""
Main module for the AI/ML integration plugin.

This module initializes the FastAPI router and includes all sub-routers
for the AI integration plugin's API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_user

# Import sub-routers
from app.plugins.ai_integration.routes.providers import router as providers_router
from app.plugins.ai_integration.routes.models import router as models_router
from app.plugins.ai_integration.routes.text_analysis import router as text_analysis_router
from app.plugins.ai_integration.routes.content_generation import router as content_generation_router
from app.plugins.ai_integration.routes.recommendations import router as recommendations_router
from app.plugins.ai_integration.routes.usage import router as usage_router


def get_router() -> APIRouter:
    # Create main router for the plugin
    router = APIRouter()

    # Include all sub-routers
    router.include_router(providers_router)
    router.include_router(models_router)
    router.include_router(text_analysis_router)
    router.include_router(content_generation_router)
    router.include_router(recommendations_router)
    router.include_router(usage_router)

    # Health check endpoint
    @router.get("/health", summary="Check plugin health")
    async def health_check():
        """Check if the AI integration plugin is functioning properly."""
        return {
            "status": "ok",
            "name": "AI/ML Integration Plugin",
            "version": "1.0.0"
        }

    return router

ai_integration_router = get_router()