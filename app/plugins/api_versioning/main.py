"""
Main module for API versioning plugin.

This plugin enables API versioning in Kaapi, allowing multiple versions of the API
to be supported simultaneously.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user, get_current_active_admin_user
from app.plugins.api_versioning.routes import versions, endpoints, changes, docs


def get_router() -> APIRouter:
    """
    Return the main router for the API versioning plugin.
    """
    router = APIRouter()

    # Include the sub-routers without adding additional tags
    # (they already have their own tags)
    router.include_router(versions.router)
    router.include_router(endpoints.router)
    router.include_router(changes.router)
    router.include_router(docs.router)

    # Root endpoint for API versioning
    @router.get("/")
    async def get_api_versioning_status(
        db: Session = Depends(get_db),
        current_user = Depends(get_current_active_admin_user)
    ):
        """
        Get the status of API versioning functionality.
        Only accessible by admin users.
        """
        from app.plugins.api_versioning.utils.version_manager import get_active_versions
        
        active_versions = get_active_versions(db)
        
        return {
            "status": "active",
            "active_versions": len(active_versions),
            "versions": [v.version for v in active_versions]
        }

    return router

api_versioning_router = get_router()
