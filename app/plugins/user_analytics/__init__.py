"""
User Analytics plugin for tracking user journeys and generating heatmaps.
This plugin builds on the advanced_audit plugin to provide visual analytics.
"""

from .main import user_analytics_router

__all__ = ["user_analytics_router"]