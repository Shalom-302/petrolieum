"""
Matomo integration plugin for Kaapi.
Provides analytics capabilities using Matomo as the backend.
"""

from .main import matomo_router

__all__ = [
    "matomo_router"
]

