"""
Base Provider for Push Notifications

This module defines the base provider class for push notifications,
implementing the standardized security approach across all providers.
"""

import logging
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.plugins.push_notifications.handlers.security_handler import SecurityHandler

logger = logging.getLogger(__name__)

class BasePushProvider:
    """
    Base class for all push notification providers,
    implementing the standardized security approach.
    """
    
    def __init__(self, provider_name: str, security_handler: SecurityHandler):
        """
        Initialize the base push provider.
        
        Args:
            provider_name: Name of the provider
            security_handler: Security handler for encryption and validation
        """
        self.provider_name = provider_name
        self.security_handler = security_handler
        logger.info(f"Initialized {provider_name} provider")
    
    def initialize(self) -> bool:
        """
        Initialize the provider with necessary setup.
        
        Returns:
            bool: Success status
        """
        logger.info(f"Base initialization for {self.provider_name}")
        return True
    
    def _validate_payload(self, title: str, body: str, data: Dict[str, Any]) -> bool:
        """
        Validate the notification payload for security risks.
        
        Args:
            title: Notification title
            body: Notification body
            data: Notification data payload
            
        Returns:
            bool: Validation success
        """
        try:
            # Check for common security issues
            validation_result = self.security_handler.validate_payload(title, body, data)
            if not validation_result.get('valid', False):
                logger.warning(f"Payload validation failed: {validation_result.get('reason')}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error in payload validation: {str(e)}")
            return False
    
    def _encrypt_sensitive_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive metadata for secure storage.
        
        Args:
            data: Data containing potentially sensitive information
            
        Returns:
            Dict: Data with sensitive fields encrypted
        """
        try:
            # Identify sensitive fields
            sensitive_fields = self._identify_sensitive_fields(data)
            
            # Create a copy of data for modification
            secure_data = data.copy()
            
            # Encrypt sensitive fields
            for field in sensitive_fields:
                if field in secure_data and secure_data[field]:
                    secure_data[field] = self.security_handler.encrypt_data({field: secure_data[field]})
            
            return secure_data
        except Exception as e:
            logger.error(f"Error encrypting sensitive metadata: {str(e)}")
            return data  # Return original data on error
    
    def _identify_sensitive_fields(self, data: Dict[str, Any]) -> List[str]:
        """
        Identify fields that contain sensitive information.
        
        Args:
            data: Data dictionary to check
            
        Returns:
            List: List of sensitive field names
        """
        sensitive_fields = []
        sensitive_patterns = ['token', 'credential', 'auth', 'private', 'key', 
                            'certificate', 'secret', 'password', 'account']
        
        for key in data.keys():
            if any(pattern in key.lower() for pattern in sensitive_patterns):
                sensitive_fields.append(key)
        
        return sensitive_fields
    
    def _log_notification_event(self, event_type: str, notification_id: str, 
                                user_id: str, device_id: str, status: str, 
                                details: Optional[Dict[str, Any]] = None) -> str:
        """
        Log notification events for auditing and debugging.
        
        Args:
            event_type: Type of event (send, status_update, error)
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            status: Status of the notification
            details: Additional details about the event
            
        Returns:
            str: ID of the logged event
        """
        try:
            event_id = str(uuid.uuid4())
            
            # Prepare the log entry with standardized fields
            log_entry = {
                "event_id": event_id,
                "timestamp": datetime.utcnow().isoformat(),
                "provider": self.provider_name,
                "event_type": event_type,
                "notification_id": notification_id,
                "user_id": user_id,
                "device_id": device_id,
                "status": status
            }
            
            # Add optional details
            if details:
                # Encrypt sensitive details
                secure_details = self._encrypt_sensitive_metadata(details)
                log_entry["details"] = secure_details
            
            # Log to both provider-specific and system-wide logs
            provider_log = f"PUSH_NOTIFICATION - {self.provider_name} - {event_type}: " \
                        f"Notification {notification_id} to User {user_id} on Device {device_id} - {status}"
            
            if event_type == "error":
                error_message = details.get("error", "Unknown error") if details else "Unknown error"
                logger.error(f"{provider_log} - Error: {error_message}")
            else:
                logger.info(provider_log)
            
            # Log entry could be saved to database or sent to log aggregation service
            # This is a placeholder for implementation in derived classes
            
            return event_id
        except Exception as e:
            logger.error(f"Error logging notification event: {str(e)}")
            return ""
    
    def send_notification(self, notification_id: str, user_id: str, device_id: str, 
                        title: str, body: str, data: Dict[str, Any] = None, 
                        high_priority: bool = False) -> Dict[str, Any]:
        """
        Send a push notification.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            title: Notification title
            body: Notification body
            data: Notification data payload
            high_priority: Whether the notification is high priority
            
        Returns:
            Dict: Result containing status and details
        """
        # This is an abstract method to be implemented by derived classes
        raise NotImplementedError("send_notification must be implemented by provider classes")
    
    def get_delivery_status(self, notification_id: str, user_id: str, device_id: str) -> Dict[str, Any]:
        """
        Get the delivery status of a notification.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            
        Returns:
            Dict: Status information
        """
        # This is an abstract method to be implemented by derived classes
        raise NotImplementedError("get_delivery_status must be implemented by provider classes")
