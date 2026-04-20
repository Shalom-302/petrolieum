"""
Device Service for Push Notifications

This module provides the device management service for the push notifications plugin,
implementing the standardized security approach.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.plugins.push_notifications.models.database import Device
from app.plugins.push_notifications.schemas.device import DeviceCreate, DeviceUpdate
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler
from app.plugins.push_notifications.handlers.redis_handler import RedisHandler

logger = logging.getLogger(__name__)

class DeviceService:
    """
    Service for managing devices for push notifications,
    implementing the standardized security approach.
    """
    
    def __init__(self, db: Session, security_handler: SecurityHandler,
                redis_handler: Optional[RedisHandler] = None):
        """
        Initialize the device service.
        
        Args:
            db: Database session
            security_handler: Security handler for encryption and validation
            redis_handler: Redis handler for caching and rate limiting
        """
        self.db = db
        self.security_handler = security_handler
        self.redis_handler = redis_handler
        logger.info("Device service initialized")
    
    def register_device(self, device_data: DeviceCreate) -> Device:
        """
        Register a new device for push notifications.
        
        Args:
            device_data: Device registration data
            
        Returns:
            Device: Registered device
        """
        try:
            # Check if device already exists
            existing_device = self.db.query(Device).filter(
                Device.device_identifier == device_data.device_identifier,
                Device.user_id == device_data.user_id
            ).first()
            
            if existing_device:
                # Update existing device
                existing_device.token = device_data.token
                existing_device.platform = device_data.platform
                existing_device.app_version = device_data.app_version
                existing_device.device_name = device_data.device_name
                existing_device.os_version = device_data.os_version
                existing_device.is_active = True
                existing_device.updated_at = datetime.utcnow()
                
                # Update device metadata securely
                if device_data.device_data:
                    # Encrypt sensitive device data
                    encrypted_data = self.security_handler.encrypt_data(device_data.device_data)
                    existing_device.encrypted_metadata = encrypted_data
                
                # Update segmentation metadata
                if hasattr(device_data, 'segmentation_data') and device_data.segmentation_data:
                    existing_device.segment_metadata = device_data.segmentation_data
                
                self.db.commit()
                
                # Log device update
                logger.info(f"Device updated for user {device_data.user_id}: {device_data.device_identifier}")
                
                # Cache in Redis if available
                if self.redis_handler:
                    cache_key = f"device:{existing_device.id}"
                    self.redis_handler.set_cache(
                        key=cache_key,
                        value={
                            "id": existing_device.id,
                            "user_id": existing_device.user_id,
                            "platform": existing_device.platform,
                            "is_active": existing_device.is_active
                        },
                        ttl=3600  # 1 hour cache
                    )
                
                return existing_device
            
            # Create new device
            device_id = str(uuid.uuid4())
            
            # Encrypt sensitive device data if provided
            encrypted_data = None
            if device_data.device_data:
                encrypted_data = self.security_handler.encrypt_data(device_data.device_data)
            
            new_device = Device(
                id=device_id,
                user_id=device_data.user_id,
                token=device_data.token,
                platform=device_data.platform,
                device_identifier=device_data.device_identifier,
                app_version=device_data.app_version,
                device_name=device_data.device_name,
                os_version=device_data.os_version,
                encrypted_metadata=encrypted_data,
                segment_metadata=device_data.segmentation_data if hasattr(device_data, 'segmentation_data') else None,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.db.add(new_device)
            self.db.commit()
            
            # Log device registration
            logger.info(f"Device registered for user {device_data.user_id}: {device_data.device_identifier}")
            
            # Cache in Redis if available
            if self.redis_handler:
                cache_key = f"device:{device_id}"
                self.redis_handler.set_cache(
                    key=cache_key,
                    value={
                        "id": device_id,
                        "user_id": new_device.user_id,
                        "platform": new_device.platform,
                        "is_active": new_device.is_active
                    },
                    ttl=3600  # 1 hour cache
                )
            
            return new_device
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error registering device: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to register device: {str(e)}")
    
    def update_device(self, device_id: str, device_data: DeviceUpdate) -> Device:
        """
        Update an existing device.
        
        Args:
            device_id: Device ID
            device_data: Updated device data
            
        Returns:
            Device: Updated device
        """
        try:
            device = self.db.query(Device).filter(Device.id == device_id).first()
            
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            
            # Update fields if provided
            if device_data.token is not None:
                device.token = device_data.token
            
            if device_data.platform is not None:
                device.platform = device_data.platform
            
            if device_data.app_version is not None:
                device.app_version = device_data.app_version
            
            if device_data.device_name is not None:
                device.device_name = device_data.device_name
            
            if device_data.os_version is not None:
                device.os_version = device_data.os_version
            
            if device_data.is_active is not None:
                device.is_active = device_data.is_active
            
            # Update device metadata securely
            if device_data.device_data:
                # Encrypt sensitive device data
                encrypted_data = self.security_handler.encrypt_data(device_data.device_data)
                device.encrypted_metadata = encrypted_data
            
            # Update segmentation metadata
            if hasattr(device_data, 'segmentation_data') and device_data.segmentation_data:
                device.segment_metadata = device_data.segmentation_data
            
            device.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Log device update
            logger.info(f"Device updated: {device_id}")
            
            # Update Redis cache if available
            if self.redis_handler:
                cache_key = f"device:{device_id}"
                self.redis_handler.set_cache(
                    key=cache_key,
                    value={
                        "id": device.id,
                        "user_id": device.user_id,
                        "platform": device.platform,
                        "is_active": device.is_active
                    },
                    ttl=3600  # 1 hour cache
                )
            
            return device
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating device: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update device: {str(e)}")
    
    def deactivate_device(self, device_id: str) -> Device:
        """
        Deactivate a device.
        
        Args:
            device_id: Device ID
            
        Returns:
            Device: Deactivated device
        """
        try:
            device = self.db.query(Device).filter(Device.id == device_id).first()
            
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            
            device.is_active = False
            device.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Log device deactivation
            logger.info(f"Device deactivated: {device_id}")
            
            # Update Redis cache if available
            if self.redis_handler:
                cache_key = f"device:{device_id}"
                self.redis_handler.set_cache(
                    key=cache_key,
                    value={
                        "id": device.id,
                        "user_id": device.user_id,
                        "platform": device.platform,
                        "is_active": False
                    },
                    ttl=3600  # 1 hour cache
                )
                
                # Remove device from user's active devices list
                user_devices_key = f"user_devices:{device.user_id}"
                self.redis_handler.remove_from_set(
                    key=user_devices_key,
                    value=device_id
                )
            
            return device
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deactivating device: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to deactivate device: {str(e)}")
    
    def delete_device(self, device_id: str) -> bool:
        """
        Delete a device.
        
        Args:
            device_id: Device ID
            
        Returns:
            bool: Success status
        """
        try:
            device = self.db.query(Device).filter(Device.id == device_id).first()
            
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            
            # Store user_id before deletion for cache cleanup
            user_id = device.user_id
            
            self.db.delete(device)
            self.db.commit()
            
            # Log device deletion
            logger.info(f"Device deleted: {device_id}")
            
            # Clean up Redis cache if available
            if self.redis_handler:
                cache_key = f"device:{device_id}"
                self.redis_handler.delete_cache(cache_key)
                
                # Remove device from user's devices list
                user_devices_key = f"user_devices:{user_id}"
                self.redis_handler.remove_from_set(
                    key=user_devices_key,
                    value=device_id
                )
            
            return True
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting device: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete device: {str(e)}")
    
    def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """
        Get a device by ID.
        
        Args:
            device_id: Device ID
            
        Returns:
            Device: Device or None
        """
        # Try to get from Redis cache first
        if self.redis_handler:
            cache_key = f"device:{device_id}"
            cached_device = self.redis_handler.get_cache(cache_key)
            
            if cached_device and "id" in cached_device:
                # Check if we need full device details
                if len(cached_device) > 4:  # Has more than just basic fields
                    # Convert cached device to Device
                    return Device(**cached_device)
        
        # Get from database
        device = self.db.query(Device).filter(Device.id == device_id).first()
        
        if device and self.redis_handler:
            # Update cache with full device details
            cache_key = f"device:{device_id}"
            
            # Create a dict with device attributes
            device_dict = {
                "id": device.id,
                "user_id": device.user_id,
                "platform": device.platform,
                "device_identifier": device.device_identifier,
                "token": device.token,
                "app_version": device.app_version,
                "device_name": device.device_name,
                "os_version": device.os_version,
                "is_active": device.is_active,
                "created_at": device.created_at.isoformat() if device.created_at else None,
                "updated_at": device.updated_at.isoformat() if device.updated_at else None
            }
            
            self.redis_handler.set_cache(
                key=cache_key,
                value=device_dict,
                ttl=3600  # 1 hour cache
            )
        
        # If device has encrypted device_data, decrypt it
        if device and device.encrypted_metadata:
            try:
                decrypted_data = self.security_handler.decrypt_data(device.encrypted_metadata)
                device.encrypted_metadata = decrypted_data
            except Exception as e:
                logger.error(f"Error decrypting device data: {str(e)}")
                # Don't fail if decryption fails, just return the encrypted data
        
        return device
    
    def get_user_devices(self, user_id: str) -> List[Device]:
        """
        Get all devices for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List[Device]: List of devices
        """
        # Try to get device IDs from Redis cache first
        device_ids = []
        if self.redis_handler:
            user_devices_key = f"user_devices:{user_id}"
            device_ids = self.redis_handler.get_set_members(user_devices_key)
        
        if device_ids:
            # Get devices by IDs
            devices = []
            for device_id in device_ids:
                device = self.get_device_by_id(device_id)
                if device:
                    devices.append(device)
            
            return devices
        
        # Get from database if not in cache
        devices = self.db.query(Device).filter(
            Device.user_id == user_id
        ).all()
        
        # Cache user's device IDs in Redis
        if devices and self.redis_handler:
            user_devices_key = f"user_devices:{user_id}"
            device_ids = [device.id for device in devices]
            
            self.redis_handler.add_to_set(
                key=user_devices_key,
                values=device_ids
            )
            
            # Cache individual devices
            for device in devices:
                cache_key = f"device:{device.id}"
                
                # Create a dict with device attributes
                device_dict = {
                    "id": device.id,
                    "user_id": device.user_id,
                    "platform": device.platform,
                    "device_identifier": device.device_identifier,
                    "token": device.token,
                    "app_version": device.app_version,
                    "device_name": device.device_name,
                    "os_version": device.os_version,
                    "is_active": device.is_active,
                    "created_at": device.created_at.isoformat() if device.created_at else None,
                    "updated_at": device.updated_at.isoformat() if device.updated_at else None
                }
                
                self.redis_handler.set_cache(
                    key=cache_key,
                    value=device_dict,
                    ttl=3600  # 1 hour cache
                )
        
        # Decrypt device data for all devices
        for device in devices:
            if device.encrypted_metadata:
                try:
                    decrypted_data = self.security_handler.decrypt_data(device.encrypted_metadata)
                    device.encrypted_metadata = decrypted_data
                except Exception as e:
                    logger.error(f"Error decrypting device data: {str(e)}")
                    # Don't fail if decryption fails, just return the encrypted data
        
        return devices
    
    def get_active_user_devices(self, user_id: str) -> List[Device]:
        """
        Get active devices for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List[Device]: List of active devices
        """
        devices = self.get_user_devices(user_id)
        return [device for device in devices if device.is_active]
    
    def get_device_by_identifier(self, user_id: str, device_identifier: str) -> Optional[Device]:
        """
        Get a device by user ID and device identifier.
        
        Args:
            user_id: User ID
            device_identifier: Device identifier
            
        Returns:
            Device: Device or None
        """
        device = self.db.query(Device).filter(
            Device.user_id == user_id,
            Device.device_identifier == device_identifier
        ).first()
        
        # If device has encrypted device_data, decrypt it
        if device and device.encrypted_metadata:
            try:
                decrypted_data = self.security_handler.decrypt_data(device.encrypted_metadata)
                device.encrypted_metadata = decrypted_data
            except Exception as e:
                logger.error(f"Error decrypting device data: {str(e)}")
                # Don't fail if decryption fails, just return the encrypted data
        
        return device
