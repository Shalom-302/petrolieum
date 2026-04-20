"""
Push Notifications Device Schemas

This module defines the Pydantic schemas for device registration and management,
implementing request validation as part of the standardized security approach.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re


class DeviceBase(BaseModel):
    """Base schema for device data."""
    platform: str = Field(..., description="Device platform (android, ios, web)")
    token: str = Field(..., description="Device push notification token")
    app_version: Optional[str] = Field(None, description="Version of the app")
    device_name: Optional[str] = Field(None, description="Name of the device")
    device_model: Optional[str] = Field(None, description="Model of the device")
    os_version: Optional[str] = Field(None, description="Operating system version")
    language: Optional[str] = Field(None, description="Device language code")
    timezone: Optional[str] = Field(None, description="Device timezone")
    device_data: Optional[Dict[str, Any]] = Field(None, description="Additional device metadata")
    segmentation_data: Optional[Dict[str, Any]] = Field(None, description="Metadata for device segmentation")
    
    @validator('platform')
    def validate_platform(cls, v):
        """Validate platform value."""
        allowed_platforms = ['android', 'ios', 'web']
        if v.lower() not in allowed_platforms:
            raise ValueError(f"Platform must be one of: {', '.join(allowed_platforms)}")
        return v.lower()
    
    @validator('token')
    def validate_token(cls, v):
        """Validate push token format."""
        if not v or len(v) < 8:
            raise ValueError("Token must be a valid push notification token")
        return v
    
    @validator('language')
    def validate_language(cls, v):
        """Validate language code format."""
        if v and not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
            raise ValueError("Language must be in format 'xx' or 'xx-XX'")
        return v
    
    @validator('device_data')
    def validate_device_data(cls, v):
        """Validate device data doesn't contain sensitive information."""
        if v:
            # Check for sensitive keys
            sensitive_keys = ['password', 'token', 'secret', 'credential', 'auth',
                           'private', 'key', 'certificate']
            for key in v.keys():
                if any(s in key.lower() for s in sensitive_keys):
                    raise ValueError(f"Device data contains sensitive key: {key}")
        return v


class DeviceCreate(DeviceBase):
    """Schema for creating a new device registration."""
    pass


class DeviceUpdate(BaseModel):
    """Schema for updating a device registration."""
    token: Optional[str] = Field(None, description="Device push notification token")
    app_version: Optional[str] = Field(None, description="Version of the app")
    device_name: Optional[str] = Field(None, description="Name of the device")
    os_version: Optional[str] = Field(None, description="Operating system version")
    language: Optional[str] = Field(None, description="Device language code")
    timezone: Optional[str] = Field(None, description="Device timezone")
    is_active: Optional[bool] = Field(None, description="Whether the device is active")
    device_data: Optional[Dict[str, Any]] = Field(None, description="Additional device metadata")
    segmentation_data: Optional[Dict[str, Any]] = Field(None, description="Metadata for device segmentation")
    
    @validator('token')
    def validate_token(cls, v):
        """Validate push token format if provided."""
        if v and (not v or len(v) < 8):
            raise ValueError("Token must be a valid push notification token")
        return v
    
    @validator('device_data')
    def validate_device_data(cls, v):
        """Validate device data doesn't contain sensitive information."""
        if v:
            # Check for sensitive keys
            sensitive_keys = ['password', 'token', 'secret', 'credential', 'auth',
                           'private', 'key', 'certificate']
            for key in v.keys():
                if any(s in key.lower() for s in sensitive_keys):
                    raise ValueError(f"Device data contains sensitive key: {key}")
        return v


class DeviceInDB(DeviceBase):
    """Schema for device information from database."""
    id: str
    user_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DeviceResponse(BaseModel):
    """Response schema for device information."""
    id: str
    platform: str
    device_name: Optional[str] = None
    device_model: Optional[str] = None
    app_version: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserDevicesResponse(BaseModel):
    """Response schema for listing a user's devices."""
    user_id: str
    devices: List[DeviceResponse]
    total: int
    
    class Config:
        from_attributes = True


class DeviceDeactivateRequest(BaseModel):
    """Request schema for deactivating a device."""
    device_id: str = Field(..., description="ID of the device to deactivate")

    @validator('device_id')
    def validate_device_id(cls, v):
        """Validate device ID format."""
        if not v or not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', v):
            raise ValueError("Invalid device ID format")
        return v
