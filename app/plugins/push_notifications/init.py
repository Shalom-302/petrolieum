"""
Initialization script for Push Notifications Plugin

This module initializes the push notifications plugin,
configuring providers and registering routes.
"""

import logging
import os
from typing import Dict, Any, Optional

from fastapi import FastAPI

from app.plugins.push_notifications.main import PushNotificationPlugin
from app.plugins.push_notifications.routes import router
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler
from app.plugins.push_notifications.handlers.redis_handler import RedisHandler
from app.plugins.push_notifications.handlers.rabbitmq_handler import RabbitMQHandler

logger = logging.getLogger(__name__)

async def init_push_notifications_plugin(app: FastAPI) -> Optional[PushNotificationPlugin]:
    """
    Initialize the push notifications plugin.
    
    Args:
        app: FastAPI application
        
    Returns:
        PushNotificationPlugin: Initialized plugin or None
    """
    try:
        # Check if the plugin is enabled
        if os.environ.get("PUSH_NOTIFICATION_ENABLED", "false").lower() != "true":
            logger.info("Push notifications plugin is disabled")
            return None
        
        logger.info("Initializing push notifications plugin")
        
        # Initialize handlers
        security_handler = SecurityHandler()
        
        redis_handler = None
        try:
            redis_handler = RedisHandler()
            logger.info("Redis handler initialized successfully")
        except Exception as e:
            logger.warning(f"Redis handler initialization failed: {str(e)}")
        
        rabbitmq_handler = None
        try:
            rabbitmq_handler = RabbitMQHandler()
            logger.info("RabbitMQ handler initialized successfully")
        except Exception as e:
            logger.warning(f"RabbitMQ handler initialization failed: {str(e)}")
        
        # Create plugin instance
        plugin = PushNotificationPlugin(
            security_handler=security_handler,
            redis_handler=redis_handler,
            rabbitmq_handler=rabbitmq_handler
        )
        
        # Initialize FCM provider if credentials are available
        fcm_api_key = os.environ.get("FCM_API_KEY")
        fcm_service_account_json = os.environ.get("FCM_SERVICE_ACCOUNT_JSON")
        
        if fcm_api_key or fcm_service_account_json:
            success = plugin.initialize_fcm_provider(
                api_key=fcm_api_key,
                service_account_json=fcm_service_account_json
            )
            if success:
                logger.info("FCM provider initialized successfully")
            else:
                logger.error("FCM provider initialization failed")
        else:
            logger.info("FCM provider not configured, skipping initialization")
        
        # Initialize APNs provider if credentials are available
        apns_key_id = os.environ.get("APNS_KEY_ID")
        apns_team_id = os.environ.get("APNS_TEAM_ID")
        apns_bundle_id = os.environ.get("APNS_BUNDLE_ID")
        apns_key_file = os.environ.get("APNS_KEY_FILE")
        apns_production = os.environ.get("APNS_PRODUCTION", "true").lower() == "true"
        
        if all([apns_key_id, apns_team_id, apns_bundle_id, apns_key_file]):
            success = plugin.initialize_apns_provider(
                key_id=apns_key_id,
                team_id=apns_team_id,
                bundle_id=apns_bundle_id,
                key_file_path=apns_key_file,
                is_production=apns_production
            )
            if success:
                logger.info("APNs provider initialized successfully")
            else:
                logger.error("APNs provider initialization failed")
        else:
            logger.info("APNs provider not configured, skipping initialization")
        
        # Initialize Web Push provider if credentials are available
        vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY")
        vapid_public_key = os.environ.get("VAPID_PUBLIC_KEY")
        vapid_claims_email = os.environ.get("VAPID_CLAIMS_EMAIL")
        vapid_claims_sub = os.environ.get("VAPID_CLAIMS_SUB")
        
        if all([vapid_private_key, vapid_public_key, vapid_claims_email]):
            success = plugin.initialize_web_push_provider(
                vapid_private_key=vapid_private_key,
                vapid_public_key=vapid_public_key,
                vapid_claims_email=vapid_claims_email,
                vapid_claims_sub=vapid_claims_sub
            )
            if success:
                logger.info("Web Push provider initialized successfully")
            else:
                logger.error("Web Push provider initialization failed")
        else:
            logger.info("Web Push provider not configured, skipping initialization")
        
        # Register routes
        app.include_router(router)
        logger.info("Push notifications routes registered successfully")
        
        return plugin
    except Exception as e:
        logger.error(f"Failed to initialize push notifications plugin: {str(e)}")
        return None
