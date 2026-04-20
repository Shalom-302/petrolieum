"""
Business alerts plugin main module.

This module serves as the entry point for the business alerts plugin,
providing initialization and configuration functionality.
"""

import logging
from fastapi import FastAPI, APIRouter

from app.core.rate_limit import configure_rate_limiting
from app.plugins.business_alerts.routes.alert_management import get_alert_management_router
from app.plugins.business_alerts.routes.notification import get_notification_router
from app.plugins.business_alerts.utils.security import initialize_alert_security

logger = logging.getLogger(__name__)


def get_router():
    """
    Get the Business Alerts router.
    
    Returns:
        APIRouter: Configured router for the business alerts plugin
    """
    router = APIRouter()
    
    # Add sub-routers
    alert_management_router = get_alert_management_router()
    notification_router = get_notification_router()
    
    router.include_router(
        alert_management_router,
        prefix="/alerts"
    )
    
    router.include_router(
        notification_router,
        prefix="/notifications"
    )
    
    return router


def init_app(app: FastAPI):
    """
    Initialize the business alerts plugin with the FastAPI application.
    
    Args:
        app: FastAPI application
    
    Returns:
        dict: Plugin metadata
    """
    # Initialize security components
    initialize_alert_security()
    
    # Include the router in the main app
    app.include_router(get_router(), prefix="/business-alerts")
    
    logger.info("Business alerts plugin initialized")
    
    return {
        "name": "business_alerts",
        "description": "Business Alerts and Notifications",
        "version": "1.0.0"
    }


def register_scheduled_tasks(scheduler):
    """
    Register scheduled tasks with the application scheduler.
    
    Args:
        scheduler: Application scheduler
    """
    from app.plugins.business_alerts.tasks.scheduled import (
        run_daily_alert_checks,
        run_hourly_alert_checks,
        run_weekly_alert_cleanup
    )
    
    # Register daily tasks
    scheduler.add_job(
        func=run_daily_alert_checks,
        trigger="cron",
        hour=1,  # Run at 1 AM
        minute=0,
        id="business_alerts_daily_checks"
    )
    
    # Register hourly tasks
    scheduler.add_job(
        func=run_hourly_alert_checks,
        trigger="interval",
        hours=1,
        id="business_alerts_hourly_checks"
    )
    
    # Register weekly tasks
    scheduler.add_job(
        func=run_weekly_alert_cleanup,
        trigger="cron",
        day_of_week="sun",  # Run on Sundays
        hour=2,  # Run at 2 AM
        minute=0,
        id="business_alerts_weekly_cleanup"
    )
    
    logger.info("Business alerts scheduled tasks registered")


# Create router instance
router = get_router()

# Export the router
business_alerts_router = router