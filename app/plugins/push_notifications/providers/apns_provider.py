"""
Apple Push Notification Service (APNs) Provider

This module implements the APNs provider for push notifications,
following the standardized security approach across all providers.
"""

import logging
import json
import uuid
import time
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

import jwt
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from app.plugins.push_notifications.providers.base_provider import BasePushProvider
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler

logger = logging.getLogger(__name__)

class APNSProvider(BasePushProvider):
    """
    Apple Push Notification Service provider for push notifications,
    implementing the standardized security approach.
    """
    
    def __init__(self, security_handler: SecurityHandler):
        """
        Initialize the APNs provider.
        
        Args:
            security_handler: Security handler for encryption and validation
        """
        super().__init__("apns", security_handler)
        self.key_id = None
        self.team_id = None
        self.bundle_id = None
        self.key_file_path = None
        self.private_key = None
        self.auth_token = None
        self.token_expiry = None
        self.is_production = True
        self.apns_topics = {}
        
        # APNs endpoints
        self.production_endpoint = "https://api.push.apple.com"
        self.sandbox_endpoint = "https://api.sandbox.push.apple.com"
        logger.info("APNs provider initialized")
    
    def initialize(self, key_id: str, team_id: str, bundle_id: str, 
                  key_file_path: str, is_production: bool = True, 
                  topics: Dict[str, str] = None) -> bool:
        """
        Initialize the APNs provider with credentials.
        
        Args:
            key_id: APNs key ID (from Apple Developer account)
            team_id: Apple Developer Team ID
            bundle_id: App bundle ID
            key_file_path: Path to the p8 private key file
            is_production: Whether to use production environment
            topics: Dictionary of custom topics for different notification types
            
        Returns:
            bool: Success status
        """
        try:
            super().initialize()
            
            # Validate credentials
            if not all([key_id, team_id, bundle_id, key_file_path]):
                logger.error("APNs initialization failed: Missing required credentials")
                return False
            
            # Check if key file exists
            if not os.path.exists(key_file_path):
                logger.error(f"APNs initialization failed: Key file not found at {key_file_path}")
                return False
            
            # Store credentials securely
            self.key_id = key_id
            self.team_id = team_id
            self.bundle_id = bundle_id
            self.key_file_path = key_file_path
            self.is_production = is_production
            
            # Store topics
            if topics:
                self.apns_topics = topics
            else:
                self.apns_topics = {
                    "default": bundle_id
                }
            
            # Read and encrypt the private key
            try:
                with open(key_file_path, 'rb') as key_file:
                    key_data = key_file.read()
                    
                # Securely store the key data
                self.private_key = self.security_handler.encrypt_data({
                    "key_data": key_data.decode('utf-8') if isinstance(key_data, bytes) else key_data
                })
                
                logger.info("APNs private key loaded and encrypted")
            except Exception as e:
                logger.error(f"Failed to read APNs private key: {str(e)}")
                return False
            
            # Generate a test token to validate credentials
            if not self._get_auth_token():
                logger.error("APNs initialization failed: Could not generate authentication token")
                return False
            
            # Log successful initialization with secure audit trail
            self._log_notification_event(
                "provider_init",
                str(uuid.uuid4()),
                "system",
                "system",
                "success",
                {
                    "provider": "apns", 
                    "environment": "production" if self.is_production else "sandbox",
                    "bundle_id": self.bundle_id
                }
            )
            
            logger.info(f"APNs provider initialized successfully in {'production' if self.is_production else 'sandbox'} mode")
            return True
        except Exception as e:
            logger.error(f"APNs initialization error: {str(e)}")
            
            # Log initialization failure
            self._log_notification_event(
                "provider_init",
                str(uuid.uuid4()),
                "system",
                "system",
                "error",
                {"provider": "apns", "error": str(e)}
            )
            
            return False
    
    def _get_auth_token(self) -> Optional[str]:
        """
        Get a valid JWT authentication token for APNs.
        
        Returns:
            str: Valid JWT token or None if error
        """
        # Check if existing token is still valid (with 5 minute buffer)
        now = datetime.utcnow()
        if self.auth_token and self.token_expiry and self.token_expiry > now + timedelta(minutes=5):
            return self.auth_token
        
        try:
            # Get the encrypted private key
            if not self.private_key:
                logger.error("Cannot get auth token: No private key available")
                return None
            
            # Decrypt private key
            decrypted_data = self.security_handler.decrypt_data(self.private_key)
            key_str = decrypted_data.get("key_data")
            
            if not key_str:
                logger.error("Cannot get auth token: Failed to decrypt private key")
                return None
            
            # Convert string to bytes if needed
            key_data = key_str.encode('utf-8') if isinstance(key_str, str) else key_str
            
            # Load the private key
            try:
                private_key = serialization.load_pem_private_key(
                    key_data,
                    password=None,
                    backend=default_backend()
                )
            except Exception:
                # Try with PKCS8 format (Apple's .p8 files)
                try:
                    # Remove headers if they exist
                    if "-----BEGIN PRIVATE KEY-----" in key_str:
                        lines = key_str.strip().split('\n')
                        if lines[0] == "-----BEGIN PRIVATE KEY-----" and lines[-1] == "-----END PRIVATE KEY-----":
                            key_content = ''.join(lines[1:-1])
                            import base64
                            key_data = base64.b64decode(key_content)
                    
                    private_key = serialization.load_der_private_key(
                        key_data,
                        password=None,
                        backend=default_backend()
                    )
                except Exception as e:
                    logger.error(f"Failed to load private key: {str(e)}")
                    return None
            
            # Token expiration (1 hour from now)
            token_expiration = int(time.time()) + 3600
            
            # Create the JWT payload
            payload = {
                'iss': self.team_id,
                'iat': int(time.time())
            }
            
            # Create the JWT token
            token = jwt.encode(
                payload,
                private_key,
                algorithm='ES256',
                headers={
                    'kid': self.key_id,
                    'alg': 'ES256'
                }
            )
            
            # Store the token and expiry
            self.auth_token = token
            self.token_expiry = now + timedelta(minutes=55)  # Set expiry to 55 minutes
            
            return token
        except Exception as e:
            logger.error(f"Error generating APNs authentication token: {str(e)}")
            return None
    
    def _get_apns_endpoint(self) -> str:
        """
        Get the appropriate APNs endpoint URL.
        
        Returns:
            str: APNs endpoint URL
        """
        if self.is_production:
            return self.production_endpoint
        else:
            return self.sandbox_endpoint
    
    def _get_topic_for_notification(self, notification_type: str = None) -> str:
        """
        Get the appropriate APNs topic for the notification type.
        
        Args:
            notification_type: Type of notification (e.g., alert, background)
            
        Returns:
            str: APNs topic
        """
        if notification_type and notification_type in self.apns_topics:
            return self.apns_topics[notification_type]
        
        return self.apns_topics.get("default", self.bundle_id)
    
    def _prepare_apns_payload(self, title: str, body: str, data: Dict[str, Any] = None,
                            badge: int = None, sound: str = "default",
                            category: str = None, thread_id: str = None,
                            content_available: bool = False, mutable_content: bool = False,
                            expiration: int = None, priority: int = 10) -> Dict[str, Any]:
        """
        Prepare the APNs message payload.
        
        Args:
            title: Notification title
            body: Notification body
            data: Custom data payload
            badge: Badge count
            sound: Sound to play
            category: Notification category
            thread_id: Thread identifier for grouping
            content_available: Whether content is available
            mutable_content: Whether content is mutable
            expiration: Expiration time
            priority: Priority (10=immediate, 5=power considerations)
            
        Returns:
            Dict: APNs message payload
        """
        # Build the alert dictionary
        alert = {
            "title": title,
            "body": body
        }
        
        # Build the aps dictionary
        aps = {
            "alert": alert
        }
        
        # Add optional fields to aps
        if badge is not None:
            aps["badge"] = badge
        
        if sound:
            aps["sound"] = sound
        
        if category:
            aps["category"] = category
        
        if thread_id:
            aps["thread-id"] = thread_id
        
        if content_available:
            aps["content-available"] = 1
        
        if mutable_content:
            aps["mutable-content"] = 1
        
        # Build the payload
        payload = {
            "aps": aps
        }
        
        # Add custom data
        if data:
            for key, value in data.items():
                # Avoid overwriting the aps dictionary
                if key != "aps":
                    payload[key] = value
        
        return payload
    
    def send_notification(self, notification_id: str, user_id: str, device_id: str, 
                         device_token: str, title: str, body: str, data: Dict[str, Any] = None, 
                         high_priority: bool = False, notification_type: str = None,
                         badge: int = None, sound: str = "default", 
                         category: str = None) -> Dict[str, Any]:
        """
        Send a push notification using APNs.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            device_token: APNs device token
            title: Notification title
            body: Notification body
            data: Notification data payload
            high_priority: Whether the notification is high priority
            notification_type: Type of notification
            badge: Badge count
            sound: Sound to play
            category: Notification category
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "apns",
            "notification_id": notification_id,
            "user_id": user_id,
            "device_id": device_id,
            "success": False,
            "status": "failed",
            "message": "",
            "details": {}
        }
        
        try:
            # Validate the notification payload
            if not self._validate_payload(title, body, data or {}):
                error_message = "Notification payload validation failed"
                result["message"] = error_message
                
                # Log error with secure audit trail
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    device_id,
                    "validation_failed",
                    {"error": error_message}
                )
                
                return result
            
            # Get authentication token
            auth_token = self._get_auth_token()
            if not auth_token:
                result["message"] = "Failed to get APNs authentication token"
                
                # Log error with secure audit trail
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    device_id,
                    "auth_failed",
                    {"error": "Failed to get APNs authentication token"}
                )
                
                return result
            
            # Prepare the APNs payload
            payload = self._prepare_apns_payload(
                title=title,
                body=body,
                data=data,
                badge=badge,
                sound=sound,
                category=category,
                priority=10 if high_priority else 5
            )
            
            # Get the APNs endpoint
            endpoint = self._get_apns_endpoint()
            
            # Get the topic
            topic = self._get_topic_for_notification(notification_type)
            
            # Set up the HTTP request
            url = f"{endpoint}/3/device/{device_token}"
            headers = {
                "Authorization": f"bearer {auth_token}",
                "apns-topic": topic,
                "apns-push-type": "alert",
                "apns-priority": "10" if high_priority else "5",
                "apns-expiration": "0"  # 0 means the notification is not stored if it cannot be delivered
            }
            
            # Add optional headers
            if notification_type == "background":
                headers["apns-push-type"] = "background"
            
            # Send the request
            response = requests.post(url, headers=headers, json=payload)
            
            # Handle the response
            if response.status_code == 200:
                result["success"] = True
                result["status"] = "sent"
                result["message"] = "Notification sent successfully"
                
                # Add APNs-specific ID if available
                apns_id = response.headers.get("apns-id")
                if apns_id:
                    result["details"]["apns_id"] = apns_id
                
                # Log success with secure audit trail
                self._log_notification_event(
                    "send",
                    notification_id,
                    user_id,
                    device_id,
                    "sent",
                    {"apns_id": apns_id} if apns_id else None
                )
            else:
                try:
                    error_data = response.json()
                    error_reason = error_data.get("reason", "Unknown error")
                    result["message"] = f"APNs error: {error_reason}"
                    result["details"] = error_data
                    
                    # Check for token related errors
                    if error_reason in ["BadDeviceToken", "DeviceTokenNotForTopic", "Unregistered"]:
                        result["status"] = "invalid_token"
                    else:
                        result["status"] = "error"
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        device_id,
                        result["status"],
                        {"error": error_reason, "error_code": response.status_code}
                    )
                except ValueError:
                    result["message"] = f"APNs error: {response.text}"
                    result["details"] = {"status_code": response.status_code, "response": response.text}
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        device_id,
                        "error",
                        {"error": response.text, "error_code": response.status_code}
                    )
        except Exception as e:
            result["message"] = f"Unexpected error: {str(e)}"
            
            # Log error with secure audit trail
            self._log_notification_event(
                "error",
                notification_id,
                user_id,
                device_id,
                "exception",
                {"error": str(e)}
            )
        
        return result
    
    def send_to_multiple_devices(self, notification_id: str, user_id: str, 
                               device_tokens: List[Dict[str, str]], title: str, 
                               body: str, data: Dict[str, Any] = None, 
                               high_priority: bool = False, notification_type: str = None,
                               badge: int = None, sound: str = "default", 
                               category: str = None) -> Dict[str, Any]:
        """
        Send a notification to multiple devices using APNs.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_tokens: List of device tokens with device IDs
            title: Notification title
            body: Notification body
            data: Notification data payload
            high_priority: Whether the notification is high priority
            notification_type: Type of notification
            badge: Badge count
            sound: Sound to play
            category: Notification category
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "apns",
            "notification_id": notification_id,
            "user_id": user_id,
            "success": False,
            "status": "failed",
            "message": "",
            "details": {
                "success_count": 0,
                "failure_count": 0,
                "device_results": []
            }
        }
        
        try:
            # Validate the notification payload
            if not self._validate_payload(title, body, data or {}):
                error_message = "Notification payload validation failed"
                result["message"] = error_message
                
                # Log error with secure audit trail
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    "multiple_devices",
                    "validation_failed",
                    {"error": error_message}
                )
                
                return result
            
            # Get authentication token
            auth_token = self._get_auth_token()
            if not auth_token:
                result["message"] = "Failed to get APNs authentication token"
                
                # Log error with secure audit trail
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    "multiple_devices",
                    "auth_failed",
                    {"error": "Failed to get APNs authentication token"}
                )
                
                return result
            
            # Prepare the APNs payload
            payload = self._prepare_apns_payload(
                title=title,
                body=body,
                data=data,
                badge=badge,
                sound=sound,
                category=category,
                priority=10 if high_priority else 5
            )
            
            # Get the APNs endpoint
            endpoint = self._get_apns_endpoint()
            
            # Get the topic
            topic = self._get_topic_for_notification(notification_type)
            
            # Process each device token
            success_count = 0
            failure_count = 0
            device_results = []
            
            for device in device_tokens:
                device_id = device.get("device_id", "unknown")
                token = device.get("token")
                
                if not token:
                    device_results.append({
                        "device_id": device_id,
                        "success": False,
                        "message": "No token provided"
                    })
                    failure_count += 1
                    continue
                
                # Set up the HTTP request for this device
                url = f"{endpoint}/3/device/{token}"
                headers = {
                    "Authorization": f"bearer {auth_token}",
                    "apns-topic": topic,
                    "apns-push-type": "alert",
                    "apns-priority": "10" if high_priority else "5",
                    "apns-expiration": "0"  # 0 means the notification is not stored if it cannot be delivered
                }
                
                # Add optional headers
                if notification_type == "background":
                    headers["apns-push-type"] = "background"
                
                try:
                    # Send the request
                    response = requests.post(url, headers=headers, json=payload)
                    
                    # Handle the response
                    if response.status_code == 200:
                        success_count += 1
                        
                        # Add APNs-specific ID if available
                        apns_id = response.headers.get("apns-id")
                        device_result = {
                            "device_id": device_id,
                            "success": True,
                            "message": "Notification sent successfully"
                        }
                        
                        if apns_id:
                            device_result["apns_id"] = apns_id
                        
                        device_results.append(device_result)
                        
                        # Log success with secure audit trail
                        self._log_notification_event(
                            "send",
                            notification_id,
                            user_id,
                            device_id,
                            "sent",
                            {"apns_id": apns_id} if apns_id else None
                        )
                    else:
                        failure_count += 1
                        
                        try:
                            error_data = response.json()
                            error_reason = error_data.get("reason", "Unknown error")
                            
                            device_results.append({
                                "device_id": device_id,
                                "success": False,
                                "message": f"APNs error: {error_reason}",
                                "error": error_reason,
                                "error_code": response.status_code
                            })
                            
                            # Log error with secure audit trail
                            self._log_notification_event(
                                "error",
                                notification_id,
                                user_id,
                                device_id,
                                "error",
                                {"error": error_reason, "error_code": response.status_code}
                            )
                        except ValueError:
                            device_results.append({
                                "device_id": device_id,
                                "success": False,
                                "message": f"APNs error: {response.text}",
                                "error": response.text,
                                "error_code": response.status_code
                            })
                            
                            # Log error with secure audit trail
                            self._log_notification_event(
                                "error",
                                notification_id,
                                user_id,
                                device_id,
                                "error",
                                {"error": response.text, "error_code": response.status_code}
                            )
                except requests.RequestException as e:
                    failure_count += 1
                    
                    device_results.append({
                        "device_id": device_id,
                        "success": False,
                        "message": f"Request error: {str(e)}",
                        "error": str(e)
                    })
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        device_id,
                        "request_failed",
                        {"error": str(e)}
                    )
            
            # Update result
            result["success"] = success_count > 0
            result["status"] = "sent" if success_count > 0 else "failed"
            result["message"] = f"Sent to {success_count} devices, failed for {failure_count} devices"
            result["details"] = {
                "success_count": success_count,
                "failure_count": failure_count,
                "device_results": device_results
            }
        except Exception as e:
            result["message"] = f"Unexpected error: {str(e)}"
            
            # Log error with secure audit trail
            self._log_notification_event(
                "error",
                notification_id,
                user_id,
                "multiple_devices",
                "exception",
                {"error": str(e)}
            )
        
        return result
    
    def get_delivery_status(self, notification_id: str, user_id: str, device_id: str) -> Dict[str, Any]:
        """
        Get the delivery status of a notification.
        APNs doesn't provide a delivery status API, so this relies on app-side delivery confirmation.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            
        Returns:
            Dict: Status information
        """
        # APNs doesn't provide a direct way to get delivery status,
        # this would typically be implemented with app-side delivery receipts
        
        # Return a response indicating this limitation
        result = {
            "provider": "apns",
            "notification_id": notification_id,
            "user_id": user_id,
            "device_id": device_id,
            "status": "unknown",
            "message": "APNs does not provide delivery status API. Status must be tracked with app-side delivery receipts."
        }
        
        # Log the status check
        self._log_notification_event(
            "status_check",
            notification_id,
            user_id,
            device_id,
            "unavailable",
            {"message": "APNs does not provide delivery status API"}
        )
        
        return result
