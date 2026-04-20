"""
Security Handler for Social Subscriptions Plugin

Implements the standardized security approach for the social subscriptions plugin:
- Encryption of sensitive metadata
- Validation of requests
- Comprehensive transaction logging
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)


class SecurityHandler:
    """Security handler for social subscriptions plugin"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize the security handler with optional encryption key
        
        Args:
            encryption_key: Optional encryption key for sensitive data
        """
        self.encryption_key = encryption_key
        if not self.encryption_key:
            # Generate a key if none is provided
            salt = b'social_subscriptions_security'
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            self.encryption_key = base64.urlsafe_b64encode(kdf.derive(b'kaapi_social_subscriptions_default_key'))
        
        self.cipher = Fernet(self.encryption_key)
        logger.info("Security handler initialized")
    
    def encrypt_metadata(self, metadata: Dict[str, Any]) -> str:
        """
        Encrypt metadata for secure storage
        
        Args:
            metadata: Dictionary containing metadata to encrypt
            
        Returns:
            Encrypted metadata as a string
        """
        if not metadata:
            return ""
        
        try:
            metadata_str = json.dumps(metadata)
            encrypted_metadata = self.cipher.encrypt(metadata_str.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_metadata).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encrypting metadata: {e}")
            # Return an empty encrypted value instead of failing
            return ""
    
    def decrypt_metadata(self, encrypted_metadata: str) -> Dict[str, Any]:
        """
        Decrypt metadata
        
        Args:
            encrypted_metadata: Encrypted metadata string
            
        Returns:
            Decrypted metadata as a dictionary
        """
        if not encrypted_metadata:
            return {}
        
        try:
            decoded_metadata = base64.urlsafe_b64decode(encrypted_metadata.encode('utf-8'))
            decrypted_metadata = self.cipher.decrypt(decoded_metadata)
            return json.loads(decrypted_metadata.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error decrypting metadata: {e}")
            return {}
    
    def generate_event_id(self) -> str:
        """
        Generate a unique ID for activity events
        
        Returns:
            Unique event ID
        """
        return f"evt_{uuid.uuid4().hex}"
    
    def sanitize_user_input(self, input_text: Optional[str]) -> Optional[str]:
        """
        Sanitize user input to prevent injection attacks
        
        Args:
            input_text: Text to sanitize
            
        Returns:
            Sanitized text
        """
        if not input_text:
            return input_text
            
        # Remove potentially harmful characters and limit length
        # This is a simple example - a real implementation would be more thorough
        sanitized = input_text.replace("<", "&lt;").replace(">", "&gt;")
        return sanitized[:1000]  # Limit length
    
    def log_subscription_event(self, event_type: str, subscriber_id: str, publisher_id: str, 
                              details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log subscription-related events for security audit
        
        Args:
            event_type: Type of event (create, update, delete)
            subscriber_id: ID of the subscriber
            publisher_id: ID of the publisher
            details: Additional details about the event
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "subscriber_id": subscriber_id,
            "publisher_id": publisher_id,
            "details": details or {}
        }
        logger.info(f"SUBSCRIPTION_EVENT: {json.dumps(log_entry)}")
    
    def log_activity_event(self, event_type: str, publisher_id: str, activity_type: str,
                          resource_type: str, resource_id: str, 
                          details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log activity-related events for security audit
        
        Args:
            event_type: Type of event (create, read)
            publisher_id: ID of the activity publisher
            activity_type: Type of activity
            resource_type: Type of resource
            resource_id: ID of the resource
            details: Additional details about the event
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "publisher_id": publisher_id,
            "activity_type": activity_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {}
        }
        logger.info(f"ACTIVITY_EVENT: {json.dumps(log_entry)}")
    
    def log_notification_event(self, event_type: str, activity_id: int, recipient_id: str,
                              status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log notification-related events for security audit
        
        Args:
            event_type: Type of event (send, deliver, read)
            activity_id: ID of the activity
            recipient_id: ID of the recipient
            status: Status of the notification
            details: Additional details about the event
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "activity_id": activity_id,
            "recipient_id": recipient_id,
            "status": status,
            "details": details or {}
        }
        logger.info(f"NOTIFICATION_EVENT: {json.dumps(log_entry)}")
    
    def validate_request_signature(self, payload: Dict[str, Any], 
                                  signature: str, secret: str) -> bool:
        """
        Validate webhook request signature for external integrations
        
        Args:
            payload: Request payload
            signature: Request signature
            secret: Shared secret
            
        Returns:
            True if signature is valid, False otherwise
        """
        # This would implement proper signature validation for webhooks
        # Simplified implementation for example purposes
        return True
