"""
API Routes for Push Notifications Plugin

This module implements the API routes for the push notifications plugin,
following the standardized security approach.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_admin_user
from app.plugins.push_notifications.schemas.device import (
    DeviceCreate, DeviceResponse, DeviceUpdate, UserDevicesResponse
)
from app.plugins.push_notifications.schemas.notification import (
    NotificationCreate, NotificationResponse, NotificationListResponse,
    TemplateNotificationCreate, NotificationHistoryResponse,
    NotificationTemplateCreate, NotificationTemplateResponse, NotificationTemplateListResponse,
    NotificationCategoryCreate, NotificationCategoryResponse, NotificationCategoryListResponse,
    NotificationTemplateUpdate, NotificationCategoryUpdate
)
from app.plugins.push_notifications.services.notification_service import NotificationService
from app.plugins.push_notifications.services.device_service import DeviceService
from app.plugins.push_notifications.services.template_service import TemplateService
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler
from app.plugins.push_notifications.handlers.redis_handler import RedisHandler
from app.plugins.push_notifications.handlers.rabbitmq_handler import RabbitMQHandler

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/push-notifications",
)

# Initialize handlers
security_handler = SecurityHandler()
redis_handler = None
rabbitmq_handler = None

try:
    redis_handler = RedisHandler()
    logger.info("Redis handler initialized successfully")
except Exception as e:
    logger.warning(f"Redis handler initialization failed: {str(e)}")

try:
    rabbitmq_handler = RabbitMQHandler()
    logger.info("RabbitMQ handler initialized successfully")
except Exception as e:
    logger.warning(f"RabbitMQ handler initialization failed: {str(e)}")


# Device registration routes
@router.post("/devices", response_model=DeviceResponse, summary="Register a device for push notifications")
async def register_device(
    device_data: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Register a device for push notifications.
    
    This endpoint allows a user to register their device to receive push notifications.
    The device data includes platform, token, and device identifiers.
    
    Security:
    - Requires authentication
    - Encrypts sensitive device metadata
    - Validates device data
    - Logs device registration events
    """
    try:
        # Set user_id from authenticated user
        device_data.user_id = current_user["id"]
        
        # Create device service
        device_service = DeviceService(db, security_handler, redis_handler)
        
        # Register device
        device = device_service.register_device(device_data)
        
        logger.info(f"Device registered for user {current_user['id']}: {device.id}")
        
        return DeviceResponse(
            id=device.id,
            user_id=device.user_id,
            platform=device.platform,
            device_identifier=device.device_identifier,
            app_version=device.app_version,
            device_name=device.device_name,
            os_version=device.os_version,
            is_active=device.is_active,
            created_at=device.created_at,
            updated_at=device.updated_at
        )
    except Exception as e:
        logger.error(f"Error registering device: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to register device: {str(e)}")


