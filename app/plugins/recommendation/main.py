"""
Recommendation Plugin - Main Module

This plugin provides a comprehensive recommendation system integrating multiple recommendation
approaches including collaborative filtering, matrix factorization, and content-based filtering.
"""
from fastapi import FastAPI, APIRouter
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

class RecommendationPlugin:
    """
    Main class for the recommendation plugin that manages initialization
    and configuration for the recommendation system.
    """
    router = APIRouter()
    
    def __init__(self):
        # Initialize plugin router with separate endpoint routers
        from .routes import recommend, feedback, admin
        self.router.include_router(recommend.router, prefix="/recommend")
        self.router.include_router(feedback.router, prefix="/feedback")
        self.router.include_router(admin.router, prefix="/admin")
        
        # Set default configuration
        self.encryption_handler = None
        self.algorithm_service = None
        self.feature_service = None
        self.similarity_service = None
        self.training_service = None
    
    def init_app(self, app: FastAPI, prefix: str = "/plugins/recommendation"):
        """
        Initialize the recommendation plugin with the FastAPI application
        
        Args:
            app: FastAPI application instance
            prefix: URL prefix for all recommendation endpoints
        """
        try:
            logger.info("Initializing recommendation plugin...")
            
            # Create database tables if they don't exist
            from app.core.db import engine
            from .models.interaction import InteractionDB
            from .models.item import ItemFeatureDB
            from .models.similarity import SimilarityMatrixDB
            from .models.recommendation import RecommendationDB
            
            # Les tables sont désormais gérées par les migrations Alembic
            logger.info("Les tables du module de recommandation sont gérées par les migrations Alembic")
            
            # Initialize security features
            from app.core.security import create_encryption_handler
            from app.core.rate_limit import configure_rate_limiting
            
            # Setup standardized security approach
            self.encryption_handler = create_encryption_handler()
            
            # Configure rate limiting for API endpoints
            configure_rate_limiting(
                self.router,
                [
                    {"path": "/recommend/items", "limit": "60/minute"},
                    {"path": "/recommend/similar", "limit": "120/minute"},
                    {"path": "/feedback/*", "limit": "300/minute"},
                    {"path": "/admin/*", "limit": "20/minute"},
                ]
            )
            
            # Initialize services with dependency injection
            from .services.algorithm_service import AlgorithmService
            from .services.feature_service import FeatureService
            from .services.similarity_service import SimilarityService
            from .services.training_service import TrainingService
            
            self.algorithm_service = AlgorithmService(encryption_handler=self.encryption_handler)
            self.feature_service = FeatureService(encryption_handler=self.encryption_handler)
            self.similarity_service = SimilarityService(encryption_handler=self.encryption_handler)
            self.training_service = TrainingService(encryption_handler=self.encryption_handler)
            
            # Register the plugin router with the main application
            app.include_router(self.router, prefix=prefix)
            
            # Setup scheduled tasks for model training and performance monitoring
            self._setup_scheduled_tasks(app)
            
            logger.info("Recommendation plugin successfully initialized")
            return self
            
        except Exception as e:
            logger.error(f"Error initializing recommendation plugin: {str(e)}")
            raise
    
    def _setup_scheduled_tasks(self, app: FastAPI):
        """
        Configure scheduled tasks for model training and performance monitoring
        
        Args:
            app: FastAPI application instance
        """
        try:
            from app.plugins.advanced_scheduler.client import scheduler
            from .tasks.model_refresh import refresh_models
            from .tasks.performance_monitor import monitor_recommendation_performance
            
            # Schedule collaborative filtering model refresh (daily at 3 AM)
            scheduler.add_job(
                refresh_models,
                "cron", 
                hour=3,
                id="refresh_recommendation_models",
                replace_existing=True
            )
            
            # Schedule performance monitoring (every 6 hours)
            scheduler.add_job(
                monitor_recommendation_performance,
                "interval", 
                hours=6,
                id="monitor_recommendation_performance",
                replace_existing=True
            )
            
            logger.info("Recommendation scheduled tasks configured")
            
        except Exception as e:
            logger.warning(f"Could not set up scheduled tasks: {str(e)}")


# Create a singleton instance of the recommendation plugin
recommendation_plugin = RecommendationPlugin()


def get_plugin():
    """Return the plugin instance for integration with the main application"""
    return recommendation_plugin

recommendation_router = recommendation_plugin.router