"""
Push Notifications Plugin

A comprehensive push notification solution for KAAPI, featuring support for multiple
providers (FCM, APNs, Web Push), device management, template-based notifications,
robust security, and high-performance message delivery.
"""

from .main import push_notifications_router

__all__ = ["push_notifications_router"]
