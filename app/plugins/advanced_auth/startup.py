"""
Startup events and initialization for the advanced authentication plugin.
"""
import logging
from typing import Callable, Dict, Any, List
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from .db_init import init_database

logger = logging.getLogger(__name__)


def register_startup_events(app: FastAPI) -> None:
    """
    Register startup events for the authentication plugin.
    
    Args:
        app: FastAPI application
    """
    
    @app.on_event("startup")
    async def init_auth_database() -> None:
        """Initialize the authentication database on startup."""
        logger.info("Initializing authentication database...")
        
        # Create a new session for the startup event
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            init_database(db)
        finally:
            db.close()
        
        logger.info("Authentication database initialization complete")


def register_shutdown_events(app: FastAPI) -> None:
    """
    Register shutdown events for the authentication plugin.
    
    Args:
        app: FastAPI application
    """
    
    @app.on_event("shutdown")
    async def cleanup_auth_resources() -> None:
        """Clean up authentication resources on shutdown."""
        logger.info("Cleaning up authentication resources...")
