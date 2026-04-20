"""
Notification Service for Push Notifications

This module provides the core notification service for the push notifications plugin,
implementing the standardized security approach.
"""

import logging
import uuid
import json
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends, BackgroundTasks

from app.plugins.push_notifications.models.database import (
    Device, Notification, NotificationDevice, 
    NotificationTemplate, NotificationCategory, NotificationSegment
)
from app.plugins.push_notifications.schemas.notification import (
    NotificationCreate, NotificationTemplateCreate, TemplateNotificationCreate
)
from app.plugins.push_notifications.schemas.device import DeviceCreate
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler
from app.plugins.push_notifications.handlers.redis_handler import RedisHandler
from app.plugins.push_notifications.handlers.rabbitmq_handler import RabbitMQHandler
from app.plugins.push_notifications.providers.base_provider import BasePushProvider
from app.plugins.push_notifications.providers.fcm_provider import FCMProvider
from app.plugins.push_notifications.providers.apns_provider import APNSProvider
from app.plugins.push_notifications.providers.web_push_provider import WebPushProvider
from app.plugins.push_notifications.services.device_service import DeviceService
from app.plugins.push_notifications.services.template_service import TemplateService

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for handling push notifications across multiple providers,
    implementing the standardized security approach.
    """
    
    def __init__(self, db: Session, security_handler: SecurityHandler,
                redis_handler: Optional[RedisHandler] = None,
                rabbitmq_handler: Optional[RabbitMQHandler] = None,
                device_service: Optional[DeviceService] = None,
                template_service: Optional[TemplateService] = None):
        """
        Initialize the notification service.
        
        Args:
            db: Database session
            security_handler: Security handler for encryption and validation
            redis_handler: Redis handler for caching and rate limiting
            rabbitmq_handler: RabbitMQ handler for async processing
            device_service: Optional existing device service instance
            template_service: Optional existing template service instance
        """
        self.db = db
        self.security_handler = security_handler
        self.redis_handler = redis_handler
        self.rabbitmq_handler = rabbitmq_handler
        
        # Initialize providers
        self.providers: Dict[str, BasePushProvider] = {}
        self.fcm_provider = None
        self.apns_provider = None
        self.web_push_provider = None
        
        # Use provided services or create new ones
        self.device_service = device_service or DeviceService(db, security_handler, redis_handler)
        self.template_service = template_service or TemplateService(db, security_handler, redis_handler)
        
        logger.info("Notification service initialized")
    
    def register_fcm_provider(self, api_key: str = None, service_account_json: str = None) -> bool:
        """
        Register the FCM provider.
        
        Args:
            api_key: FCM server key
            service_account_json: Firebase service account JSON
            
        Returns:
            bool: Success status
        """
        try:
            if not api_key and not service_account_json:
                logger.error("FCM provider registration failed: No credentials provided")
                return False
            
            # Initialize FCM provider
            self.fcm_provider = FCMProvider(self.security_handler)
            success = self.fcm_provider.initialize(api_key=api_key, service_account_json=service_account_json)
            
            if success:
                self.providers["fcm"] = self.fcm_provider
                logger.info("FCM provider registered successfully")
            else:
                logger.error("FCM provider registration failed: Initialization error")
            
            return success
        except Exception as e:
            logger.error(f"Error registering FCM provider: {str(e)}")
            return False
    
    def register_apns_provider(self, key_id: str, team_id: str, bundle_id: str,
                              key_file_path: str, is_production: bool = True,
                              topics: Dict[str, str] = None) -> bool:
        """
        Register the APNs provider.
        
        Args:
            key_id: APNs key ID
            team_id: Apple Developer Team ID
            bundle_id: App bundle ID
            key_file_path: Path to the p8 private key file
            is_production: Whether to use production environment
            topics: Dictionary of custom topics
            
        Returns:
            bool: Success status
        """
        try:
            # Initialize APNs provider
            self.apns_provider = APNSProvider(self.security_handler)
            success = self.apns_provider.initialize(
                key_id=key_id,
                team_id=team_id,
                bundle_id=bundle_id,
                key_file_path=key_file_path,
                is_production=is_production,
                topics=topics
            )
            
            if success:
                self.providers["apns"] = self.apns_provider
                logger.info("APNs provider registered successfully")
            else:
                logger.error("APNs provider registration failed: Initialization error")
            
            return success
        except Exception as e:
            logger.error(f"Error registering APNs provider: {str(e)}")
            return False
    
    def register_web_push_provider(self, vapid_private_key: str, vapid_public_key: str,
                                 vapid_claims_email: str, vapid_claims_sub: str = None) -> bool:
        """
        Register the Web Push provider.
        
        Args:
            vapid_private_key: VAPID private key
            vapid_public_key: VAPID public key
            vapid_claims_email: Email for VAPID claims
            vapid_claims_sub: Subject for VAPID claims
            
        Returns:
            bool: Success status
        """
        try:
            # Initialize Web Push provider
            self.web_push_provider = WebPushProvider(self.security_handler)
            success = self.web_push_provider.initialize(
                vapid_private_key=vapid_private_key,
                vapid_public_key=vapid_public_key,
                vapid_claims_email=vapid_claims_email,
                vapid_claims_sub=vapid_claims_sub
            )
            
            if success:
                self.providers["web_push"] = self.web_push_provider
                logger.info("Web Push provider registered successfully")
            else:
                logger.error("Web Push provider registration failed: Initialization error")
            
            return success
        except Exception as e:
            logger.error(f"Error registering Web Push provider: {str(e)}")
            return False
    
    def get_provider_for_platform(self, platform: str) -> Optional[BasePushProvider]:
        """
        Get the appropriate provider for a platform.
        
        Args:
            platform: Device platform (android, ios, web)
            
        Returns:
            BasePushProvider: Provider instance or None
        """
        platform_map = {
            "android": "fcm",
            "ios": "apns",
            "web": "web_push"
        }
        
        provider_key = platform_map.get(platform.lower())
        if not provider_key:
            logger.warning(f"No provider mapping for platform: {platform}")
            return None
        
        provider = self.providers.get(provider_key)
        if not provider:
            logger.warning(f"Provider {provider_key} not registered")
            return None
        
        return provider
    
    def create_notification(self, notification_data: NotificationCreate, 
                          background_tasks: BackgroundTasks,
                          send_immediately: bool = True) -> Dict[str, Any]:
        """
        Create and send a notification to multiple users.
        
        Args:
            notification_data: Notification data
            background_tasks: FastAPI background tasks
            send_immediately: Whether to send immediately or schedule
            
        Returns:
            Dict: Result with notification ID and status
        """
        try:
            # Validate notification data
            if not notification_data.user_ids:
                raise ValueError("At least one user ID is required")
            
            # Create notification record
            notification_id = str(uuid.uuid4())
            
            new_notification = Notification(
                id=notification_id,
                title=notification_data.title,
                body=notification_data.body,
                data=notification_data.data,
                priority=notification_data.priority,
                ttl=notification_data.ttl,
                collapse_key=notification_data.collapse_key,
                scheduled_for=notification_data.scheduled_for,
                created_at=datetime.utcnow()
            )
            
            self.db.add(new_notification)
            self.db.flush()
            
            # If scheduled for later, don't send immediately
            if notification_data.scheduled_for and send_immediately:
                if notification_data.scheduled_for > datetime.utcnow():
                    # Store in Redis for scheduled delivery
                    if self.redis_handler:
                        self.redis_handler.schedule_notification(
                            notification_id=notification_id,
                            scheduled_time=notification_data.scheduled_for,
                            payload={
                                "notification_id": notification_id,
                                "user_ids": notification_data.user_ids,
                                "title": notification_data.title,
                                "body": notification_data.body,
                                "data": notification_data.data,
                                "priority": notification_data.priority == "high",
                                "ttl": notification_data.ttl,
                                "collapse_key": notification_data.collapse_key
                            }
                        )
                    
                    self.db.commit()
                    return {
                        "notification_id": notification_id,
                        "status": "scheduled",
                        "scheduled_for": notification_data.scheduled_for.isoformat()
                    }
            
            # Process send in background if requested
            if send_immediately:
                if self.rabbitmq_handler:
                    # Send via RabbitMQ for async processing
                    self.rabbitmq_handler.publish_message(
                        queue_key="push_notifications",
                        message={
                            "action": "send_notification",
                            "notification_id": notification_id,
                            "user_ids": notification_data.user_ids,
                            "title": notification_data.title,
                            "body": notification_data.body,
                            "data": notification_data.data,
                            "priority": notification_data.priority == "high"
                        },
                        priority=10 if notification_data.priority == "high" else 0
                    )
                    sent_status = "queued"
                else:
                    # Send in background task
                    background_tasks.add_task(
                        self.send_notification_to_users,
                        notification_id=notification_id,
                        user_ids=notification_data.user_ids,
                        title=notification_data.title,
                        body=notification_data.body,
                        data=notification_data.data,
                        high_priority=notification_data.priority == "high"
                    )
                    sent_status = "processing"
            else:
                sent_status = "created"
            
            self.db.commit()
            
            return {
                "notification_id": notification_id,
                "status": sent_status
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create notification: {str(e)}")
    
    def create_template_notification(self, notification_data: TemplateNotificationCreate,
                                   background_tasks: BackgroundTasks,
                                   send_immediately: bool = True) -> Dict[str, Any]:
        """
        Create and send a notification based on a template.
        
        Args:
            notification_data: Template notification data
            background_tasks: FastAPI background tasks
            send_immediately: Whether to send immediately or schedule
            
        Returns:
            Dict: Result with notification ID and status
        """
        try:
            # Get the template
            template = self.template_service.get_template_by_id(notification_data.template_id)
            if not template:
                raise ValueError(f"Template not found: {notification_data.template_id}")
            
            # Apply template data to create title and body
            title = self._apply_template(template.title_template, notification_data.template_data)
            body = self._apply_template(template.body_template, notification_data.template_data)
            
            # Apply template to data if it exists
            data = None
            if template.data_template:
                data = self._apply_template_to_data(template.data_template, notification_data.template_data)
            
            # Create notification record
            notification_id = str(uuid.uuid4())
            
            new_notification = Notification(
                id=notification_id,
                title=title,
                body=body,
                data=data,
                priority=notification_data.priority,
                template_id=notification_data.template_id,
                scheduled_for=notification_data.scheduled_for,
                created_at=datetime.utcnow()
            )
            
            self.db.add(new_notification)
            self.db.flush()
            
            # If scheduled for later, don't send immediately
            if notification_data.scheduled_for and send_immediately:
                if notification_data.scheduled_for > datetime.utcnow():
                    # Store in Redis for scheduled delivery
                    if self.redis_handler:
                        self.redis_handler.schedule_notification(
                            notification_id=notification_id,
                            scheduled_time=notification_data.scheduled_for,
                            payload={
                                "notification_id": notification_id,
                                "user_ids": notification_data.user_ids,
                                "title": title,
                                "body": body,
                                "data": data,
                                "priority": notification_data.priority == "high"
                            }
                        )
                    
                    self.db.commit()
                    return {
                        "notification_id": notification_id,
                        "status": "scheduled",
                        "scheduled_for": notification_data.scheduled_for.isoformat()
                    }
            
            # Process send in background if requested
            if send_immediately:
                if self.rabbitmq_handler:
                    # Send via RabbitMQ for async processing
                    self.rabbitmq_handler.publish_message(
                        queue_key="push_notifications",
                        message={
                            "action": "send_notification",
                            "notification_id": notification_id,
                            "user_ids": notification_data.user_ids,
                            "title": title,
                            "body": body,
                            "data": data,
                            "priority": notification_data.priority == "high"
                        },
                        priority=10 if notification_data.priority == "high" else 0
                    )
                    sent_status = "queued"
                else:
                    # Send in background task
                    background_tasks.add_task(
                        self.send_notification_to_users,
                        notification_id=notification_id,
                        user_ids=notification_data.user_ids,
                        title=title,
                        body=body,
                        data=data,
                        high_priority=notification_data.priority == "high"
                    )
                    sent_status = "processing"
            else:
                sent_status = "created"
            
            self.db.commit()
            
            return {
                "notification_id": notification_id,
                "status": sent_status,
                "title": title,
                "body": body
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating template notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create template notification: {str(e)}")
    
    def _apply_template(self, template: str, data: Dict[str, Any]) -> str:
        """
        Apply template data to a template string.
        
        Args:
            template: Template string with placeholders
            data: Data to apply to template
            
        Returns:
            str: Rendered template
        """
        result = template
        
        # Simple placeholder replacement
        for key, value in data.items():
            placeholder = '{{' + key + '}}'
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        
        return result
    
    def _apply_template_to_data(self, data_template: Dict[str, Any], 
                              template_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply template data to a data template.
        
        Args:
            data_template: Data template with placeholders
            template_data: Data to apply to template
            
        Returns:
            Dict: Rendered data
        """
        # Convert to JSON and back for a deep copy
        result = json.loads(json.dumps(data_template))
        
        # Recursively replace placeholders in values
        def process_dict(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    process_dict(v)
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            process_dict(item)
                        elif isinstance(item, str):
                            for key, value in template_data.items():
                                placeholder = '{{' + key + '}}'
                                if placeholder in item:
                                    v[i] = item.replace(placeholder, str(value))
                elif isinstance(v, str):
                    for key, value in template_data.items():
                        placeholder = '{{' + key + '}}'
                        if placeholder in v:
                            d[k] = v.replace(placeholder, str(value))
        
        process_dict(result)
        return result
    
    def send_notification_to_users(self, notification_id: str, user_ids: List[str],
                                 title: str, body: str, data: Dict[str, Any] = None,
                                 high_priority: bool = False) -> Dict[str, Any]:
        """
        Send a notification to multiple users.
        
        Args:
            notification_id: ID of the notification
            user_ids: List of user IDs
            title: Notification title
            body: Notification body
            data: Notification data
            high_priority: Whether notification is high priority
            
        Returns:
            Dict: Result with success counts
        """
        result = {
            "notification_id": notification_id,
            "total_users": len(user_ids),
            "processed_users": 0,
            "success_devices": 0,
            "failed_devices": 0,
            "user_results": []
        }
        
        try:
            # Update notification as being sent
            notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
            if notification:
                notification.sent_at = datetime.utcnow()
                self.db.commit()
            
            # Process each user
            for user_id in user_ids:
                # Get user's devices
                devices = self.device_service.get_user_devices(user_id)
                
                if not devices:
                    result["user_results"].append({
                        "user_id": user_id,
                        "success": False,
                        "message": "No devices found",
                        "device_count": 0
                    })
                    continue
                
                # Group devices by platform for batch sending
                platform_devices = {}
                for device in devices:
                    if device.is_active:
                        if device.platform not in platform_devices:
                            platform_devices[device.platform] = []
                        
                        platform_devices[device.platform].append({
                            "device_id": device.id,
                            "token": device.token,
                            "platform": device.platform
                        })
                
                user_result = {
                    "user_id": user_id,
                    "success": False,
                    "device_count": len(devices),
                    "success_devices": 0,
                    "failed_devices": 0,
                    "device_results": []
                }
                
                # Send to each platform group
                for platform, devices in platform_devices.items():
                    provider = self.get_provider_for_platform(platform)
                    
                    if not provider:
                        for device in devices:
                            user_result["device_results"].append({
                                "device_id": device["device_id"],
                                "success": False,
                                "message": f"No provider available for platform {platform}"
                            })
                            user_result["failed_devices"] += 1
                            result["failed_devices"] += 1
                        
                        continue
                    
                    # Handle Web Push differently due to subscription format
                    if platform == "web":
                        for device in devices:
                            device_id = device["device_id"]
                            db_device = self.device_service.get_device_by_id(device_id)
                            
                            if not db_device:
                                user_result["device_results"].append({
                                    "device_id": device_id,
                                    "success": False,
                                    "message": "Device not found"
                                })
                                user_result["failed_devices"] += 1
                                result["failed_devices"] += 1
                                continue
                            
                            # Extract subscription info from token or device data
                            subscription_info = None
                            try:
                                if db_device.device_data and "subscription" in db_device.device_data:
                                    subscription_info = db_device.device_data["subscription"]
                                else:
                                    subscription_info = json.loads(db_device.token)
                            except json.JSONDecodeError:
                                user_result["device_results"].append({
                                    "device_id": device_id,
                                    "success": False,
                                    "message": "Invalid subscription format"
                                })
                                user_result["failed_devices"] += 1
                                result["failed_devices"] += 1
                                continue
                            
                            # Send to web device
                            send_result = provider.send_notification(
                                notification_id=notification_id,
                                user_id=user_id,
                                device_id=device_id,
                                subscription_info=subscription_info,
                                title=title,
                                body=body,
                                data=data,
                                high_priority=high_priority
                            )
                            
                            # Create delivery record
                            delivery = NotificationDevice(
                                id=str(uuid.uuid4()),
                                notification_id=notification_id,
                                user_id=user_id,
                                device_id=device_id,
                                status="sent" if send_result["success"] else "failed",
                                provider="web_push",
                                error_message=None if send_result["success"] else send_result["message"],
                                error_code=None if send_result["success"] else send_result.get("details", {}).get("status_code"),
                                created_at=datetime.utcnow()
                            )
                            
                            self.db.add(delivery)
                            
                            user_result["device_results"].append({
                                "device_id": device_id,
                                "success": send_result["success"],
                                "message": send_result["message"]
                            })
                            
                            if send_result["success"]:
                                user_result["success_devices"] += 1
                                result["success_devices"] += 1
                            else:
                                user_result["failed_devices"] += 1
                                result["failed_devices"] += 1
                    else:
                        # Send batch to other platforms
                        send_result = provider.send_to_multiple_devices(
                            notification_id=notification_id,
                            user_id=user_id,
                            device_tokens=devices,
                            title=title,
                            body=body,
                            data=data,
                            high_priority=high_priority
                        )
                        
                        # Process results for each device
                        for device_result in send_result["details"]["device_results"]:
                            device_id = device_result["device_id"]
                            success = device_result.get("success", False)
                            
                            # Create delivery record
                            delivery = NotificationDevice(
                                id=str(uuid.uuid4()),
                                notification_id=notification_id,
                                user_id=user_id,
                                device_id=device_id,
                                status="sent" if success else "failed",
                                provider=platform,
                                error_message=None if success else device_result.get("error", device_result.get("message")),
                                error_code=None if success else device_result.get("error_code"),
                                created_at=datetime.utcnow()
                            )
                            
                            self.db.add(delivery)
                            
                            user_result["device_results"].append({
                                "device_id": device_id,
                                "success": success,
                                "message": device_result.get("message", "Unknown status")
                            })
                            
                            if success:
                                user_result["success_devices"] += 1
                                result["success_devices"] += 1
                            else:
                                user_result["failed_devices"] += 1
                                result["failed_devices"] += 1
                
                # Update user result success status
                user_result["success"] = user_result["success_devices"] > 0
                result["user_results"].append(user_result)
                result["processed_users"] += 1
                
                # Save to database
                self.db.commit()
                
                # Track metrics if Redis is available
                if self.redis_handler:
                    self.redis_handler.increment_metric(
                        metric="push_notifications_sent",
                        tags={
                            "user_id": user_id,
                            "notification_id": notification_id,
                            "success": str(user_result["success"])
                        }
                    )
            
            # Update overall result
            result["success"] = result["success_devices"] > 0
            
            # If Redis is available, log total metrics
            if self.redis_handler:
                self.redis_handler.increment_metric(
                    metric="push_notifications_total",
                    tags={
                        "notification_id": notification_id,
                        "success": str(result["success"])
                    },
                    value=result["success_devices"]
                )
            
            return result
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error sending notification to users: {str(e)}")
            result["error"] = str(e)
            return result
    
    def get_notification_by_id(self, notification_id: str) -> Optional[Notification]:
        """
        Get a notification by ID.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            Notification: Notification or None
        """
        return self.db.query(Notification).filter(Notification.id == notification_id).first()
    
    def get_notification_history(self, user_id: Optional[str] = None, 
                               limit: int = 50, offset: int = 0,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> Tuple[List[Notification], int]:
        """
        Get notification history for a user or all users.
        
        Args:
            user_id: Optional user ID to filter by
            limit: Maximum number of results
            offset: Result offset
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Tuple: List of notifications and total count
        """
        query = self.db.query(Notification)
        
        # Apply filters
        if user_id:
            # Join with deliveries to filter by user
            query = query.join(
                NotificationDevice,
                Notification.id == NotificationDevice.notification_id
            ).filter(
                NotificationDevice.user_id == user_id
            ).distinct()
        
        if start_date:
            query = query.filter(Notification.created_at >= start_date)
        
        if end_date:
            query = query.filter(Notification.created_at <= end_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        notifications = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
        
        return notifications, total
