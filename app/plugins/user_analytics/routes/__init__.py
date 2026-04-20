"""
API routes for the user analytics plugin.
"""
from .sessions import router as sessions_router
from .events import router as events_router
from .analytics import router as analytics_router

__all__ = ["sessions_router", "events_router", "analytics_router"]
