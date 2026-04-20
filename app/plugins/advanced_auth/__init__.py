"""
Advanced Authentication plugin for Kaapi.

This plugin provides a comprehensive authentication system with support for multiple providers,
secure session management, and advanced security features.
"""
from .main import auth_router

__all__ = ["auth_router"]
