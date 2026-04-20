"""
Rate Limiting model for the API Gateway plugin.

Provides functionality to track and enforce rate limits on API requests
to prevent abuse and ensure fair resource usage.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, func, and_
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

from app.core.db import Base

# Setup logging
logger = logging.getLogger(__name__)

class RateLimitDB(Base):
    """Rate limit tracking database model."""
    
    __tablename__ = "api_gateway_rate_limits"
    
    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), ForeignKey("api_gateway_keys.id", ondelete="CASCADE"), nullable=False)
    
    # Tracking information
    path_pattern = Column(String(255), nullable=False, index=True)
    window_size = Column(String(20), nullable=False, index=True)  # 'minute', 'hour', 'day'
    window_start = Column(DateTime, nullable=False, index=True)
    window_end = Column(DateTime, nullable=False)
    
    # Usage counters
    request_count = Column(Integer, nullable=False, default=0)
    
    # Relationships
    api_key = relationship("ApiKeyDB", back_populates="rate_limits")
    
    @classmethod
    def track_request(
        cls,
        db_session,
        api_key_id: str,
        path_pattern: str
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Track an API request and check if it exceeds rate limits.
        
        This method tracks the request count within the current time windows (minute, hour, day)
        and returns whether any limits have been exceeded.
        
        Args:
            db_session: SQLAlchemy database session
            api_key_id: API key ID
            path_pattern: The path pattern this request matches
            
        Returns:
            Tuple of (overall_allowed, {window: is_exceeded})
        """
        now = datetime.utcnow()
        
        # Get API key to check the configured limits
        api_key = db_session.query("ApiKeyDB").filter_by(id=api_key_id).first()
        if not api_key:
            return False, {"error": "API key not found"}
        
        # Track request for different time windows
        window_exceeded = {}
        
        # Check minute limit
        if api_key.rate_limit_per_minute:
            minute_start = datetime(now.year, now.month, now.day, now.hour, now.minute)
            minute_end = minute_start + timedelta(minutes=1)
            
            minute_exceeded = cls._track_window_request(
                db_session, 
                api_key_id, 
                path_pattern, 
                "minute", 
                minute_start, 
                minute_end, 
                api_key.rate_limit_per_minute
            )
            window_exceeded["minute"] = minute_exceeded
        
        # Check hour limit
        if api_key.rate_limit_per_hour:
            hour_start = datetime(now.year, now.month, now.day, now.hour)
            hour_end = hour_start + timedelta(hours=1)
            
            hour_exceeded = cls._track_window_request(
                db_session, 
                api_key_id, 
                path_pattern, 
                "hour", 
                hour_start, 
                hour_end, 
                api_key.rate_limit_per_hour
            )
            window_exceeded["hour"] = hour_exceeded
        
        # Check day limit
        if api_key.rate_limit_per_day:
            day_start = datetime(now.year, now.month, now.day)
            day_end = day_start + timedelta(days=1)
            
            day_exceeded = cls._track_window_request(
                db_session, 
                api_key_id, 
                path_pattern, 
                "day", 
                day_start, 
                day_end, 
                api_key.rate_limit_per_day
            )
            window_exceeded["day"] = day_exceeded
        
        # Overall allowed only if all windows are not exceeded
        overall_allowed = not any(window_exceeded.values())
        
        # Log rate limit violations
        if not overall_allowed:
            exceeded_windows = [w for w, v in window_exceeded.items() if v]
            logger.warning(
                f"Rate limit exceeded for API key {api_key.prefix} on path {path_pattern}. "
                f"Exceeded windows: {', '.join(exceeded_windows)}",
                extra={
                    "api_key_id": api_key_id,
                    "path_pattern": path_pattern,
                    "exceeded_windows": exceeded_windows
                }
            )
            
            # Update API key's usage statistics
            api_key.use_count += 1
            api_key.last_used_at = now
            db_session.add(api_key)
        
        return overall_allowed, window_exceeded
    
    @classmethod
    def _track_window_request(
        cls,
        db_session,
        api_key_id: str,
        path_pattern: str,
        window_size: str,
        window_start: datetime,
        window_end: datetime,
        limit: int
    ) -> bool:
        """
        Track a request within a specific time window.
        
        Args:
            db_session: SQLAlchemy database session
            api_key_id: API key ID
            path_pattern: Path pattern
            window_size: Size of the window ('minute', 'hour', 'day')
            window_start: Start of the time window
            window_end: End of the time window
            limit: Maximum allowed requests in this window
            
        Returns:
            True if the limit is exceeded, False otherwise
        """
        # Try to find an existing rate limit entry for this window
        rate_limit = db_session.query(cls).filter(
            cls.api_key_id == api_key_id,
            cls.path_pattern == path_pattern,
            cls.window_size == window_size,
            cls.window_start == window_start
        ).first()
        
        if rate_limit:
            # Increment the counter
            rate_limit.request_count += 1
            db_session.add(rate_limit)
            
            # Check if limit is exceeded
            return rate_limit.request_count > limit
        else:
            # Create a new entry
            new_rate_limit = cls(
                api_key_id=api_key_id,
                path_pattern=path_pattern,
                window_size=window_size,
                window_start=window_start,
                window_end=window_end,
                request_count=1
            )
            db_session.add(new_rate_limit)
            
            # First request, not exceeded
            return False
    
    @classmethod
    def clean_expired_windows(cls, db_session) -> int:
        """
        Clean up expired rate limit windows.
        
        Args:
            db_session: SQLAlchemy database session
            
        Returns:
            Number of records deleted
        """
        now = datetime.utcnow()
        
        # Delete expired windows
        result = db_session.query(cls).filter(
            cls.window_end < now
        ).delete()
        
        return result


# Pydantic models for rate limiting
class RateLimitInfo(BaseModel):
    """Rate limit information model."""
    
    window: str
    limit: int
    remaining: int
    reset: datetime
    
    class Config:
        from_attributes = True


class RateLimitResponse(BaseModel):
    """Rate limit response model."""
    
    limits: List[RateLimitInfo]
    
    class Config:
        from_attributes = True
