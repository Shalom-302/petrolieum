"""
Business alerts routes.

This module contains API route definitions for the business alerts plugin.
"""

from .alert_management import get_alert_management_router
from .notification import get_notification_router

__all__ = ["get_alert_management_router", "get_notification_router"]
