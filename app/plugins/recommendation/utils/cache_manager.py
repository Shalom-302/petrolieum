"""
Cache Manager

This module implements caching functionality for recommendations to improve
performance and reduce database load.
"""
import logging
import json
import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Get plugin instance to access encryption handler
from ..main import recommendation_plugin


class RecommendationCache:
    """
    Cache handler for recommendation results, following standardized security
    approach for managing sensitive data.
    """
    
    def __init__(self, ttl: int = 3600):
        """
        Initialize cache with specified TTL.
        
        Args:
            ttl: Time-to-live in seconds for cached items
        """
        self._cache = {}
        self.ttl = ttl
        self.security_handler = recommendation_plugin.security_handler
    
    def _generate_cache_key(self, user_id: str, params: Dict[str, Any]) -> str:
        """
        Generate a secure cache key from user ID and request parameters.
        
        Args:
            user_id: User identifier
            params: Request parameters
            
        Returns:
            Cache key string
        """
        # Create a standardized cache key format
        key_data = {
            "user_id": user_id,
            "params": params,
            "timestamp": int(time.time() / (self.ttl / 2))  # Include time bucket in key
        }
        
        # Securely hash the key data
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(self, user_id: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve recommendations from cache if available and not expired.
        
        Args:
            user_id: User identifier
            params: Request parameters
            
        Returns:
            Cached recommendations or None if not found/expired
        """
        cache_key = self._generate_cache_key(user_id, params)
        
        # Check if key exists and not expired
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            
            # Check if entry has expired
            if entry["expires_at"] < datetime.now():
                # Remove expired entry
                del self._cache[cache_key]
                return None
                
            # Log cache hit using standardized security approach
            self.security_handler.secure_log(
                "Recommendation cache hit",
                {
                    "user_id": user_id,
                    "algorithm": params.get("algorithm", "unknown"),
                    "cache_key": cache_key[:8] + "..."  # Only log part of the key
                }
            )
            
            # Decrypt the stored recommendations using standardized security approach
            return self.security_handler.decrypt_recommendation_data(entry["data"])
        
        return None
    
    def set(self, user_id: str, params: Dict[str, Any], 
            recommendations: List[Dict[str, Any]]) -> None:
        """
        Store recommendations in cache.
        
        Args:
            user_id: User identifier
            params: Request parameters
            recommendations: Recommendation data to cache
        """
        cache_key = self._generate_cache_key(user_id, params)
        
        # Encrypt the recommendations using standardized security approach
        encrypted_data = self.security_handler.encrypt_recommendation_data(recommendations)
        
        # Store in cache with expiration
        self._cache[cache_key] = {
            "data": encrypted_data,
            "expires_at": datetime.now() + timedelta(seconds=self.ttl)
        }
        
        # Log cache set using standardized security approach
        self.security_handler.secure_log(
            "Recommendation cache set",
            {
                "user_id": user_id,
                "algorithm": params.get("algorithm", "unknown"),
                "items_count": len(recommendations),
                "ttl": self.ttl
            }
        )
    
    def invalidate(self, user_id: Optional[str] = None) -> int:
        """
        Invalidate cache entries for a user or all entries.
        
        Args:
            user_id: Optional user ID to invalidate cache for (None for all)
            
        Returns:
            Number of invalidated entries
        """
        if user_id is None:
            # Invalidate all cache entries
            count = len(self._cache)
            self._cache = {}
            return count
        
        # Find and invalidate entries for specific user
        to_remove = []
        for key, entry in self._cache.items():
            # Check if entry contains the user ID
            encrypted_data = entry["data"]
            try:
                decrypted_data = self.security_handler.decrypt_recommendation_data(encrypted_data)
                
                # Check if any recommendation is for this user
                if any(rec.get("user_id") == user_id for rec in decrypted_data):
                    to_remove.append(key)
            except Exception:
                # If decryption fails, remove the entry as a precaution
                to_remove.append(key)
        
        # Remove identified entries
        for key in to_remove:
            del self._cache[key]
            
        # Log invalidation using standardized security approach
        self.security_handler.secure_log(
            "Recommendation cache invalidation",
            {
                "user_id": user_id,
                "entries_removed": len(to_remove)
            }
        )
        
        return len(to_remove)
        
    def cleanup(self) -> int:
        """
        Remove all expired entries from cache.
        
        Returns:
            Number of removed entries
        """
        now = datetime.now()
        to_remove = [
            key for key, entry in self._cache.items() 
            if entry["expires_at"] < now
        ]
        
        for key in to_remove:
            del self._cache[key]
            
        return len(to_remove)
