"""
Pydantic schemas for the PWA Support plugin
"""
from pydantic import BaseModel, HttpUrl, Field, validator
from typing import List, Dict, Optional, Any, Union, Set
from datetime import datetime


class IconSchema(BaseModel):
    """Schema for PWA manifest icons"""
    src: str
    sizes: str
    type: str = "image/png"
    purpose: Optional[str] = None


class PWAManifestSchema(BaseModel):
    """Schema for PWA manifest.json"""
    name: str
    short_name: str
    start_url: str = "/"
    display: str = "standalone"
    background_color: str = "#4F46E5"
    theme_color: str = "#4F46E5"
    description: Optional[str] = None
    icons: List[IconSchema]
    orientation: Optional[str] = None
    scope: Optional[str] = None
    screenshots: Optional[List[Dict[str, str]]] = None
    categories: Optional[List[str]] = None
    shortcuts: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Kaapi App",
                "short_name": "Kaapi",
                "description": "Your Kaapi application",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#4F46E5",
                "theme_color": "#4F46E5",
                "icons": [
                    {
                        "src": "/static/icons/icon-192x192.png",
                        "sizes": "192x192",
                        "type": "image/png"
                    },
                    {
                        "src": "/static/icons/icon-512x512.png",
                        "sizes": "512x512",
                        "type": "image/png"
                    }
                ]
            }
        }


class ServiceWorkerConfigSchema(BaseModel):
    """Schema for service worker configuration"""
    cache_version: str = "v1"
    cache_name: str = "kaapi-pwa-cache"
    urls_to_cache: List[str]
    offline_fallback: str = "/offline.html"
    dynamic_cache_enabled: bool = True
    cache_strategies: Optional[Dict[str, str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "cache_version": "v1",
                "cache_name": "kaapi-pwa-cache",
                "urls_to_cache": [
                    "/",
                    "/static/css/main.css",
                    "/static/js/main.js",
                    "/offline.html"
                ],
                "offline_fallback": "/offline.html",
                "dynamic_cache_enabled": True,
                "cache_strategies": {
                    "images": "cache-first",
                    "api": "network-first",
                    "static": "cache-first"
                }
            }
        }


class PushSubscriptionKeys(BaseModel):
    """Schema for push subscription keys"""
    p256dh: str
    auth: str


class PushSubscriptionSchema(BaseModel):
    """Schema for Web Push subscription"""
    endpoint: str
    expirationTime: Optional[Union[int, None]] = None
    keys: PushSubscriptionKeys


class PushNotificationSchema(BaseModel):
    """Schema for push notification payload"""
    title: str
    message: str
    icon: Optional[str] = "/static/icons/icon-192x192.png"
    badge: Optional[str] = None
    tag: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, str]]] = None


# New schemas for segmented notifications

class SegmentCriteriaSchema(BaseModel):
    """Schema for segment criteria definition"""
    device_types: Optional[List[str]] = None  # List of device types e.g. ["mobile", "desktop"]
    languages: Optional[List[str]] = None  # List of language codes e.g. ["en", "fr"]
    locations: Optional[List[str]] = None  # List of locations e.g. ["Paris", "New York"]
    tags: Optional[List[str]] = None  # List of tags for custom segmentation
    user_role_ids: Optional[List[int]] = None  # List of user role IDs to include
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_types": ["mobile", "tablet"],
                "languages": ["en", "fr"],
                "locations": ["Paris", "London"],
                "tags": ["premium", "early_adopter"],
                "user_role_ids": [1, 2]
            }
        }


class NotificationSegmentCreate(BaseModel):
    """Schema for creating a new notification segment"""
    name: str
    description: Optional[str] = None
    criteria: Optional[SegmentCriteriaSchema] = None
    is_dynamic: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Premium Mobile Users",
                "description": "Mobile users with premium subscription",
                "criteria": {
                    "device_types": ["mobile", "tablet"],
                    "tags": ["premium"]
                },
                "is_dynamic": True
            }
        }


class NotificationSegmentUpdate(BaseModel):
    """Schema for updating an existing notification segment"""
    name: Optional[str] = None
    description: Optional[str] = None
    criteria: Optional[SegmentCriteriaSchema] = None
    is_dynamic: Optional[bool] = None


class NotificationSegmentRead(BaseModel):
    """Schema for reading notification segment data"""
    id: int
    name: str
    description: Optional[str] = None
    criteria: Optional[SegmentCriteriaSchema] = None
    is_dynamic: bool
    created_at: datetime
    updated_at: datetime
    subscription_count: int
    
    class Config:
        from_attributes = True


class SegmentSubscriptionAssignment(BaseModel):
    """Schema for assigning subscriptions to segments"""
    segment_id: int
    subscription_ids: List[int]


class SegmentedNotificationSend(BaseModel):
    """Schema for sending a notification to a specific segment"""
    segment_id: int
    title: str
    message: str
    icon: Optional[str] = "/static/icons/icon-192x192.png"
    url: Optional[str] = None
    badge: Optional[str] = None
    tag: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, str]]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "segment_id": 1,
                "title": "Special Offer for Premium Users",
                "message": "Enjoy 20% off on your next purchase!",
                "icon": "/static/icons/special-offer.png",
                "url": "/offers/premium",
                "data": {
                    "offer_id": "PREMIUM20"
                }
            }
        }


class NotificationHistoryRead(BaseModel):
    """Schema for reading notification history"""
    id: int
    title: str
    message: str
    icon: Optional[str] = None
    url: Optional[str] = None
    segment_id: Optional[int] = None
    segment_name: Optional[str] = None
    sent_at: datetime
    sent_count: int
    
    class Config:
        from_attributes = True


class NotificationStatistics(BaseModel):
    """Schema for notification delivery statistics"""
    total_sent: int
    delivered: int
    clicked: int
    failed: int
    delivery_rate: float
    click_rate: float
