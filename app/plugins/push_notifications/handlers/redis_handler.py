"""
Redis Handler for Push Notifications

This module provides Redis integration for caching, rate limiting,
and real-time analytics for the push notifications plugin.
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Union
import asyncio
from datetime import datetime, timedelta
import hashlib

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

class RedisHandler:
    """
    Handler for Redis operations to enable high-performance caching,
    rate limiting, and real-time metrics for push notifications.
    """
    
    def __init__(self, redis_url: str, prefix: str = "push_notifications:"):
        """
        Initialize the Redis handler.
        
        Args:
            redis_url: Redis connection URL
            prefix: Prefix for all Redis keys
        """
        self.redis_url = redis_url
        self.prefix = prefix
        self.redis_client = None
        self.connect()
        logger.info("Redis handler initialized")
    
    def connect(self) -> bool:
        """
        Establish connection to Redis server.
        
        Returns:
            bool: Connection success status
        """
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis server")
            return True
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            return False
    
    def _get_key(self, key: str) -> str:
        """
        Generate a namespaced key with the prefix.
        
        Args:
            key: Base key
            
        Returns:
            str: Prefixed key
        """
        return f"{self.prefix}{key}"
    
    def set_cache(self, key: str, value: Any, expire: int = 3600) -> bool:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            expire: Expiration time in seconds
            
        Returns:
            bool: Success status
        """
        try:
            serialized_value = json.dumps(value) if not isinstance(value, str) else value
            full_key = self._get_key(key)
            self.redis_client.set(full_key, serialized_value, ex=expire)
            return True
        except (RedisError, TypeError) as e:
            logger.error(f"Error setting cache for {key}: {str(e)}")
            return False
    
    def get_cache(self, key: str) -> Any:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Any: Cached value or None if not found
        """
        try:
            full_key = self._get_key(key)
            value = self.redis_client.get(full_key)
            
            if value is None:
                return None
                
            try:
                # Try to parse as JSON
                return json.loads(value)
            except json.JSONDecodeError:
                # If not JSON, return as string
                return value
                
        except RedisError as e:
            logger.error(f"Error getting cache for {key}: {str(e)}")
            return None
    
    def delete_cache(self, key: str) -> bool:
        """
        Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: Success status
        """
        try:
            full_key = self._get_key(key)
            self.redis_client.delete(full_key)
            return True
        except RedisError as e:
            logger.error(f"Error deleting cache for {key}: {str(e)}")
            return False
    
    def check_rate_limit(self, key: str, limit: int, period: int) -> bool:
        """
        Check if a rate limit has been exceeded.
        
        Args:
            key: Rate limit key
            limit: Maximum number of operations
            period: Time period in seconds
            
        Returns:
            bool: True if limit is not exceeded, False otherwise
        """
        try:
            full_key = self._get_key(f"rate_limit:{key}")
            
            # Increment counter
            current = self.redis_client.incr(full_key)
            
            # Set expiration if it's a new key
            if current == 1:
                self.redis_client.expire(full_key, period)
            
            # Check if limit is exceeded
            return current <= limit
            
        except RedisError as e:
            logger.error(f"Error checking rate limit for {key}: {str(e)}")
            # Default to allowing the operation on error
            return True
    
    def store_device_token(self, user_id: str, device_id: str, platform: str,
                         token: str, expire_days: int = 90) -> bool:
        """
        Store a device token in Redis for quick access.
        
        Args:
            user_id: User ID
            device_id: Device ID
            platform: Device platform
            token: Device token
            expire_days: Token expiration in days
            
        Returns:
            bool: Success status
        """
        try:
            # Store token by device ID
            device_key = self._get_key(f"device:{device_id}")
            device_data = {
                "user_id": user_id,
                "device_id": device_id,
                "platform": platform,
                "token": token,
                "updated_at": datetime.utcnow().isoformat()
            }
            self.redis_client.set(device_key, json.dumps(device_data), 
                               ex=expire_days * 86400)
            
            # Add device to user's device set
            user_devices_key = self._get_key(f"user_devices:{user_id}")
            self.redis_client.sadd(user_devices_key, device_id)
            
            # Add device to platform set for analytics
            platform_devices_key = self._get_key(f"platform_devices:{platform}")
            self.redis_client.sadd(platform_devices_key, device_id)
            
            return True
            
        except RedisError as e:
            logger.error(f"Error storing device token: {str(e)}")
            return False
    
    def get_user_device_tokens(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all device tokens for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List: List of device data dictionaries
        """
        try:
            # Get the set of user's device IDs
            user_devices_key = self._get_key(f"user_devices:{user_id}")
            device_ids = self.redis_client.smembers(user_devices_key)
            
            if not device_ids:
                return []
            
            # Get device data for each device ID
            devices = []
            for device_id in device_ids:
                device_key = self._get_key(f"device:{device_id}")
                device_data_str = self.redis_client.get(device_key)
                
                if device_data_str:
                    try:
                        device_data = json.loads(device_data_str)
                        devices.append(device_data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid device data format for {device_id}")
            
            return devices
            
        except RedisError as e:
            logger.error(f"Error getting user device tokens: {str(e)}")
            return []
    
    def remove_device_token(self, device_id: str, user_id: Optional[str] = None) -> bool:
        """
        Remove a device token from Redis.
        
        Args:
            device_id: Device ID
            user_id: User ID (optional, for verification)
            
        Returns:
            bool: Success status
        """
        try:
            # Get device data first to check user_id if provided
            device_key = self._get_key(f"device:{device_id}")
            device_data_str = self.redis_client.get(device_key)
            
            if not device_data_str:
                logger.warning(f"Device {device_id} not found")
                return False
            
            try:
                device_data = json.loads(device_data_str)
            except json.JSONDecodeError:
                logger.warning(f"Invalid device data format for {device_id}")
                return False
            
            # If user_id is provided, verify it matches
            if user_id and device_data.get("user_id") != user_id:
                logger.warning(f"User ID mismatch for device {device_id}")
                return False
            
            # Remove device data
            self.redis_client.delete(device_key)
            
            # Remove from user's device set
            user_devices_key = self._get_key(f"user_devices:{device_data.get('user_id')}")
            self.redis_client.srem(user_devices_key, device_id)
            
            # Remove from platform set
            platform = device_data.get("platform")
            if platform:
                platform_devices_key = self._get_key(f"platform_devices:{platform}")
                self.redis_client.srem(platform_devices_key, device_id)
            
            return True
            
        except RedisError as e:
            logger.error(f"Error removing device token: {str(e)}")
            return False
    
    def increment_metric(self, metric: str, tags: Dict[str, str] = None,
                      value: int = 1, expire: int = 86400) -> bool:
        """
        Increment a metric counter in Redis.
        
        Args:
            metric: Metric name
            tags: Dictionary of tag keys and values
            value: Value to increment by
            expire: Expiration time in seconds
            
        Returns:
            bool: Success status
        """
        try:
            # Generate a unique key for the metric with tags
            key_parts = [metric]
            if tags:
                for tag_key, tag_value in sorted(tags.items()):
                    key_parts.append(f"{tag_key}:{tag_value}")
            
            metric_key = self._get_key(f"metrics:{':'.join(key_parts)}")
            
            # Get the current timestamp for time-based metrics
            now = datetime.utcnow()
            day_str = now.strftime("%Y-%m-%d")
            hour_str = now.strftime("%Y-%m-%d:%H")
            
            # Increment daily counter
            daily_key = f"{metric_key}:day:{day_str}"
            self.redis_client.incrby(daily_key, value)
            self.redis_client.expire(daily_key, 30 * 86400)  # 30 days
            
            # Increment hourly counter
            hourly_key = f"{metric_key}:hour:{hour_str}"
            self.redis_client.incrby(hourly_key, value)
            self.redis_client.expire(hourly_key, 7 * 86400)  # 7 days
            
            # Increment total counter
            total_key = f"{metric_key}:total"
            self.redis_client.incrby(total_key, value)
            
            return True
            
        except RedisError as e:
            logger.error(f"Error incrementing metric {metric}: {str(e)}")
            return False
    
    def get_metrics(self, metric: str, tags: Dict[str, str] = None,
                 interval: str = "day", start_time: datetime = None,
                 end_time: datetime = None) -> Dict[str, int]:
        """
        Get metric values for a time range.
        
        Args:
            metric: Metric name
            tags: Dictionary of tag keys and values
            interval: Time interval ('hour', 'day')
            start_time: Start time for range
            end_time: End time for range
            
        Returns:
            Dict: Dictionary of timestamps and values
        """
        try:
            # Generate a unique key for the metric with tags
            key_parts = [metric]
            if tags:
                for tag_key, tag_value in sorted(tags.items()):
                    key_parts.append(f"{tag_key}:{tag_value}")
            
            metric_key = self._get_key(f"metrics:{':'.join(key_parts)}")
            
            # Set default time range if not provided
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                if interval == "hour":
                    start_time = end_time - timedelta(days=2)  # 48 hours
                else:
                    start_time = end_time - timedelta(days=30)  # 30 days
            
            # Generate pattern for keys to scan
            pattern = f"{metric_key}:{interval}:*"
            
            # Scan for matching keys
            result = {}
            cursor = 0
            while True:
                cursor, keys = self.redis_client.scan(cursor, pattern, 100)
                
                # Filter keys by time range
                for key in keys:
                    # Extract timestamp from key
                    key_parts = key.split(":")
                    timestamp_str = key_parts[-1]
                    if interval == "hour":
                        timestamp_str = f"{timestamp_str}:00:00"
                    else:
                        timestamp_str = f"{timestamp_str} 00:00:00"
                    
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        
                        # Check if in range
                        if start_time <= timestamp <= end_time:
                            value = int(self.redis_client.get(key) or 0)
                            result[timestamp.isoformat()] = value
                    except ValueError:
                        continue
                
                if cursor == 0:
                    break
            
            return result
            
        except RedisError as e:
            logger.error(f"Error getting metrics for {metric}: {str(e)}")
            return {}
    
    def cache_notification_template(self, template_id: str, template_data: Dict[str, Any]) -> bool:
        """
        Cache a notification template for quick access.
        
        Args:
            template_id: Template ID
            template_data: Template data
            
        Returns:
            bool: Success status
        """
        template_key = self._get_key(f"template:{template_id}")
        return self.set_cache(template_key, template_data, expire=86400)  # 24 hours
    
    def get_notification_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached notification template.
        
        Args:
            template_id: Template ID
            
        Returns:
            Dict: Template data or None if not found
        """
        template_key = self._get_key(f"template:{template_id}")
        return self.get_cache(template_key)
    
    def schedule_notification(self, notification_id: str, scheduled_time: datetime,
                           payload: Dict[str, Any]) -> bool:
        """
        Schedule a notification for future delivery using Redis sorted sets.
        
        Args:
            notification_id: Notification ID
            scheduled_time: When to deliver the notification
            payload: Notification payload
            
        Returns:
            bool: Success status
        """
        try:
            # Store the payload
            payload_key = self._get_key(f"scheduled:{notification_id}")
            self.set_cache(payload_key, payload, expire=86400 * 7)  # 7 days
            
            # Add to the scheduled set with timestamp score
            scheduled_set = self._get_key("scheduled_notifications")
            score = int(scheduled_time.timestamp())
            self.redis_client.zadd(scheduled_set, {notification_id: score})
            
            return True
            
        except RedisError as e:
            logger.error(f"Error scheduling notification: {str(e)}")
            return False
    
    def get_due_notifications(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get notifications that are due for delivery.
        
        Args:
            limit: Maximum number of notifications to retrieve
            
        Returns:
            List: List of notification payloads
        """
        try:
            scheduled_set = self._get_key("scheduled_notifications")
            now = int(time.time())
            
            # Get IDs of due notifications
            due_ids = self.redis_client.zrangebyscore(scheduled_set, 0, now, start=0, num=limit)
            
            # Get payloads
            notifications = []
            for notification_id in due_ids:
                payload_key = self._get_key(f"scheduled:{notification_id}")
                payload = self.get_cache(payload_key)
                
                if payload:
                    payload["id"] = notification_id
                    notifications.append(payload)
                
                # Remove from scheduled set
                self.redis_client.zrem(scheduled_set, notification_id)
                
                # Delete payload
                self.delete_cache(payload_key)
            
            return notifications
            
        except RedisError as e:
            logger.error(f"Error getting due notifications: {str(e)}")
            return []
    
    def cancel_scheduled_notification(self, notification_id: str) -> bool:
        """
        Cancel a scheduled notification.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            bool: Success status
        """
        try:
            # Remove from scheduled set
            scheduled_set = self._get_key("scheduled_notifications")
            removed = self.redis_client.zrem(scheduled_set, notification_id)
            
            # Delete payload
            payload_key = self._get_key(f"scheduled:{notification_id}")
            self.delete_cache(payload_key)
            
            return removed > 0
            
        except RedisError as e:
            logger.error(f"Error canceling scheduled notification: {str(e)}")
            return False
