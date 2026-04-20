"""
Security Utilities

This module implements security functions for the recommendation plugin,
following the standardized security approach used across KAAPI plugins.
"""
import logging
import json
import hashlib
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class RecommendationSecurity:
    """
    Security handler for recommendation plugin, implementing the standardized
    approach for encryption, data protection, and secure logging.
    """
    
    def __init__(self, encryption_handler=None):
        """
        Initialize security handler with the application's core encryption handler.
        
        Args:
            encryption_handler: The application's encryption handler instance
        """
        self.encryption_handler = encryption_handler
    
    def encrypt_recommendation_data(self, data: Dict[str, Any]) -> str:
        """
        Encrypt sensitive recommendation data using the standardized approach.
        
        Args:
            data: Dictionary containing recommendation data
            
        Returns:
            Encrypted string
        """
        if not self.encryption_handler:
            logger.warning("Encryption handler not available, data not encrypted")
            return json.dumps(data)
            
        return self.encryption_handler.encrypt_sensitive_data(json.dumps(data))
    
    def decrypt_recommendation_data(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt recommendation data using the standardized approach.
        
        Args:
            encrypted_data: Encrypted data string
            
        Returns:
            Dictionary containing decrypted recommendation data
        """
        if not self.encryption_handler:
            logger.warning("Encryption handler not available, assuming data is not encrypted")
            return json.loads(encrypted_data)
            
        decrypted = self.encryption_handler.decrypt_sensitive_data(encrypted_data)
        return json.loads(decrypted)
    
    def hash_user_identifier(self, user_id: str) -> str:
        """
        Create a secure hash of a user ID for logging without exposing actual identifiers.
        
        Args:
            user_id: User identifier to hash
            
        Returns:
            Hashed identifier
        """
        if self.encryption_handler:
            return self.encryption_handler.hash_sensitive_data(user_id)
            
        # Fallback if encryption handler not available
        return hashlib.sha256(user_id.encode()).hexdigest()
    
    def validate_recommendation_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validate recommendation request data for security issues.
        
        Args:
            request_data: Request data to validate
            
        Returns:
            True if request is valid, False otherwise
        """
        # Check for suspicious request patterns (e.g., excessive counts, injection attempts)
        if request_data.get('count', 10) > 100:
            logger.warning("Suspicious request: excessive item count", 
                          extra={"count": request_data.get('count')})
            return False
            
        # Additional validation logic can be added here
        
        return True
    
    def secure_log(self, message: str, data: Dict[str, Any], level: str = "info"):
        """
        Securely log events with sensitive data protected.
        
        Args:
            message: Log message
            data: Data to log (will be protected)
            level: Log level ('info', 'warning', 'error')
        """
        # Hash or remove any sensitive fields
        secure_data = data.copy()
        
        # Protect user identifiers
        if 'user_id' in secure_data:
            secure_data['user_id_hash'] = self.hash_user_identifier(str(secure_data['user_id']))
            del secure_data['user_id']
            
        # Encrypt any data that might contain patterns of user behavior
        if 'recommendations' in secure_data:
            secure_data['recommendations_count'] = len(secure_data['recommendations'])
            del secure_data['recommendations']
            
        # Log with appropriate level
        if level == "warning":
            logger.warning(message, extra=secure_data)
        elif level == "error":
            logger.error(message, extra=secure_data)
        else:
            logger.info(message, extra=secure_data)
