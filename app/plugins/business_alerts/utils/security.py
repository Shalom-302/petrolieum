"""
Security utilities for business alerts.

This module contains security-related utility functions for the
business alerts plugin, implementing the standardized security approach
used across the application.
"""

import logging
import secrets
from typing import Dict, Any, Optional

from app.core.security import (
    create_encryption_handler, 
    EncryptionHandler,
    create_default_encryption
)

logger = logging.getLogger(__name__)

# Module-level variables
_alert_security_initialized = False
_alert_encryption_handler = None


def initialize_alert_security(secret_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Initialize security utilities for the business alerts plugin.
    
    This function sets up encryption handlers and other security
    utilities needed by the business alerts plugin. It follows the
    standardized security approach used across the application.
    
    Args:
        secret_key: Optional custom secret key for encryption
        
    Returns:
        Dict[str, Any]: Initialization status
    """
    global _alert_security_initialized, _alert_encryption_handler
    
    if _alert_security_initialized:
        logger.info("Business alerts security already initialized")
        return {"status": "already_initialized"}
        
    try:
        # Use provided secret key or generate a new one
        if not secret_key:
            # Use application default or generate a new one
            logger.info("Using default encryption for business alerts")
            _alert_encryption_handler = create_default_encryption()
        else:
            # Create custom encryption handler
            logger.info("Creating custom encryption handler for business alerts")
            _alert_encryption_handler = create_encryption_handler(secret_key)
            
        # Mark as initialized
        _alert_security_initialized = True
        
        logger.info("Business alerts security initialized successfully")
        return {
            "status": "success",
            "message": "Business alerts security initialized successfully"
        }
        
    except Exception as e:
        logger.error(f"Error initializing business alerts security: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to initialize security: {str(e)}"
        }


def create_alert_encryption_handler() -> EncryptionHandler:
    """
    Get the encryption handler for business alerts.
    
    Returns:
        EncryptionHandler: Encryption handler for business alerts
        
    Note:
        This will initialize security if not already initialized.
    """
    global _alert_security_initialized, _alert_encryption_handler
    
    if not _alert_security_initialized:
        initialize_alert_security()
        
    return _alert_encryption_handler


def encrypt_alert_data(data: Dict[str, Any]) -> str:
    """
    Encrypt sensitive alert data.
    
    Args:
        data: Data to encrypt
        
    Returns:
        str: Encrypted data
    """
    encryption_handler = create_alert_encryption_handler()
    return encryption_handler.encrypt_data(data)


def decrypt_alert_data(encrypted_data: str) -> Dict[str, Any]:
    """
    Decrypt sensitive alert data.
    
    Args:
        encrypted_data: Encrypted data to decrypt
        
    Returns:
        Dict[str, Any]: Decrypted data
    """
    encryption_handler = create_alert_encryption_handler()
    return encryption_handler.decrypt_data(encrypted_data)


def generate_secure_token() -> str:
    """
    Generate a secure token for API operations.
    
    Returns:
        str: Secure token
    """
    return secrets.token_urlsafe(32)


def validate_entity_access(user_id: str, entity_type: str, entity_id: str) -> bool:
    """
    Validate that a user has access to an entity.
    
    Args:
        user_id: User ID
        entity_type: Entity type
        entity_id: Entity ID
        
    Returns:
        bool: Whether the user has access to the entity
        
    Note:
        This is a placeholder implementation. In a real system, this would
        check against a permissions database or service.
    """
    # In a real implementation, this would check user permissions
    # For now, we'll just log the check and return True
    logger.info(f"Validating access for user {user_id} to {entity_type}:{entity_id}")
    return True
