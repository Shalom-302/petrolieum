"""
Advanced Authentication Plugin

Ce plugin gère l'authentification et l'autorisation avancées pour l'application.
Il fournit des fonctionnalités telles que l'authentification à plusieurs facteurs,
l'authentification OAuth, la gestion des sessions, etc.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings
from .routes import router as authentication_router


def get_router() -> APIRouter:
    """
    Return the main router for the advanced authentication plugin.
    """
    router = APIRouter()
    
    # Include sub-routers
    router.include_router(authentication_router)

    return router

auth_router = get_router()
