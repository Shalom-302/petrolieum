
"""
API Versioning Plugin for Kaapi

This plugin adds API versioning capabilities to your Kaapi application:
- API version management
- API endpoint versioning
- API version history
"""

from .main import api_versioning_router
from .integration import register_with_main_app

__all__ = ["api_versioning_router", "register_with_main_app"]
