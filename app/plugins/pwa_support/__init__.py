"""
PWA Support Plugin for Kaapi

This plugin adds Progressive Web App capabilities to your Kaapi application:
- Web App Manifest management
- Service Worker for offline support
- Push Notifications
"""

from .main import pwa_support_router

__all__ = ["pwa_support_router"]
