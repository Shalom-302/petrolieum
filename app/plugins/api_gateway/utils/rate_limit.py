"""
Rate limiting utilities for the API Gateway plugin.

This module provides functions and decorators for rate limiting API endpoints.
"""

import logging
import time
from typing import Dict, Any, Callable, Optional, Union, cast
import functools
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from ..models.rate_limit import RateLimitDB

logger = logging.getLogger(__name__)

# In-memory cache for rate limiting
# Structure: {client_ip: {endpoint: {window: [list of timestamps]}}}
RATE_LIMIT_CACHE = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

def parse_rate_limit(rate_limit_str: str) -> Dict[str, int]:
    """
    Parse a rate limit string into a dictionary of time windows and limits.
    
    Args:
        rate_limit_str: Rate limit string (e.g., "100/minute", "1000/day")
        
    Returns:
        Dict mapping time windows to their limits
    """
    result = {}
    
    if not rate_limit_str:
        return result
        
    try:
        parts = rate_limit_str.split(",")
        for part in parts:
            limit, period = part.strip().split("/")
            limit = int(limit)
            
            # Normalize period names
            if period.lower() in ["minute", "min", "m"]:
                result["minute"] = limit
            elif period.lower() in ["hour", "hr", "h"]:
                result["hour"] = limit
            elif period.lower() in ["day", "d"]:
                result["day"] = limit
            else:
                logger.warning(f"Unknown rate limit period: {period}, using as per minute")
                result["minute"] = limit
    except Exception as e:
        logger.error(f"Error parsing rate limit '{rate_limit_str}': {str(e)}")
        
    return result

def _clean_expired_timestamps(timestamps: list, window_seconds: int) -> list:
    """Remove expired timestamps based on the time window."""
    now = time.time()
    return [ts for ts in timestamps if now - ts <= window_seconds]

def rate_limit(
    limit_per_minute: Optional[int] = None,
    limit_per_hour: Optional[int] = None, 
    limit_per_day: Optional[int] = None,
    key_func: Callable = None
) -> Callable:
    """
    Rate limiting decorator for FastAPI endpoints.
    
    Args:
        limit_per_minute: Maximum requests per minute
        limit_per_hour: Maximum requests per hour
        limit_per_day: Maximum requests per day
        key_func: Function to extract the client key (defaults to client IP)
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
                    
            if not request:
                for arg_name, arg_value in kwargs.items():
                    if isinstance(arg_value, Request):
                        request = arg_value
                        break
            
            if not request:
                logger.warning(f"Rate limit applied but no request object found for {func.__name__}")
                return await func(*args, **kwargs)
                
            # Get client identifier (default to IP address)
            if key_func:
                client_id = key_func(request)
            else:
                client_id = request.client.host
                
            endpoint = f"{request.method}:{request.url.path}"
            now = time.time()
            
            # Check minute limit
            if limit_per_minute:
                window = "minute"
                window_seconds = 60
                timestamps = RATE_LIMIT_CACHE[client_id][endpoint][window]
                timestamps = _clean_expired_timestamps(timestamps, window_seconds)
                
                if len(timestamps) >= limit_per_minute:
                    retry_after = int(timestamps[0] + window_seconds - now) + 1
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                        headers={"Retry-After": str(retry_after)}
                    )
                    
                timestamps.append(now)
                RATE_LIMIT_CACHE[client_id][endpoint][window] = timestamps
                
            # Check hour limit
            if limit_per_hour:
                window = "hour"
                window_seconds = 3600
                timestamps = RATE_LIMIT_CACHE[client_id][endpoint][window]
                timestamps = _clean_expired_timestamps(timestamps, window_seconds)
                
                if len(timestamps) >= limit_per_hour:
                    retry_after = int(timestamps[0] + window_seconds - now) + 1
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                        headers={"Retry-After": str(retry_after)}
                    )
                    
                timestamps.append(now)
                RATE_LIMIT_CACHE[client_id][endpoint][window] = timestamps
                
            # Check day limit
            if limit_per_day:
                window = "day"
                window_seconds = 86400
                timestamps = RATE_LIMIT_CACHE[client_id][endpoint][window]
                timestamps = _clean_expired_timestamps(timestamps, window_seconds)
                
                if len(timestamps) >= limit_per_day:
                    retry_after = int(timestamps[0] + window_seconds - now) + 1
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                        headers={"Retry-After": str(retry_after)}
                    )
                    
                timestamps.append(now)
                RATE_LIMIT_CACHE[client_id][endpoint][window] = timestamps
                
            # Call the original function
            return await func(*args, **kwargs)
            
        return wrapper
        
    return decorator

def rate_limit_by_key(
    rate_limit_str: str, 
    key_func: Callable = None,
    db: Session = Depends(get_db)
) -> Callable:
    """
    More advanced rate limiting that can use database storage.
    
    Args:
        rate_limit_str: Rate limit string (e.g., "100/minute,1000/day")
        key_func: Function to extract the client key
        db: Database session
        
    Returns:
        Decorator function
    """
    limits = parse_rate_limit(rate_limit_str)
    
    return rate_limit(
        limit_per_minute=limits.get("minute"),
        limit_per_hour=limits.get("hour"),
        limit_per_day=limits.get("day"),
        key_func=key_func
    )
