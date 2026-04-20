"""
Pydantic schemas for user analytics plugin.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

class DeviceInfo(BaseModel):
    """Information about the user's device"""
    os: Optional[str] = None
    browser: Optional[str] = None
    device_type: Optional[str] = None
    screen_resolution: Optional[str] = None

class SessionCreate(BaseModel):
    """Schema for creating a new analytics session"""
    user_id: Optional[str] = None
    device_info: Optional[DeviceInfo] = None
    referrer: Optional[str] = None
    
class SessionResponse(BaseModel):
    """Response after creating a session"""
    id: str
    session_token: str
    created_at: datetime
    
    class Config:
        orm_mode = True

class EventCreate(BaseModel):
    """Schema for creating a new user event"""
    session_token: str
    event_type: str
    target_type: str
    target_id: Optional[str] = None
    target_path: Optional[str] = None
    component_name: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None  # Maps to event_metadata in the model
    
    # For heatmaps
    x_position: Optional[float] = None
    y_position: Optional[float] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None

class EventResponse(BaseModel):
    """Response after recording an event"""
    id: str
    received_at: datetime
    
    class Config:
        orm_mode = True

class HeatmapFilter(BaseModel):
    """Filter criteria for generating heatmaps"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page_path: Optional[str] = None
    component_name: Optional[str] = None
    event_type: Optional[str] = Field(None, description="click, hover, view, etc.")
    user_id: Optional[str] = None
    
class UserJourneyFilter(BaseModel):
    """Filter criteria for retrieving user journeys"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: Optional[int] = 10
