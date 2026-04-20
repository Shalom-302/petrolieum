"""
Database models for user analytics plugin.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base
from uuid import uuid4

class AnalyticsUserSession(Base):
    """Represents a unique user session for analytics tracking"""
    __tablename__ = "user_analytics_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, nullable=True)  # Can be null for anonymous sessions
    session_start = Column(DateTime, default=func.now())
    session_end = Column(DateTime, nullable=True)
    device_info = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    referrer = Column(String, nullable=True)
    is_anonymized = Column(Boolean, default=False)
    
    # Relationship with events
    events = relationship("AnalyticsUserEvent", back_populates="session", cascade="all, delete-orphan")

class AnalyticsUserEvent(Base):
    """Represents a single event in the user journey"""
    __tablename__ = "user_analytics_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("user_analytics_sessions.id", ondelete="CASCADE"))
    event_type = Column(String, nullable=False)  # click, view, hover, etc.
    target_type = Column(String, nullable=False)  # button, page, link, etc.
    target_id = Column(String, nullable=True)    # ID of the target element
    target_path = Column(String, nullable=True)  # DOM path or route
    component_name = Column(String, nullable=True) # UI component name
    timestamp = Column(DateTime, default=func.now())
    duration_ms = Column(Integer, nullable=True)  # Duration of interaction if applicable
    event_metadata = Column(JSON, nullable=True)  # Additional data
    
    # For heatmaps
    x_position = Column(Float, nullable=True)     # Relative X position (0-1)
    y_position = Column(Float, nullable=True)     # Relative Y position (0-1)
    screen_width = Column(Integer, nullable=True)
    screen_height = Column(Integer, nullable=True)
    
    # Relationships
    session = relationship("AnalyticsUserSession", back_populates="events")
