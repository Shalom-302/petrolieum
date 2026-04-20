"""
Push Notifications Plugin

A comprehensive push notification solution for KAAPI, featuring support for multiple
providers (FCM, APNs, Web Push), device management, template-based notifications,
robust security, and high-performance message delivery.

The plugin follows KAAPI's standardized security approach for all providers:
- Validation of notification requests
- Encryption of sensitive metadata
- Comprehensive transaction logging
- Standardized configuration and initialization
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from fastapi import APIRouter, Depends, FastAPI, BackgroundTasks, HTTPException

from app.core.config import settings
from app.core.security import oauth2_scheme, get_current_user, get_current_active_user

from .services.device_service import DeviceService
from .services.notification_service import NotificationService
from .services.template_service import TemplateService
from .services.analytics_service import AnalyticsService

from .handlers.security_handler import SecurityHandler
from .handlers.rabbitmq_handler import RabbitMQHandler
from .handlers.redis_handler import RedisHandler

from .models.database import Device, Notification, NotificationTemplate

logger = logging.getLogger(__name__)


class PushNotificationService:
    """
    Push Notification Service Plugin main class that handles initialization,
    configuration and provides core push notification functionalities.
    """
    
    def __init__(self):
        """Initialize the push notification service plugin."""
        self.router = None
        self.security_handler = None
        self.rabbitmq_handler = None
        self.redis_handler = None
        self._is_initialized = False
        
        # Default configuration values
        self.config = {
            "enabled": True,
            "default_ttl": 86400,  # 24 hours in seconds
            "default_priority": "normal",
            "default_badge": 1,
            "default_sound": "default",
            "max_devices_per_user": 10,
            "max_notification_size": 4096,  # bytes
            "batch_size": 1000,
            "retry_attempts": 3,
            "retry_delay": 60,  # seconds
            "providers": {
                "fcm": {
                    "enabled": True,
                    "batch_size": 500,
                    "priority_mapping": {
                        "high": "high",
                        "normal": "normal"
                    }
                },
                "apns": {
                    "enabled": True,
                    "batch_size": 500,
                    "priority_mapping": {
                        "high": 10,
                        "normal": 5
                    },
                    "production": True
                },
                "web_push": {
                    "enabled": True,
                    "batch_size": 100,
                    "ttl": 43200  # 12 hours in seconds
                }
            },
            "rate_limits": {
                "per_user": 10,      # Max 10 notifications per user per minute
                "per_app": 1000,     # Max 1000 notifications per minute for the entire app
                "per_template": 100  # Max 100 instances of the same template per minute
            },
            "analytics": {
                "enabled": True,
                "retention_days": 90
            }
        }

    def init_app(self, app: FastAPI, router: APIRouter, prefix: str = "/push-notifications"):
        """
        Initialize the plugin with the main application.
        
        Args:
            app: FastAPI application instance
            router: API router to use for routes
            prefix: API route prefix
        """
        if self._is_initialized:
            logger.warning("Push Notification Service already initialized")
            return
        
        logger.info("Initializing Push Notification Service")
        
        # Store router reference
        self.router = router
        
        # Merge settings from environment with defaults
        self._init_config_from_settings()
        
        # Initialize handlers
        self._init_security_handler()
        self._init_rabbitmq_handler()
        self._init_redis_handler()
        
        # Initialize services
        self._init_services()
        
        # Set up routes
        self._setup_routes()
        
        # Include router in main app if needed
        if app is not None:
            app.include_router(self.router, prefix=prefix, tags=["push-notifications"])
        
        self._is_initialized = True
        logger.info("Push Notification Service initialized")
    
    def _init_config_from_settings(self):
        """Initialize configuration from application settings."""
        if hasattr(settings, "PUSH_NOTIFICATION_ENABLED"):
            self.config["enabled"] = settings.PUSH_NOTIFICATION_ENABLED
        
        # FCM settings
        if hasattr(settings, "FCM_API_KEY"):
            self.config["providers"]["fcm"]["api_key"] = settings.FCM_API_KEY
        
        # APNs settings
        if hasattr(settings, "APNS_KEY_ID"):
            self.config["providers"]["apns"]["key_id"] = settings.APNS_KEY_ID
        if hasattr(settings, "APNS_TEAM_ID"):
            self.config["providers"]["apns"]["team_id"] = settings.APNS_TEAM_ID
        if hasattr(settings, "APNS_BUNDLE_ID"):
            self.config["providers"]["apns"]["bundle_id"] = settings.APNS_BUNDLE_ID
        if hasattr(settings, "APNS_KEY_FILE"):
            self.config["providers"]["apns"]["key_file"] = settings.APNS_KEY_FILE
        
        # Web Push settings
        if hasattr(settings, "VAPID_PRIVATE_KEY"):
            self.config["providers"]["web_push"]["vapid_private_key"] = settings.VAPID_PRIVATE_KEY
        if hasattr(settings, "VAPID_PUBLIC_KEY"):
            self.config["providers"]["web_push"]["vapid_public_key"] = settings.VAPID_PUBLIC_KEY
        if hasattr(settings, "VAPID_CLAIMS_EMAIL"):
            self.config["providers"]["web_push"]["vapid_claims_email"] = settings.VAPID_CLAIMS_EMAIL
            
    def _init_security_handler(self):
        """Initialize the security handler for push notification encryption and security."""
        self.security_handler = SecurityHandler()
        logger.info("Security handler initialized")
        
    def _init_rabbitmq_handler(self):
        """Initialize the RabbitMQ handler for async message processing."""
        rabbitmq_config = {
            "username": settings.RABBITMQ_USERNAME,
            "password": settings.RABBITMQ_PASSWORD,
            "host": settings.RABBITMQ_HOST,
            "port": settings.RABBITMQ_PORT,
            "exchange": "push_notifications",
            "queue_prefix": "push_notifications_"
        }
        self.rabbitmq_handler = RabbitMQHandler(rabbitmq_config)
        logger.info("RabbitMQ handler initialized")
        
    def _init_redis_handler(self):
        """Initialize the Redis handler for caching and rate limiting."""
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        self.redis_handler = RedisHandler(redis_url, prefix="push_notifications:")
        logger.info("Redis handler initialized")
        
    def _init_services(self):
        """Initialize all plugin services."""
        # Créer une session BD
        from app.core.db import SessionLocal
        db = SessionLocal()
        
        try:
            # Initialize services with their correct constructor signatures
            self.device_service = DeviceService(
                db=db,
                security_handler=self.security_handler,
                redis_handler=self.redis_handler
            )
            
            self.template_service = TemplateService(
                db=db,
                security_handler=self.security_handler,
                redis_handler=self.redis_handler
            )
            
            # Pass the existing device and template services to the notification service
            self.notification_service = NotificationService(
                db=db,
                security_handler=self.security_handler,
                redis_handler=self.redis_handler,
                rabbitmq_handler=self.rabbitmq_handler,
                device_service=self.device_service,
                template_service=self.template_service
            )
            
            self.analytics_service = AnalyticsService(
                db=db,
                security_handler=self.security_handler,
                redis_handler=self.redis_handler
            )
            
            logger.info("All services initialized")
        finally:
            db.close()
        
    def _setup_routes(self):
        """Set up all API routes for the push notification service."""
        if self.router is None:
            raise RuntimeError("Router not initialized")
            
        # Import routes module and copy all routes to the main router
        from .routes import router as all_routes
        
        # Copy all routes from the imported router to our main router
        self.router.routes.extend(all_routes.routes)
        
        # Add status route
        @self.router.get("/status")
        async def get_plugin_status():
            """
            Get the status of the Push Notifications plugin.
            
            Returns:
                dict: Status information
            """
            return {
                "status": "active",
                "version": "1.0.0",
                "timestamp": datetime.utcnow().isoformat()
            }
        
    def update_config(self, new_config: Dict[str, Any]):
        """
        Update plugin configuration.
        
        Args:
            new_config: Dictionary containing new configuration values
        """
        for key, value in new_config.items():
            if key in self.config:
                if isinstance(value, dict) and isinstance(self.config[key], dict):
                    self.config[key].update(value)
                else:
                    self.config[key] = value
        
        # Update services with new config
        if hasattr(self, 'device_service'):
            self.device_service.update_config(self.config)
        if hasattr(self, 'notification_service'):
            self.notification_service.update_config(self.config)
        if hasattr(self, 'template_service'):
            self.template_service.update_config(self.config)
        if hasattr(self, 'analytics_service'):
            self.analytics_service.update_config(self.config)
            
        logger.info("Configuration updated")
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get current plugin configuration.
        
        Returns:
            Dictionary containing current configuration values
        """
        # Return a copy to prevent modification of internal state
        return self.config.copy()
    
    # Public API methods
    
    def register_device(self, user_id: str, device_token: str, platform: str, 
                        app_version: str = None, device_data: Dict[str, Any] = None) -> str:
        """
        Register a device for push notifications.
        
        Args:
            user_id: ID of the user owning the device
            device_token: Push notification token/ID for the device
            platform: Device platform (android, ios, web)
            app_version: Version of the app installed on the device
            device_data: Additional device data
            
        Returns:
            Device ID
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.device_service.register_device(
            user_id=user_id,
            device_token=device_token,
            platform=platform,
            app_version=app_version,
            device_data=device_data
        )
    
    def unregister_device(self, device_id: str, user_id: str = None) -> bool:
        """
        Unregister a device from push notifications.
        
        Args:
            device_id: ID of the device to unregister
            user_id: ID of the user owning the device (for validation)
            
        Returns:
            Success status
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.device_service.unregister_device(
            device_id=device_id,
            user_id=user_id
        )
    
    def send_notification(self, user_ids: List[str], title: str, body: str, 
                         data: Dict[str, Any] = None, high_priority: bool = False,
                         ttl: int = None, collapse_key: str = None) -> str:
        """
        Send a push notification to specified users.
        
        Args:
            user_ids: List of user IDs to receive the notification
            title: Notification title
            body: Notification body text
            data: Additional data payload
            high_priority: Whether the notification is high priority
            ttl: Time to live in seconds
            collapse_key: Notification collapse key for grouping
            
        Returns:
            Notification ID
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.notification_service.send_notification(
            user_ids=user_ids,
            title=title,
            body=body,
            data=data,
            high_priority=high_priority,
            ttl=ttl,
            collapse_key=collapse_key
        )
    
    def send_template_notification(self, user_ids: List[str], template_id: str,
                                 template_data: Dict[str, Any] = None,
                                 high_priority: bool = False) -> str:
        """
        Send a template-based notification to specified users.
        
        Args:
            user_ids: List of user IDs to receive the notification
            template_id: ID of the notification template to use
            template_data: Data to apply to the template
            high_priority: Whether the notification is high priority
            
        Returns:
            Notification ID
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.notification_service.send_template_notification(
            user_ids=user_ids,
            template_id=template_id,
            template_data=template_data,
            high_priority=high_priority
        )
    
    def schedule_notification(self, user_ids: List[str], title: str, body: str,
                            scheduled_time: datetime, data: Dict[str, Any] = None,
                            high_priority: bool = False) -> str:
        """
        Schedule a notification for future delivery.
        
        Args:
            user_ids: List of user IDs to receive the notification
            title: Notification title
            body: Notification body text
            scheduled_time: When to deliver the notification
            data: Additional data payload
            high_priority: Whether the notification is high priority
            
        Returns:
            Scheduled notification ID
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.notification_service.schedule_notification(
            user_ids=user_ids,
            title=title,
            body=body,
            scheduled_time=scheduled_time,
            data=data,
            high_priority=high_priority
        )
    
    def cancel_scheduled_notification(self, notification_id: str) -> bool:
        """
        Cancel a scheduled notification.
        
        Args:
            notification_id: ID of the scheduled notification
            
        Returns:
            Success status
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.notification_service.cancel_scheduled_notification(
            notification_id=notification_id
        )
    
    def get_notification_status(self, notification_id: str) -> Dict[str, Any]:
        """
        Get the status of a notification.
        
        Args:
            notification_id: ID of the notification
            
        Returns:
            Notification status information
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.notification_service.get_notification_status(
            notification_id=notification_id
        )
    
    def create_notification_template(self, name: str, title_template: str, 
                                  body_template: str, data_template: Dict[str, Any] = None,
                                  description: str = None) -> str:
        """
        Create a notification template.
        
        Args:
            name: Template name/identifier
            title_template: Template for notification title
            body_template: Template for notification body
            data_template: Template for notification data payload
            description: Template description
            
        Returns:
            Template ID
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.template_service.create_template(
            name=name,
            title_template=title_template,
            body_template=body_template,
            data_template=data_template,
            description=description
        )
    
    def get_analytics(self, start_date: datetime, end_date: datetime,
                    metrics: List[str] = None, group_by: List[str] = None) -> Dict[str, Any]:
        """
        Get notification analytics.
        
        Args:
            start_date: Start date for analytics period
            end_date: End date for analytics period
            metrics: List of metrics to retrieve
            group_by: List of dimensions to group by
            
        Returns:
            Analytics data
        """
        if not self._is_initialized:
            raise RuntimeError("Push Notification Service not initialized")
        
        return self.analytics_service.get_analytics(
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            group_by=group_by
        )

    def get_router(self) -> APIRouter:
        """
        Get the push notifications router with all routes configured.
        
        Returns:
            APIRouter: The configured router
        """
        if self.router is None:
            raise RuntimeError("Router not initialized")
        
        return self.router


# Create singleton instance
push_notifications_service = PushNotificationService()

def get_router() -> APIRouter:
    """
    Get the push notifications router with all routes configured.
    
    Returns:
        APIRouter: The configured router
    """
    router = APIRouter()
    
    # Initialize the service with the router
    push_notifications_service.init_app(app=None, router=router)
    
    @router.get("/", response_model=Dict[str, Any])
    async def plugin_info():
        """Get push notification plugin information."""
        return {
            "name": "Push Notifications System",
            "description": "Comprehensive push notification solution with multi-provider support",
            "version": "1.0.0",
            "features": [
                "Multi-provider support (FCM, APNs, Web Push)",
                "Template-based notifications",
                "Scheduled notifications",
                "Device management",
                "Analytics and reporting"
            ]
        }
    
    return router


# Initialize and export router
push_notifications_router = get_router()
