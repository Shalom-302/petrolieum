"""
Firebase Cloud Messaging (FCM) Provider for Push Notifications

This module implements the FCM provider for push notifications,
following the standardized security approach across all providers.
"""

import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time

import requests
from firebase_admin import messaging, initialize_app, credentials, get_app
from firebase_admin.exceptions import FirebaseError
from google.oauth2 import service_account

from app.plugins.push_notifications.providers.base_provider import BasePushProvider
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler

logger = logging.getLogger(__name__)

class FCMProvider(BasePushProvider):
    """
    Firebase Cloud Messaging provider for push notifications,
    implementing the standardized security approach.
    """
    
    def __init__(self, security_handler: SecurityHandler):
        """
        Initialize the FCM provider.
        
        Args:
            security_handler: Security handler for encryption and validation
        """
        super().__init__("fcm", security_handler)
        self.api_key = None
        self.service_account_info = None
        self.fcm_app = None
        self.api_url = "https://fcm.googleapis.com/fcm/send"
        self.batch_api_url = "https://fcm.googleapis.com/batch"
        self.oauth_token = None
        self.token_expiry = None
        logger.info("FCM provider initialized")
    
    def initialize(self, api_key: str = None, service_account_json: str = None) -> bool:
        """
        Initialize the FCM provider with credentials.
        
        Args:
            api_key: FCM server key for legacy HTTP API
            service_account_json: Service account JSON for FCM Admin SDK
            
        Returns:
            bool: Success status
        """
        try:
            super().initialize()
            
            if not api_key and not service_account_json:
                logger.error("FCM initialization failed: No credentials provided")
                return False
            
            # Store credentials securely
            if api_key:
                self.api_key = api_key
                logger.info("FCM initialized with server key")
            
            # Initialize Firebase Admin SDK if service account info is provided
            if service_account_json:
                try:
                    # Securely store service account info
                    self.service_account_info = self.security_handler.encrypt_data({
                        "service_account": service_account_json
                    })
                    
                    # Parse the service account info
                    service_info = json.loads(service_account_json)
                    
                    # Initialize Firebase Admin app
                    try:
                        # Try to get existing app
                        self.fcm_app = get_app("fcm")
                        logger.info("Using existing Firebase app")
                    except ValueError:
                        # Create new app if it doesn't exist
                        cred = credentials.Certificate(service_info)
                        self.fcm_app = initialize_app(cred, name="fcm")
                        logger.info("Initialized new Firebase Admin app")
                    
                    logger.info("FCM initialized with service account")
                except (ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Invalid service account JSON: {str(e)}")
                    return False
            
            # Log successful initialization with secure audit trail
            self._log_notification_event(
                "provider_init",
                str(uuid.uuid4()),
                "system",
                "system",
                "success",
                {"provider": "fcm", "using_api_key": bool(api_key), "using_service_account": bool(service_account_json)}
            )
            
            return True
        except Exception as e:
            logger.error(f"FCM initialization error: {str(e)}")
            
            # Log initialization failure
            self._log_notification_event(
                "provider_init",
                str(uuid.uuid4()),
                "system",
                "system",
                "error",
                {"provider": "fcm", "error": str(e)}
            )
            
            return False
    
    def _get_oauth_token(self) -> Optional[str]:
        """
        Get a valid OAuth token for FCM HTTP v1 API.
        
        Returns:
            str: Valid OAuth token or None if error
        """
        # Check if existing token is still valid
        now = datetime.utcnow()
        if self.oauth_token and self.token_expiry and self.token_expiry > now:
            return self.oauth_token
        
        try:
            # Get the encrypted service account info
            if not self.service_account_info:
                logger.error("Cannot get OAuth token: No service account info")
                return None
            
            # Decrypt service account info
            decrypted_data = self.security_handler.decrypt_data(self.service_account_info)
            service_json = decrypted_data.get("service_account")
            
            if not service_json:
                logger.error("Cannot get OAuth token: Failed to decrypt service account info")
                return None
            
            # Parse the service account JSON
            service_info = json.loads(service_json)
            
            # Create service account credentials for OAuth
            credentials = service_account.Credentials.from_service_account_info(
                service_info,
                scopes=["https://www.googleapis.com/auth/firebase.messaging"]
            )
            
            # Get the token
            token = credentials.token
            if not token:
                credentials.refresh(None)
                token = credentials.token
            
            # Store token and expiry
            self.oauth_token = token
            self.token_expiry = now + timedelta(minutes=55)  # Set expiry slightly less than actual
            
            return token
        except Exception as e:
            logger.error(f"Error getting OAuth token: {str(e)}")
            return None
    
    def _prepare_fcm_message(self, token: str, title: str, body: str, 
                            data: Dict[str, Any] = None, high_priority: bool = False) -> Dict[str, Any]:
        """
        Prepare the FCM message payload.
        
        Args:
            token: Device FCM token
            title: Notification title
            body: Notification body
            data: Notification data payload
            high_priority: Whether the notification is high priority
            
        Returns:
            Dict: FCM message payload
        """
        # Base message structure
        message = {
            "to": token,
            "notification": {
                "title": title,
                "body": body,
                "sound": "default"
            },
            "priority": "high" if high_priority else "normal"
        }
        
        # Add data payload if provided
        if data:
            # Ensure all values are strings for FCM
            string_data = {}
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    string_data[key] = json.dumps(value)
                else:
                    string_data[key] = str(value)
            
            message["data"] = string_data
        
        return message
    
    def send_notification(self, notification_id: str, user_id: str, device_id: str, 
                         device_token: str, title: str, body: str, data: Dict[str, Any] = None, 
                         high_priority: bool = False) -> Dict[str, Any]:
        """
        Send a push notification using FCM.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            device_token: FCM device token
            title: Notification title
            body: Notification body
            data: Notification data payload
            high_priority: Whether the notification is high priority
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "fcm",
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
            
            # Use Firebase Admin SDK if available, otherwise fall back to HTTP API
            if self.fcm_app:
                try:
                    # Build FCM message
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=title,
                            body=body
                        ),
                        data=data if data else {},
                        token=device_token,
                        android=messaging.AndroidConfig(
                            priority="high" if high_priority else "normal"
                        ),
                        apns=messaging.APNSConfig(
                            headers={
                                "apns-priority": "10" if high_priority else "5"
                            }
                        )
                    )
                    
                    # Send message
                    response = messaging.send(message, app=self.fcm_app)
                    
                    result["success"] = True
                    result["status"] = "sent"
                    result["message"] = "Notification sent successfully"
                    result["details"] = {"message_id": response}
                    
                    # Log success with secure audit trail
                    self._log_notification_event(
                        "send",
                        notification_id,
                        user_id,
                        device_id,
                        "sent",
                        {"message_id": response}
                    )
                except FirebaseError as e:
                    result["message"] = f"Firebase Admin SDK error: {str(e)}"
                    result["details"] = {"error_code": e.code if hasattr(e, 'code') else "unknown"}
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        device_id,
                        "send_failed",
                        {"error": str(e), "error_code": e.code if hasattr(e, 'code') else "unknown"}
                    )
            elif self.api_key:
                try:
                    # Prepare the FCM message
                    message = self._prepare_fcm_message(device_token, title, body, data, high_priority)
                    
                    # Set up the HTTP request
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"key={self.api_key}"
                    }
                    
                    # Send the request
                    response = requests.post(self.api_url, headers=headers, data=json.dumps(message))
                    response_data = response.json()
                    
                    if response.status_code == 200 and response_data.get("success", 0) >= 1:
                        result["success"] = True
                        result["status"] = "sent"
                        result["message"] = "Notification sent successfully"
                        result["details"] = {
                            "message_id": response_data.get("multicast_id"),
                            "success_count": response_data.get("success"),
                            "failure_count": response_data.get("failure"),
                        }
                        
                        # Log success with secure audit trail
                        self._log_notification_event(
                            "send",
                            notification_id,
                            user_id,
                            device_id,
                            "sent",
                            {"message_id": response_data.get("multicast_id")}
                        )
                    else:
                        result["message"] = f"FCM HTTP API error: {response.text}"
                        result["details"] = response_data
                        
                        # Log error with secure audit trail
                        self._log_notification_event(
                            "error",
                            notification_id,
                            user_id,
                            device_id,
                            "send_failed",
                            {"error": response.text, "error_code": response.status_code}
                        )
                except requests.RequestException as e:
                    result["message"] = f"HTTP request error: {str(e)}"
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        device_id,
                        "request_failed",
                        {"error": str(e)}
                    )
            else:
                result["message"] = "No FCM credentials available"
                
                # Log error with secure audit trail
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    device_id,
                    "no_credentials",
                    {"error": "No FCM credentials available"}
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
                               high_priority: bool = False) -> Dict[str, Any]:
        """
        Send a notification to multiple devices.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_tokens: List of device tokens with device IDs
            title: Notification title
            body: Notification body
            data: Notification data payload
            high_priority: Whether the notification is high priority
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "fcm",
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
            
            # Use Firebase Admin SDK if available
            if self.fcm_app:
                try:
                    messages = []
                    device_results = []
                    
                    # Prepare messages for each device
                    for device in device_tokens:
                        device_id = device.get("device_id", "unknown")
                        token = device.get("token")
                        
                        if not token:
                            device_results.append({
                                "device_id": device_id,
                                "success": False,
                                "message": "No token provided"
                            })
                            continue
                        
                        # Build FCM message
                        message = messaging.Message(
                            notification=messaging.Notification(
                                title=title,
                                body=body
                            ),
                            data=data if data else {},
                            token=token,
                            android=messaging.AndroidConfig(
                                priority="high" if high_priority else "normal"
                            ),
                            apns=messaging.APNSConfig(
                                headers={
                                    "apns-priority": "10" if high_priority else "5"
                                }
                            )
                        )
                        
                        messages.append((device_id, message))
                    
                    # Send messages in batches
                    success_count = 0
                    failure_count = 0
                    
                    for device_id, message in messages:
                        try:
                            response = messaging.send(message, app=self.fcm_app)
                            
                            device_results.append({
                                "device_id": device_id,
                                "success": True,
                                "message_id": response
                            })
                            
                            success_count += 1
                            
                            # Log success for this device
                            self._log_notification_event(
                                "send",
                                notification_id,
                                user_id,
                                device_id,
                                "sent",
                                {"message_id": response}
                            )
                        except FirebaseError as e:
                            failure_count += 1
                            
                            device_results.append({
                                "device_id": device_id,
                                "success": False,
                                "error": str(e),
                                "error_code": e.code if hasattr(e, 'code') else "unknown"
                            })
                            
                            # Log error for this device
                            self._log_notification_event(
                                "error",
                                notification_id,
                                user_id,
                                device_id,
                                "send_failed",
                                {"error": str(e), "error_code": e.code if hasattr(e, 'code') else "unknown"}
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
                    result["message"] = f"Firebase Admin SDK error: {str(e)}"
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        "multiple_devices",
                        "batch_failed",
                        {"error": str(e)}
                    )
            elif self.api_key:
                try:
                    # Using FCM HTTP v1 API for multicast messages
                    success_count = 0
                    failure_count = 0
                    device_results = []
                    
                    # Process in batches of 100 (FCM limit)
                    batch_size = 100
                    
                    for i in range(0, len(device_tokens), batch_size):
                        batch = device_tokens[i:i+batch_size]
                        
                        # If there's only one device in the batch, send as single
                        if len(batch) == 1:
                            device = batch[0]
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
                            
                            # Send individual message
                            message = self._prepare_fcm_message(token, title, body, data, high_priority)
                            
                            # Set up the HTTP request
                            headers = {
                                "Content-Type": "application/json",
                                "Authorization": f"key={self.api_key}"
                            }
                            
                            # Send the request
                            try:
                                response = requests.post(self.api_url, headers=headers, data=json.dumps(message))
                                response_data = response.json()
                                
                                if response.status_code == 200 and response_data.get("success", 0) >= 1:
                                    success_count += 1
                                    device_results.append({
                                        "device_id": device_id,
                                        "success": True,
                                        "message_id": response_data.get("multicast_id")
                                    })
                                    
                                    # Log success
                                    self._log_notification_event(
                                        "send",
                                        notification_id,
                                        user_id,
                                        device_id,
                                        "sent",
                                        {"message_id": response_data.get("multicast_id")}
                                    )
                                else:
                                    failure_count += 1
                                    device_results.append({
                                        "device_id": device_id,
                                        "success": False,
                                        "error": response.text,
                                        "error_code": response.status_code
                                    })
                                    
                                    # Log error
                                    self._log_notification_event(
                                        "error",
                                        notification_id,
                                        user_id,
                                        device_id,
                                        "send_failed",
                                        {"error": response.text, "error_code": response.status_code}
                                    )
                            except requests.RequestException as e:
                                failure_count += 1
                                device_results.append({
                                    "device_id": device_id,
                                    "success": False,
                                    "error": str(e)
                                })
                                
                                # Log error
                                self._log_notification_event(
                                    "error",
                                    notification_id,
                                    user_id,
                                    device_id,
                                    "request_failed",
                                    {"error": str(e)}
                                )
                        else:
                            # Send to multiple registration_ids
                            tokens = [device.get("token") for device in batch if device.get("token")]
                            device_ids = {device.get("token"): device.get("device_id", "unknown") for device in batch if device.get("token")}
                            
                            if not tokens:
                                continue
                            
                            # Prepare multicast message
                            message = {
                                "registration_ids": tokens,
                                "notification": {
                                    "title": title,
                                    "body": body,
                                    "sound": "default"
                                },
                                "priority": "high" if high_priority else "normal"
                            }
                            
                            # Add data payload if provided
                            if data:
                                # Ensure all values are strings for FCM
                                string_data = {}
                                for key, value in data.items():
                                    if isinstance(value, (dict, list)):
                                        string_data[key] = json.dumps(value)
                                    else:
                                        string_data[key] = str(value)
                                
                                message["data"] = string_data
                            
                            # Set up the HTTP request
                            headers = {
                                "Content-Type": "application/json",
                                "Authorization": f"key={self.api_key}"
                            }
                            
                            # Send the request
                            try:
                                response = requests.post(self.api_url, headers=headers, data=json.dumps(message))
                                response_data = response.json()
                                
                                if response.status_code == 200:
                                    # Process results
                                    success_count += response_data.get("success", 0)
                                    failure_count += response_data.get("failure", 0)
                                    
                                    # Map results to devices
                                    results = response_data.get("results", [])
                                    for i, result_item in enumerate(results):
                                        if i >= len(tokens):
                                            break
                                            
                                        token = tokens[i]
                                        device_id = device_ids.get(token, "unknown")
                                        
                                        if "message_id" in result_item:
                                            device_results.append({
                                                "device_id": device_id,
                                                "success": True,
                                                "message_id": result_item.get("message_id")
                                            })
                                            
                                            # Log success
                                            self._log_notification_event(
                                                "send",
                                                notification_id,
                                                user_id,
                                                device_id,
                                                "sent",
                                                {"message_id": result_item.get("message_id")}
                                            )
                                        else:
                                            error = result_item.get("error", "Unknown error")
                                            device_results.append({
                                                "device_id": device_id,
                                                "success": False,
                                                "error": error
                                            })
                                            
                                            # Log error
                                            self._log_notification_event(
                                                "error",
                                                notification_id,
                                                user_id,
                                                device_id,
                                                "send_failed",
                                                {"error": error}
                                            )
                                else:
                                    # Failed to send batch
                                    failure_count += len(tokens)
                                    
                                    for token in tokens:
                                        device_id = device_ids.get(token, "unknown")
                                        device_results.append({
                                            "device_id": device_id,
                                            "success": False,
                                            "error": response.text,
                                            "error_code": response.status_code
                                        })
                                        
                                        # Log error
                                        self._log_notification_event(
                                            "error",
                                            notification_id,
                                            user_id,
                                            device_id,
                                            "batch_failed",
                                            {"error": response.text, "error_code": response.status_code}
                                        )
                            except requests.RequestException as e:
                                # Failed to send batch
                                failure_count += len(tokens)
                                
                                for token in tokens:
                                    device_id = device_ids.get(token, "unknown")
                                    device_results.append({
                                        "device_id": device_id,
                                        "success": False,
                                        "error": str(e)
                                    })
                                    
                                    # Log error
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
                    result["message"] = f"FCM HTTP API error: {str(e)}"
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        "multiple_devices",
                        "batch_failed",
                        {"error": str(e)}
                    )
            else:
                result["message"] = "No FCM credentials available"
                
                # Log error with secure audit trail
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    "multiple_devices",
                    "no_credentials",
                    {"error": "No FCM credentials available"}
                )
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
        FCM doesn't provide a delivery status API, so this relies on app-side delivery confirmation.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            
        Returns:
            Dict: Status information
        """
        # FCM doesn't provide a direct way to get delivery status,
        # this would typically be implemented with app-side delivery receipts
        
        # Return a response indicating this limitation
        result = {
            "provider": "fcm",
            "notification_id": notification_id,
            "user_id": user_id,
            "device_id": device_id,
            "status": "unknown",
            "message": "FCM does not provide delivery status API. Status must be tracked with app-side delivery receipts."
        }
        
        # Log the status check
        self._log_notification_event(
            "status_check",
            notification_id,
            user_id,
            device_id,
            "unavailable",
            {"message": "FCM does not provide delivery status API"}
        )
        
        return result
