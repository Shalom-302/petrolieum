"""
Main entry point for the Matomo integration plugin.
Handles plugin initialization and router configuration.
"""
import logging
from fastapi import FastAPI, APIRouter
from typing import Dict, Any

logger = logging.getLogger(__name__)

def get_router() -> APIRouter:
    """
    Creates and configures the main router for the Matomo integration plugin.
    
    Returns:
        APIRouter: Configured FastAPI router
    """
    from .routes import auth_router, config_router, embed_router
    
    router = APIRouter()
    
    # Include sub-routers
    router.include_router(
        auth_router,
        prefix="/auth"
    )
    
    router.include_router(
        config_router,
        prefix="/config"
    )
    
    router.include_router(
        embed_router,
        prefix="/embed"
    )
    
    return router

def init_app(app: FastAPI) -> Dict[str, Any]:
    """
    Initialize the Matomo integration plugin with the FastAPI application.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        dict: Plugin metadata
    """
    # Initialize plugin configuration
    from .services.config_service import initialize_default_config
    initialize_default_config()
    
    # Include the router in the main app
    app.include_router(get_router(), prefix="/matomo")
    
    logger.info("Matomo integration plugin initialized")
    
    return {
        "name": "matomo_integration",
        "description": "Integration with Matomo for analytics and user tracking",
        "version": "1.0.0"
    }


matomo_router = get_router()
