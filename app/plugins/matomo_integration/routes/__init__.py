"""
API routes for the Matomo integration plugin.
"""
from .auth import router as auth_router
from .config import router as config_router
from .embed import router as embed_router

__all__ = ["auth_router", "config_router", "embed_router"]
