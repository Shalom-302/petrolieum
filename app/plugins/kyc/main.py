"""
Main module for KYC (Know Your Customer) plugin.

This plugin provides functionality for user identity verification,
with special support for regions with low infrastructure through
simplified KYC processes.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, APIRouter, Depends

from app.core.db import get_db
from sqlalchemy.orm import Session

from .routes import (
    get_verification_router,
    get_profile_router,
    get_region_router,
    get_simplified_kyc_router,
    get_dashboard_router
)

# Export security utilities
from .utils.security import initialize_kyc_security, kyc_security

logger = logging.getLogger(__name__)


def get_admin_router() -> APIRouter:
    """
    Create and configure the KYC admin router.
    
    Returns:
        APIRouter: The configured admin router
    """
    router = APIRouter()
    
    # Add admin routes
    router.include_router(
        get_dashboard_router(),
        prefix="/dashboard"
    )
    
    @router.get("/", response_model=Dict[str, Any])
    async def plugin_info():
        """Get KYC plugin information."""
        return {
            "name": "KYC Plugin",
            "version": "1.0.0",
            "description": "Know Your Customer verification and identity management",
            "author": "Kaapi Team",
            "features": [
                "Identity verification",
                "Profile management",
                "Regional adaptability for different infrastructure levels",
                "Simplified KYC for low-infrastructure regions",
                "Admin dashboard with verification metrics"
            ]
        }
        
    def init_app(app):
        """Initialize the KYC admin plugin."""
        # Initialize security utilities
        initialize_kyc_security()
        app.include_router(router)
        return {
            "name": "kyc_admin",
            "description": "KYC Admin Dashboard",
            "version": "1.0.0"
        }
    
    return router


def get_api_router() -> APIRouter:
    """
    Create and configure the KYC API router.
    
    Returns:
        APIRouter: The configured API router
    """
    router = APIRouter()
    
    # Add user routes
    router.include_router(
        get_verification_router(),
        prefix="/verifications"
    )
    
    router.include_router(
        get_profile_router(),
        prefix="/profiles"
    )
    
    router.include_router(
        get_region_router(),
        prefix="/regions"
    )
    
    router.include_router(
        get_simplified_kyc_router(),
        prefix="/simplified"
    )
    
    @router.get("/", response_model=Dict[str, Any])
    async def api_info():
        """Get KYC API information."""
        return {
            "name": "KYC API",
            "version": "1.0.0",
            "description": "KYC verification and profile management API",
        }
        
    return router


# Initialize and export routers
kyc_admin_router = get_admin_router()
kyc_api_router = get_api_router()
