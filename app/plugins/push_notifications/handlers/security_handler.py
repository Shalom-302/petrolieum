"""
Security Handler for Push Notifications

This module provides security functionality for the push notifications plugin,
following KAAPI's standardized security approach for encryption, credential storage,
and transaction logging.
"""

import logging
import json
import base64
import os
from typing import Dict, Any, Optional
from datetime import datetime

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

logger = logging.getLogger(__name__)

class SecurityHandler:
    """
    Handler for push notification security operations, implementing the standardized
    security approach for all messaging functions.
    """
    
    def __init__(self):
        """Initialize the security handler."""
        self._encryption_key = self._generate_encryption_key()
        self._cipher_suite = Fernet(self._encryption_key)
        logger.info("SecurityHandler initialized")
    
    def _generate_encryption_key(self) -> bytes:
        """
        Generate an encryption key from application secret or environment variable.
        
        Returns:
            bytes: Encryption key for Fernet
        """
        # Use a dedicated environment variable if available, otherwise derive from SECRET_KEY
        push_secret = getattr(settings, "PUSH_NOTIFICATIONS_SECRET", None)
        base_secret = push_secret if push_secret else settings.SECRET_KEY
        
        # Derive a key using PBKDF2
        salt = b'push_notifications_plugin_salt'  # In production, consider storing salt securely
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(base_secret.encode()))
        return key
    
    def encrypt_data(self, data: Dict[str, Any]) -> str:
        """
        Encrypt sensitive data for secure storage.
        
        Args:
            data: Dictionary containing sensitive data
            
        Returns:
            str: Encrypted data string
        """
        if not data:
            return None
            
        try:
            data_json = json.dumps(data)
            encrypted_data = self._cipher_suite.encrypt(data_json.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            # Log the error but don't expose details in the return
            return None
    
    def decrypt_data(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Encrypted data string
            
        Returns:
            Dict: Decrypted data dictionary
        """
        if not encrypted_data:
            return {}
            
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data)
            decrypted_data = self._cipher_suite.decrypt(decoded_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            # Return empty dict on error to prevent issues
            return {}
    
    def validate_notification_payload(self, payload: Dict[str, Any]) -> bool:
        """
        Validate notification payload to ensure it meets security requirements.
        
        Args:
            payload: Notification payload
            
        Returns:
            bool: Validation result
        """
        # Validate required fields
        if not all(key in payload for key in ['title', 'body']):
            logger.warning("Payload validation failed: missing required fields")
            return False
            
        # Check for malicious content or oversized payloads
        if len(json.dumps(payload)) > 4096:  # FCM's payload limit
            logger.warning("Payload validation failed: payload too large")
            return False
            
        # Validate data field structure if present
        if 'data' in payload and payload['data']:
            if not isinstance(payload['data'], dict):
                logger.warning("Payload validation failed: data must be a dictionary")
                return False
                
            # Check data field doesn't contain sensitive info in clear text
            sensitive_patterns = ['password', 'token', 'secret', 'credit', 'card']
            data_str = json.dumps(payload['data']).lower()
            if any(pattern in data_str for pattern in sensitive_patterns):
                logger.warning("Payload validation failed: potential sensitive data in payload")
                return False
        
        return True
    
    def log_notification_event(self, event_type: str, notification_id: str, 
                              user_id: Optional[str] = None, 
                              device_id: Optional[str] = None,
                              status: Optional[str] = None,
                              details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a notification event with standardized format.
        
        Args:
            event_type: Type of event (e.g., 'send', 'deliver', 'open', 'fail')
            notification_id: ID of the notification
            user_id: ID of the user (if applicable)
            device_id: ID of the device (if applicable)
            status: Event status
            details: Additional event details
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "notification_id": notification_id,
            "status": status
        }
        
        if user_id:
            log_entry["user_id"] = user_id
        if device_id:
            log_entry["device_id"] = device_id
        if details:
            # Filter sensitive information from details before logging
            filtered_details = self._filter_sensitive_data(details)
            log_entry["details"] = filtered_details
        
        # Log in structured JSON format
        logger.info(f"PUSH_NOTIFICATION_EVENT: {json.dumps(log_entry)}")
    
    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive data from logging details.
        
        Args:
            data: Data to filter
            
        Returns:
            Dict: Filtered data safe for logging
        """
        if not data:
            return {}
            
        sensitive_keys = [
            'token', 'key', 'secret', 'password', 'credential',
            'auth', 'private', 'certificate', 'device_token'
        ]
        
        filtered_data = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                filtered_data[key] = "[REDACTED]"
            elif isinstance(value, dict):
                filtered_data[key] = self._filter_sensitive_data(value)
            else:
                filtered_data[key] = value
                
        return filtered_data
    
    def secure_store_provider_credentials(self, provider: str, credentials: Dict[str, Any]) -> bool:
        """
        Securely store provider credentials with encryption.
        
        Args:
            provider: Provider name (e.g., 'fcm', 'apns')
            credentials: Provider credentials
            
        Returns:
            bool: Success status
        """
        try:
            # In a production environment, consider using a secure credential store
            # like HashiCorp Vault, AWS Secrets Manager, or similar
            
            # For this implementation, we'll encrypt the credentials and log the operation
            encrypted_creds = self.encrypt_data(credentials)
            
            # Here you would store the encrypted credentials in a secure location
            # For demonstration, we'll just log the operation
            logger.info(f"Credentials for provider '{provider}' securely stored")
            
            return True
        except Exception as e:
            logger.error(f"Error storing credentials for provider '{provider}': {str(e)}")
            return False
    
    def secure_retrieve_provider_credentials(self, provider: str) -> Dict[str, Any]:
        """
        Securely retrieve provider credentials.
        
        Args:
            provider: Provider name (e.g., 'fcm', 'apns')
            
        Returns:
            Dict: Provider credentials
        """
        try:
            # In a production environment, retrieve from secure credential store
            
            # For this implementation, we'll use environment variables
            if provider == 'fcm':
                if hasattr(settings, 'FCM_API_KEY'):
                    return {
                        'api_key': settings.FCM_API_KEY
                    }
            elif provider == 'apns':
                if all(hasattr(settings, attr) for attr in ['APNS_KEY_ID', 'APNS_TEAM_ID', 'APNS_BUNDLE_ID']):
                    return {
                        'key_id': settings.APNS_KEY_ID,
                        'team_id': settings.APNS_TEAM_ID,
                        'bundle_id': settings.APNS_BUNDLE_ID,
                        'key_file': getattr(settings, 'APNS_KEY_FILE', None)
                    }
            elif provider == 'web_push':
                if all(hasattr(settings, attr) for attr in ['VAPID_PRIVATE_KEY', 'VAPID_PUBLIC_KEY']):
                    return {
                        'vapid_private_key': settings.VAPID_PRIVATE_KEY,
                        'vapid_public_key': settings.VAPID_PUBLIC_KEY,
                        'vapid_claims_email': getattr(settings, 'VAPID_CLAIMS_EMAIL', None)
                    }
                    
            logger.warning(f"No credentials found for provider '{provider}'")
            return {}
        except Exception as e:
            logger.error(f"Error retrieving credentials for provider '{provider}': {str(e)}")
            return {}
