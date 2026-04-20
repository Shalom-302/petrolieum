"""
Scheduler Configuration

This module configures scheduled tasks for the recommendation plugin,
including model training, performance monitoring, and data cleanup.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from app.plugins.advanced_scheduler.scheduler import register_task, scheduler

from .model_refresh import refresh_models
from .performance_monitor import monitor_recommendation_performance
from ..main import recommendation_plugin

logger = logging.getLogger(__name__)


def initialize_scheduled_tasks(hour_for_model_refresh: int = 3):
    """
    Initialize all scheduled tasks for the recommendation plugin.
    
    Args:
        hour_for_model_refresh: Hour of day (0-23) to refresh models, typically
                               set to off-peak hours
    """
    logger.info(f"Initializing recommendation scheduled tasks")
    
    # Register daily model refresh task at specified hour
    register_task(
        "recommendation_model_refresh",
        scheduler.cron(f"0 {hour_for_model_refresh} * * *"),
        _scheduled_model_refresh,
        {"algorithm": "all", "force": False}
    )
    
    # Register hourly performance monitoring
    register_task(
        "recommendation_performance_monitor",
        scheduler.cron("0 * * * *"),  # Every hour
        _scheduled_performance_monitor,
        {}
    )
    
    # Register weekly data cleanup task (Sunday at 2 AM)
    register_task(
        "recommendation_data_cleanup",
        scheduler.cron("0 2 * * 0"),
        _scheduled_data_cleanup,
        {"days_to_keep": 180}  # Keep 6 months of data
    )
    
    logger.info("Recommendation scheduled tasks initialized")


async def _scheduled_model_refresh(algorithm: str = "all", force: bool = False):
    """
    Wrapper for scheduled model refresh task.
    
    Args:
        algorithm: Algorithm to refresh ("all", "collaborative", etc.)
        force: Whether to force retraining even if recent model exists
    """
    try:
        # Use standardized security approach for logging
        recommendation_plugin.security_handler.secure_log(
            "Starting scheduled model refresh",
            {"algorithm": algorithm, "force": force},
            "info"
        )
        
        # Set training flag to prevent concurrent training
        if recommendation_plugin._training_in_progress:
            logger.warning("Training already in progress, skipping scheduled refresh")
            return
            
        recommendation_plugin._training_in_progress = True
        
        # Refresh models
        await refresh_models(algorithm, force)
        
    except Exception as e:
        logger.error(f"Error in scheduled model refresh: {str(e)}")
        recommendation_plugin._training_in_progress = False


async def _scheduled_performance_monitor():
    """Wrapper for scheduled performance monitoring task."""
    try:
        # Use standardized security approach for logging
        recommendation_plugin.security_handler.secure_log(
            "Starting scheduled performance monitoring",
            {},
            "info"
        )
        
        # Monitor performance
        await monitor_recommendation_performance()
        
    except Exception as e:
        logger.error(f"Error in scheduled performance monitoring: {str(e)}")


async def _scheduled_data_cleanup(days_to_keep: int = 180):
    """
    Clean up old recommendation data to maintain database performance.
    
    Args:
        days_to_keep: Number of days of data to keep
    """
    from app.core.db import SessionLocal
    from ..models.recommendation import RecommendationDB
    from ..models.interaction import InteractionDB
    from sqlalchemy import func
    
    try:
        # Use standardized security approach for logging
        recommendation_plugin.security_handler.secure_log(
            "Starting scheduled data cleanup",
            {"days_to_keep": days_to_keep},
            "info"
        )
        
        db = SessionLocal()
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Delete old recommendations
            rec_count = db.query(func.count(RecommendationDB.id)).filter(
                RecommendationDB.created_at < cutoff_date
            ).scalar() or 0
            
            if rec_count > 0:
                db.query(RecommendationDB).filter(
                    RecommendationDB.created_at < cutoff_date
                ).delete(synchronize_session=False)
                
                logger.info(f"Deleted {rec_count} old recommendations")
            
            # Delete old interactions (except ratings which are valuable for training)
            int_count = db.query(func.count(InteractionDB.id)).filter(
                InteractionDB.created_at < cutoff_date,
                InteractionDB.interaction_type != 'rating'
            ).scalar() or 0
            
            if int_count > 0:
                db.query(InteractionDB).filter(
                    InteractionDB.created_at < cutoff_date,
                    InteractionDB.interaction_type != 'rating'
                ).delete(synchronize_session=False)
                
                logger.info(f"Deleted {int_count} old interactions")
                
            db.commit()
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in scheduled data cleanup: {str(e)}")