@router.put("/devices/{device_id}", response_model=DeviceResponse, summary="Update a registered device")
async def update_device(
    device_id: str = Path(..., description="Device ID"),
    device_data: DeviceUpdate = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update a registered device.
    
    This endpoint allows a user to update their registered device information,
    such as the device token or active status.
    
    Security:
    - Requires authentication
    - Validates user ownership of device
    - Encrypts sensitive device metadata
    - Logs device update events
    """
    try:
        # Create device service
        device_service = DeviceService(db, security_handler, redis_handler)
        
        # Get the device to verify ownership
        device = device_service.get_device_by_id(device_id)
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Check if user owns the device
        if device.user_id != current_user["id"]:
            # Only allow admins to update devices they don't own
            if not current_user.get("is_admin", False):
                raise HTTPException(status_code=403, detail="Not authorized to update this device")
        
        # Update device
        updated_device = device_service.update_device(device_id, device_data)
        
        logger.info(f"Device updated for user {current_user['id']}: {device_id}")
        
        return DeviceResponse(
            id=updated_device.id,
            user_id=updated_device.user_id,
            platform=updated_device.platform,
            device_identifier=updated_device.device_identifier,
            app_version=updated_device.app_version,
            device_name=updated_device.device_name,
            os_version=updated_device.os_version,
            is_active=updated_device.is_active,
            created_at=updated_device.created_at,
            updated_at=updated_device.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update device: {str(e)}")


@router.delete("/devices/{device_id}", response_model=Dict[str, Any], summary="Deactivate a device")
async def deactivate_device(
    device_id: str = Path(..., description="Device ID"),
    delete: bool = Query(False, description="Whether to delete the device completely"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Deactivate or delete a registered device.
    
    This endpoint allows a user to deactivate or delete a registered device
    to stop receiving push notifications on the device.
    
    Security:
    - Requires authentication
    - Validates user ownership of device
    - Logs device deactivation/deletion events
    """
    try:
        # Create device service
        device_service = DeviceService(db, security_handler, redis_handler)
        
        # Get the device to verify ownership
        device = device_service.get_device_by_id(device_id)
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Check if user owns the device
        if device.user_id != current_user["id"]:
            # Only allow admins to deactivate devices they don't own
            if not current_user.get("is_admin", False):
                raise HTTPException(status_code=403, detail="Not authorized to deactivate this device")
        
        # Delete or deactivate device
        if delete:
            device_service.delete_device(device_id)
            logger.info(f"Device deleted for user {current_user['id']}: {device_id}")
            return {"success": True, "message": "Device deleted successfully"}
        else:
            device_service.deactivate_device(device_id)
            logger.info(f"Device deactivated for user {current_user['id']}: {device_id}")
            return {"success": True, "message": "Device deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating device: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to deactivate device: {str(e)}")


@router.get("/devices", response_model=UserDevicesResponse, summary="Get user's registered devices")
async def get_user_devices(
    active_only: bool = Query(False, description="Whether to return only active devices"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get a list of registered devices for the current user.
    
    This endpoint allows a user to view all their registered devices.
    
    Security:
    - Requires authentication
    - Filters devices by user ID
    - Decrypts sensitive device metadata
    """
    try:
        # Create device service
        device_service = DeviceService(db, security_handler, redis_handler)
        
        # Get user's devices
        if active_only:
            devices = device_service.get_active_user_devices(current_user["id"])
        else:
            devices = device_service.get_user_devices(current_user["id"])
        
        # Convert to response model
        device_responses = []
        for device in devices:
            device_responses.append(DeviceResponse(
                id=device.id,
                user_id=device.user_id,
                platform=device.platform,
                device_identifier=device.device_identifier,
                app_version=device.app_version,
                device_name=device.device_name,
                os_version=device.os_version,
                is_active=device.is_active,
                created_at=device.created_at,
                updated_at=device.updated_at
            ))
        
        return UserDevicesResponse(
            user_id=current_user["id"],
            devices=device_responses,
            total=len(device_responses)
        )
    except Exception as e:
        logger.error(f"Error retrieving user devices: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve devices: {str(e)}")


# Notification routes
@router.post("/notifications", response_model=NotificationResponse, summary="Send a notification")
async def send_notification(
    notification_data: NotificationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Send a push notification to one or more users.
    
    This endpoint allows an admin to send a notification to multiple users.
    The notification can be scheduled for later delivery.
    
    Security:
    - Requires admin authentication
    - Validates notification payload
    - Logs notification events
    - Uses background tasks for async processing
    """
    try:
        # Create notification service
        notification_service = NotificationService(
            db, 
            security_handler, 
            redis_handler, 
            rabbitmq_handler
        )
        
        # Create and send notification
        result = notification_service.create_notification(
            notification_data=notification_data,
            background_tasks=background_tasks,
            send_immediately=True
        )
        
        logger.info(f"Notification created: {result['notification_id']}, status: {result['status']}")
        
        scheduled_time = None
        if "scheduled_for" in result:
            scheduled_time = datetime.fromisoformat(result["scheduled_for"])
        
        return NotificationResponse(
            id=result["notification_id"],
            status=result["status"],
            scheduled_for=scheduled_time
        )
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")


@router.post("/notifications/template", response_model=NotificationResponse, summary="Send a template notification")
async def send_template_notification(
    notification_data: TemplateNotificationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Send a notification using a template.
    
    This endpoint allows an admin to send a notification based on a predefined template.
    Template data is applied to the template to create the final notification.
    
    Security:
    - Requires admin authentication
    - Validates template and notification payload
    - Logs notification events
    - Uses background tasks for async processing
    """
    try:
        # Create notification service
        notification_service = NotificationService(
            db, 
            security_handler, 
            redis_handler, 
            rabbitmq_handler
        )
        
        # Create and send template notification
        result = notification_service.create_template_notification(
            notification_data=notification_data,
            background_tasks=background_tasks,
            send_immediately=True
        )
        
        logger.info(f"Template notification created: {result['notification_id']}, status: {result['status']}")
        
        scheduled_time = None
        if "scheduled_for" in result:
            scheduled_time = datetime.fromisoformat(result["scheduled_for"])
        
        return NotificationResponse(
            id=result["notification_id"],
            status=result["status"],
            scheduled_for=scheduled_time,
            title=result.get("title"),
            body=result.get("body")
        )
    except Exception as e:
        logger.error(f"Error sending template notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send template notification: {str(e)}")


@router.get("/notifications/history", response_model=NotificationHistoryResponse, summary="Get notification history")
async def get_notification_history(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(50, description="Maximum number of results"),
    offset: int = Query(0, description="Result offset"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Get notification history.
    
    This endpoint allows an admin to view notification history,
    optionally filtered by user ID and date range.
    
    Security:
    - Requires admin authentication
    - Logs history access events
    """
    try:
        # Create notification service
        notification_service = NotificationService(
            db, 
            security_handler, 
            redis_handler, 
            rabbitmq_handler
        )
        
        # Get notification history
        notifications, total = notification_service.get_notification_history(
            user_id=user_id,
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert to response model
        notification_responses = []
        for notification in notifications:
            notification_responses.append(NotificationResponse(
                id=notification.id,
                title=notification.title,
                body=notification.body,
                status="sent" if notification.sent_at else "scheduled",
                scheduled_for=notification.scheduled_for,
                created_at=notification.created_at,
                sent_at=notification.sent_at
            ))
        
        return NotificationHistoryResponse(
            notifications=notification_responses,
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Error retrieving notification history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve notification history: {str(e)}")


# Template routes
@router.post("/templates", response_model=NotificationTemplateResponse, summary="Create a notification template")
async def create_template(
    template_data: NotificationTemplateCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Create a notification template.
    
    This endpoint allows an admin to create a reusable notification template.
    The template can include placeholders that are replaced with data when sending.
    
    Security:
    - Requires admin authentication
    - Validates template data
    - Encrypts sensitive template metadata
    - Logs template creation events
    """
    try:
        # Set created_by from authenticated user
        template_data.created_by = current_user["id"]
        
        # Create template service
        template_service = TemplateService(db, security_handler, redis_handler)
        
        # Create template
        template = template_service.create_template(template_data)
        
        logger.info(f"Notification template created: {template.id}")
        
        return NotificationTemplateResponse(
            id=template.id,
            name=template.name,
            title_template=template.title_template,
            body_template=template.body_template,
            data_template=template.data_template,
            category_id=template.category_id,
            metadata=template.metadata,
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at,
            created_by=template.created_by,
            updated_by=template.updated_by
        )
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")


@router.put("/templates/{template_id}", response_model=NotificationTemplateResponse, summary="Update a notification template")
async def update_template(
    template_id: str = Path(..., description="Template ID"),
    template_data: NotificationTemplateUpdate = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Update a notification template.
    
    This endpoint allows an admin to update an existing notification template.
    
    Security:
    - Requires admin authentication
    - Validates template data
    - Encrypts sensitive template metadata
    - Logs template update events
    """
    try:
        # Set updated_by from authenticated user
        if template_data:
            template_data.updated_by = current_user["id"]
        
        # Create template service
        template_service = TemplateService(db, security_handler, redis_handler)
        
        # Update template
        template = template_service.update_template(template_id, template_data)
        
        logger.info(f"Notification template updated: {template_id}")
        
        return NotificationTemplateResponse(
            id=template.id,
            name=template.name,
            title_template=template.title_template,
            body_template=template.body_template,
            data_template=template.data_template,
            category_id=template.category_id,
            metadata=template.metadata,
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at,
            created_by=template.created_by,
            updated_by=template.updated_by
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")


@router.delete("/templates/{template_id}", response_model=Dict[str, Any], summary="Delete a notification template")
async def delete_template(
    template_id: str = Path(..., description="Template ID"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Delete a notification template.
    
    This endpoint allows an admin to delete an existing notification template.
    
    Security:
    - Requires admin authentication
    - Logs template deletion events
    """
    try:
        # Create template service
        template_service = TemplateService(db, security_handler, redis_handler)
        
        # Delete template
        template_service.delete_template(template_id)
        
        logger.info(f"Notification template deleted: {template_id}")
        
        return {"success": True, "message": "Template deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")


@router.get("/templates", response_model=NotificationTemplateListResponse, summary="Get notification templates")
async def get_templates(
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    active_only: bool = Query(False, description="Whether to return only active templates"),
    limit: int = Query(50, description="Maximum number of results"),
    offset: int = Query(0, description="Result offset"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Get notification templates.
    
    This endpoint allows an admin to view notification templates,
    optionally filtered by category ID and active status.
    
    Security:
    - Requires admin authentication
    - Decrypts sensitive template metadata
    """
    try:
        # Create template service
        template_service = TemplateService(db, security_handler, redis_handler)
        
        # Get templates
        templates = template_service.get_templates(
            category_id=category_id,
            active_only=active_only,
            limit=limit,
            offset=offset
        )
        
        # Convert to response model
        template_responses = []
        for template in templates:
            template_responses.append(NotificationTemplateResponse(
                id=template.id,
                name=template.name,
                title_template=template.title_template,
                body_template=template.body_template,
                data_template=template.data_template,
                category_id=template.category_id,
                metadata=template.metadata,
                is_active=template.is_active,
                created_at=template.created_at,
                updated_at=template.updated_at,
                created_by=template.created_by,
                updated_by=template.updated_by
            ))
        
        return NotificationTemplateListResponse(
            templates=template_responses,
            count=len(template_responses)
        )
    except Exception as e:
        logger.error(f"Error retrieving templates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve templates: {str(e)}")


# Category routes
@router.post("/categories", response_model=NotificationCategoryResponse, summary="Create a notification category")
async def create_category(
    category_data: NotificationCategoryCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Create a notification category.
    
    This endpoint allows an admin to create a notification category
    for organizing templates.
    
    Security:
    - Requires admin authentication
    - Validates category data
    - Logs category creation events
    """
    try:
        # Set created_by from authenticated user
        category_data.created_by = current_user["id"]
        
        # Create template service
        template_service = TemplateService(db, security_handler, redis_handler)
        
        # Create category
        category = template_service.create_category(category_data)
        
        logger.info(f"Notification category created: {category.id}")
        
        return NotificationCategoryResponse(
            id=category.id,
            name=category.name,
            description=category.description,
            created_at=category.created_at,
            updated_at=category.updated_at,
            created_by=category.created_by,
            updated_by=category.updated_by
        )
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create category: {str(e)}")


@router.put("/categories/{category_id}", response_model=NotificationCategoryResponse, summary="Update a notification category")
async def update_category(
    category_id: str = Path(..., description="Category ID"),
    category_data: NotificationCategoryUpdate = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Update a notification category.
    
    This endpoint allows an admin to update an existing notification category.
    
    Security:
    - Requires admin authentication
    - Validates category data
    - Logs category update events
    """
    try:
        # Set updated_by from authenticated user
        if category_data:
            category_data.updated_by = current_user["id"]
        
        # Create template service
        template_service = TemplateService(db, security_handler, redis_handler)
        
        # Update category
        category = template_service.update_category(category_id, category_data)
        
        logger.info(f"Notification category updated: {category_id}")
        
        return NotificationCategoryResponse(
            id=category.id,
            name=category.name,
            description=category.description,
            created_at=category.created_at,
            updated_at=category.updated_at,
            created_by=category.created_by,
            updated_by=category.updated_by
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating category: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update category: {str(e)}")


@router.delete("/categories/{category_id}", response_model=Dict[str, Any], summary="Delete a notification category")
async def delete_category(
    category_id: str = Path(..., description="Category ID"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Delete a notification category.
    
    This endpoint allows an admin to delete an existing notification category.
    
    Security:
    - Requires admin authentication
    - Validates that no templates are using the category
    - Logs category deletion events
    """
    try:
        # Create template service
        template_service = TemplateService(db, security_handler, redis_handler)
        
        # Delete category
        template_service.delete_category(category_id)
        
        logger.info(f"Notification category deleted: {category_id}")
        
        return {"success": True, "message": "Category deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting category: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete category: {str(e)}")


@router.get("/categories", response_model=NotificationCategoryListResponse, summary="Get notification categories")
async def get_categories(
    limit: int = Query(50, description="Maximum number of results"),
    offset: int = Query(0, description="Result offset"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_admin_user)
):
    """
    Get notification categories.
    
    This endpoint allows an admin to view notification categories.
    
    Security:
    - Requires admin authentication
    """
    try:
        # Create template service
        template_service = TemplateService(db, security_handler, redis_handler)
        
        # Get categories
        categories = template_service.get_categories(
            limit=limit,
            offset=offset
        )
        
        # Convert to response model
        category_responses = []
        for category in categories:
            category_responses.append(NotificationCategoryResponse(
                id=category.id,
                name=category.name,
                description=category.description,
                created_at=category.created_at,
                updated_at=category.updated_at,
                created_by=category.created_by,
                updated_by=category.updated_by
            ))
        
        return NotificationCategoryListResponse(
            categories=category_responses,
            count=len(category_responses)
        )
    except Exception as e:
        logger.error(f"Error retrieving categories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve categories: {str(e)}")


# Web Push specific routes
@router.get("/web-push/vapid-public-key", response_model=Dict[str, str], summary="Get VAPID public key")
async def get_vapid_public_key(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get VAPID public key for Web Push.
    
    This endpoint returns the VAPID public key needed for Web Push subscription.
    
    Security:
    - Requires authentication
    """
    try:
        # Create notification service
        notification_service = NotificationService(
            db, 
            security_handler, 
            redis_handler, 
            rabbitmq_handler
        )
        
        # Get provider
        web_push_provider = notification_service.web_push_provider
        
        if not web_push_provider:
            raise HTTPException(status_code=404, detail="Web Push provider not configured")
        
        # Get public key
        public_key = web_push_provider.get_public_key()
        
        if not public_key:
            raise HTTPException(status_code=500, detail="Failed to get VAPID public key")
        
        return {"vapid_public_key": public_key}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting VAPID public key: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get VAPID public key: {str(e)}")
