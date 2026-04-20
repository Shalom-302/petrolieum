"""
Web Push Provider for Push Notifications

This module implements the Web Push provider for push notifications,
following the standardized security approach across all providers.
"""

import logging
import json
import uuid
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
import importlib
import os

import requests
from pywebpush import webpush, WebPushException

from app.plugins.push_notifications.providers.base_provider import BasePushProvider
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler

logger = logging.getLogger(__name__)

class WebPushProvider(BasePushProvider):
    """
    Web Push provider for browser notifications,
    implementing the standardized security approach.
    """
    
    def __init__(self, security_handler: SecurityHandler):
        """
        Initialize the Web Push provider.
        
        Args:
            security_handler: Security handler for encryption and validation
        """
        super().__init__("web_push", security_handler)
        self.vapid_private_key = None
        self.vapid_public_key = None
        self.vapid_claims = None
        
        # Check if pwa_support module is available and enabled
        self.pwa_support_enabled = False
        self.pwa_push_service = None
        
        try:
            # Check if PWA support is enabled via environment variable
            pwa_enabled = os.environ.get("PWA_SUPPORT_ENABLED", "false").lower() == "true"
            
            if pwa_enabled:
                # Try to import the push_service module
                push_service_module = importlib.import_module("app.plugins.pwa_support.push_service")
                
                # Try to get the PushService class
                if hasattr(push_service_module, "PushService"):
                    self.pwa_push_service = push_service_module.PushService()
                    self.pwa_support_enabled = True
                    logger.info("Web Push provider initialized with PWA support integration")
                else:
                    logger.warning("PWA support enabled but PushService class not found")
            else:
                logger.info("PWA support not enabled, using native Web Push implementation")
        except ImportError:
            logger.info("PWA support module not available, using native Web Push implementation")
        except Exception as e:
            logger.warning(f"Error initializing PWA support integration: {str(e)}")
        
        if not self.pwa_support_enabled:
            logger.info("Web Push provider initialized with native implementation")

    def initialize(self, vapid_private_key: str, vapid_public_key: str, 
                  vapid_claims_email: str, vapid_claims_sub: str = None) -> bool:
        """
        Initialize the Web Push provider with VAPID credentials.
        
        Args:
            vapid_private_key: VAPID private key
            vapid_public_key: VAPID public key
            vapid_claims_email: Email for VAPID claims
            vapid_claims_sub: Subject for VAPID claims (website URL)
            
        Returns:
            bool: Success status
        """
        try:
            super().initialize()
            
            # Validate credentials
            if not all([vapid_private_key, vapid_public_key, vapid_claims_email]):
                logger.error("Web Push initialization failed: Missing required credentials")
                return False
            
            # Store credentials securely
            self.vapid_private_key = self.security_handler.encrypt_data({
                "vapid_private_key": vapid_private_key
            })
            
            self.vapid_public_key = vapid_public_key
            
            # Prepare VAPID claims
            if not vapid_claims_sub:
                vapid_claims_sub = f"mailto:{vapid_claims_email}"
            elif not vapid_claims_sub.startswith(("https://", "mailto:")):
                vapid_claims_sub = f"https://{vapid_claims_sub}"
            
            self.vapid_claims = {
                "sub": vapid_claims_sub
            }
            
            # Initialize PWA support if available
            if self.pwa_support_enabled and self.pwa_push_service:
                try:
                    # Use the same VAPID credentials for the PWA support module
                    self.pwa_push_service.initialize_vapid(
                        private_key=vapid_private_key,
                        public_key=vapid_public_key,
                        claims_email=vapid_claims_email,
                        claims_sub=vapid_claims_sub
                    )
                    logger.info("PWA support push service initialized with shared VAPID credentials")
                except Exception as e:
                    logger.error(f"Failed to initialize PWA support push service: {str(e)}")
                    # If PWA initialization fails, we'll fall back to the native implementation
                    self.pwa_support_enabled = False
            
            # Log successful initialization with secure audit trail
            self._log_notification_event(
                "provider_init",
                str(uuid.uuid4()),
                "system",
                "system",
                "success",
                {"provider": "web_push", "claims_sub": vapid_claims_sub, "pwa_support": self.pwa_support_enabled}
            )
            
            logger.info(f"Web Push provider initialized successfully (PWA support: {self.pwa_support_enabled})")
            return True
        except Exception as e:
            logger.error(f"Web Push initialization error: {str(e)}")
            
            # Log initialization failure
            self._log_notification_event(
                "provider_init",
                str(uuid.uuid4()),
                "system",
                "system",
                "error",
                {"provider": "web_push", "error": str(e)}
            )
            
            return False
    
    def send_notification(self, notification_id: str, user_id: str, device_id: str, 
                         subscription_info: Dict[str, Any], title: str, body: str, 
                         data: Dict[str, Any] = None, high_priority: bool = False,
                         icon: str = None, badge: str = None, 
                         tag: str = None, ttl: int = 86400) -> Dict[str, Any]:
        """
        Send a Web Push notification.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            subscription_info: Web Push subscription information
            title: Notification title
            body: Notification body
            data: Custom data payload
            high_priority: Whether to use high priority
            icon: URL of the icon to display
            badge: URL of the badge to display
            tag: Tag for replacing notifications
            ttl: Time to live in seconds
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "web_push",
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
            
            # Validate subscription info
            if not subscription_info or not isinstance(subscription_info, dict):
                error_message = "Invalid subscription information"
                result["message"] = error_message
                
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    device_id,
                    "invalid_subscription",
                    {"error": error_message}
                )
                
                return result
            
            required_fields = ["endpoint", "keys"]
            if not all(field in subscription_info for field in required_fields):
                error_message = "Missing required fields in subscription info"
                result["message"] = error_message
                
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    device_id,
                    "invalid_subscription",
                    {"error": error_message}
                )
                
                return result
            
            # If PWA support is enabled, use it for sending notifications
            if self.pwa_support_enabled and self.pwa_push_service:
                return self._send_with_pwa_support(
                    notification_id=notification_id,
                    user_id=user_id,
                    device_id=device_id,
                    subscription_info=subscription_info,
                    title=title,
                    body=body,
                    data=data,
                    high_priority=high_priority,
                    icon=icon,
                    badge=badge,
                    tag=tag,
                    ttl=ttl
                )
            
            # Get private key for native implementation
            private_key = self._get_private_key()
            if not private_key:
                error_message = "Failed to get VAPID private key"
                result["message"] = error_message
                
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    device_id,
                    "credentials_error",
                    {"error": error_message}
                )
                
                return result
            
            # Prepare payload
            payload = self._prepare_web_push_payload(
                title=title,
                body=body,
                data=data,
                icon=icon,
                badge=badge,
                tag=tag
            )
            
            # Convert payload to JSON
            json_payload = json.dumps(payload)
            
            try:
                # Send the Web Push notification
                response = webpush(
                    subscription_info=subscription_info,
                    data=json_payload,
                    vapid_private_key=private_key,
                    vapid_claims=self.vapid_claims.copy(),
                    ttl=ttl
                )
                
                # Check response
                if response.status_code >= 200 and response.status_code < 300:
                    result["success"] = True
                    result["status"] = "sent"
                    result["message"] = "Notification sent successfully"
                    result["details"] = {
                        "status_code": response.status_code,
                        "headers": dict(response.headers)
                    }
                    
                    # Log success with secure audit trail
                    self._log_notification_event(
                        "send",
                        notification_id,
                        user_id,
                        device_id,
                        "sent",
                        {"status_code": response.status_code}
                    )
                else:
                    error_message = f"Web Push error: HTTP {response.status_code}"
                    result["message"] = error_message
                    result["details"] = {
                        "status_code": response.status_code,
                        "response": response.text
                    }
                    
                    # Check for subscription expiration
                    if response.status_code == 410:
                        result["status"] = "subscription_expired"
                    else:
                        result["status"] = "error"
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        device_id,
                        result["status"],
                        {"error": error_message, "response": response.text}
                    )
            except WebPushException as e:
                error_message = f"Web Push exception: {str(e)}"
                result["message"] = error_message
                
                # Check if it's a subscription expiration
                if hasattr(e, 'response') and e.response and e.response.status_code == 410:
                    result["status"] = "subscription_expired"
                    result["details"] = {"status_code": 410}
                else:
                    result["details"] = {
                        "error": str(e),
                        "status_code": e.response.status_code if hasattr(e, 'response') and e.response else None
                    }
                
                # Log error with secure audit trail
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    device_id,
                    result["status"],
                    {"error": error_message}
                )
            
            return result
        except Exception as e:
            error_message = f"Error sending Web Push notification: {str(e)}"
            result["message"] = error_message
            result["details"] = {"error": str(e)}
            
            # Log error with secure audit trail
            self._log_notification_event(
                "error",
                notification_id,
                user_id,
                device_id,
                "system_error",
                {"error": error_message}
            )
            
            return result
    
    def _send_with_pwa_support(self, notification_id: str, user_id: str, device_id: str, 
                              subscription_info: Dict[str, Any], title: str, body: str, 
                              data: Dict[str, Any] = None, high_priority: bool = False,
                              icon: str = None, badge: str = None, 
                              tag: str = None, ttl: int = 86400) -> Dict[str, Any]:
        """
        Send a Web Push notification using the PWA support module.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            subscription_info: Web Push subscription information
            title: Notification title
            body: Notification body
            data: Custom data payload
            high_priority: Whether to use high priority
            icon: URL of the icon to display
            badge: URL of the badge to display
            tag: Tag for replacing notifications
            ttl: Time to live in seconds
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "web_push",
            "notification_id": notification_id,
            "user_id": user_id,
            "device_id": device_id,
            "success": False,
            "status": "failed",
            "message": "",
            "details": {}
        }
        
        try:
            # Prepare options for PWA push service
            options = {
                "notification": {
                    "title": title,
                    "body": body
                }
            }
            
            # Add optional notification parameters
            if icon:
                options["notification"]["icon"] = icon
            
            if badge:
                options["notification"]["badge"] = badge
            
            if tag:
                options["notification"]["tag"] = tag
            
            # Add data payload if provided
            if data:
                options["data"] = data
            
            # Log attempt with secure audit trail
            self._log_notification_event(
                "send_attempt",
                notification_id,
                user_id,
                device_id,
                "using_pwa_support",
                {}
            )
            
            # Send notification using PWA support
            pwa_result = self.pwa_push_service.send_notification(
                subscription=subscription_info,
                payload=options,
                ttl=ttl
            )
            
            # Translate PWA support result to our format
            if pwa_result.get("success", False):
                result["success"] = True
                result["status"] = "sent"
                result["message"] = "Notification sent successfully via PWA support"
                result["details"] = pwa_result
                
                # Log success with secure audit trail
                self._log_notification_event(
                    "send",
                    notification_id,
                    user_id,
                    device_id,
                    "sent",
                    {"via": "pwa_support"}
                )
            else:
                error_message = pwa_result.get("error", "Unknown error")
                result["message"] = f"PWA support error: {error_message}"
                result["details"] = pwa_result
                
                # Check for subscription expiration
                if "expired" in error_message.lower() or "not found" in error_message.lower():
                    result["status"] = "subscription_expired"
                else:
                    result["status"] = "error"
                
                # Log error with secure audit trail
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    device_id,
                    result["status"],
                    {"error": error_message, "via": "pwa_support"}
                )
            
            return result
        except Exception as e:
            error_message = f"Error sending notification via PWA support: {str(e)}"
            result["message"] = error_message
            result["details"] = {"error": str(e)}
            
            # Log error with secure audit trail
            self._log_notification_event(
                "error",
                notification_id,
                user_id,
                device_id,
                "pwa_support_error",
                {"error": error_message}
            )
            
            # Fall back to native implementation
            logger.warning(f"PWA support error, falling back to native implementation: {error_message}")
            
            # Temporarily disable PWA support for this call
            original_pwa_enabled = self.pwa_support_enabled
            self.pwa_support_enabled = False
            
            try:
                # Call send_notification again, which will now use the native implementation
                result = self.send_notification(
                    notification_id=notification_id,
                    user_id=user_id,
                    device_id=device_id,
                    subscription_info=subscription_info,
                    title=title,
                    body=body,
                    data=data,
                    high_priority=high_priority,
                    icon=icon,
                    badge=badge,
                    tag=tag,
                    ttl=ttl
                )
                
                # Add fallback information to the result
                result["details"]["fallback"] = "Used native implementation after PWA support failure"
                
                return result
            finally:
                # Restore the original PWA support setting
                self.pwa_support_enabled = original_pwa_enabled
    
    def _get_private_key(self) -> Optional[str]:
        """
        Get the decrypted VAPID private key.
        
        Returns:
            str: Decrypted private key or None on error
        """
        try:
            if not self.vapid_private_key:
                logger.error("No VAPID private key available")
                return None
            
            decrypted_data = self.security_handler.decrypt_data(self.vapid_private_key)
            private_key = decrypted_data.get("vapid_private_key")
            
            if not private_key:
                logger.error("Failed to decrypt VAPID private key")
                return None
            
            return private_key
        except Exception as e:
            logger.error(f"Error getting VAPID private key: {str(e)}")
            return None
    
    def _prepare_web_push_payload(self, title: str, body: str, data: Dict[str, Any] = None,
                                icon: str = None, badge: str = None, image: str = None,
                                tag: str = None, renotify: bool = False,
                                require_interaction: bool = False,
                                silent: bool = False, actions: List[Dict[str, str]] = None,
                                timestamp: int = None, vibrate: List[int] = None,
                                dir: str = None, lang: str = None) -> Dict[str, Any]:
        """
        Prepare the Web Push notification payload.
        
        Args:
            title: Notification title
            body: Notification body
            data: Custom data payload
            icon: URL of the icon to display
            badge: URL of the badge to display
            image: URL of the image to display
            tag: Tag for replacing notifications
            renotify: Whether to notify again if replacing
            require_interaction: Whether to require user interaction
            silent: Whether to show without sound
            actions: Action buttons
            timestamp: Notification timestamp
            vibrate: Vibration pattern
            dir: Text direction
            lang: Language code
            
        Returns:
            Dict: Web Push notification payload
        """
        # Build the payload according to the Web Push standard
        payload = {
            "notification": {
                "title": title,
                "body": body
            }
        }
        
        # Add optional notification parameters
        notification = payload["notification"]
        
        if icon:
            notification["icon"] = icon
        
        if badge:
            notification["badge"] = badge
        
        if image:
            notification["image"] = image
        
        if tag:
            notification["tag"] = tag
            
        if renotify:
            notification["renotify"] = True
            
        if require_interaction:
            notification["requireInteraction"] = True
            
        if silent:
            notification["silent"] = True
            
        if actions:
            notification["actions"] = actions
            
        if timestamp:
            notification["timestamp"] = timestamp
            
        if vibrate:
            notification["vibrate"] = vibrate
            
        if dir:
            notification["dir"] = dir
            
        if lang:
            notification["lang"] = lang
        
        # Add custom data
        if data:
            payload["data"] = data
        
        return payload
    
    def get_public_key(self) -> str:
        """
        Get the VAPID public key for client-side subscription.
        
        Returns:
            str: VAPID public key
        """
        return self.vapid_public_key
    
    def get_delivery_status(self, notification_id: str, user_id: str, device_id: str) -> Dict[str, Any]:
        """
        Get the delivery status of a notification.
        Web Push doesn't provide a delivery status API, so this relies on app-side delivery confirmation.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_id: ID of the device
            
        Returns:
            Dict: Status information
        """
        # Web Push doesn't provide a direct way to get delivery status,
        # this would typically be implemented with app-side delivery receipts
        
        # Return a response indicating this limitation
        result = {
            "provider": "web_push",
            "notification_id": notification_id,
            "user_id": user_id,
            "device_id": device_id,
            "status": "unknown",
            "message": "Web Push does not provide delivery status API. Status must be tracked with app-side delivery receipts."
        }
        
        # Log the status check
        self._log_notification_event(
            "status_check",
            notification_id,
            user_id,
            device_id,
            "unavailable",
            {"message": "Web Push does not provide delivery status API"}
        )
        
        return result

    def send_to_multiple_devices(self, notification_id: str, user_id: str, 
                               device_subscriptions: List[Dict[str, Any]], title: str, 
                               body: str, data: Dict[str, Any] = None, 
                               high_priority: bool = False, icon: str = None,
                               badge: str = None, tag: str = None,
                               ttl: int = 86400) -> Dict[str, Any]:
        """
        Send a Web Push notification to multiple devices.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user
            device_subscriptions: List of device subscriptions with device IDs
            title: Notification title
            body: Notification body
            data: Custom data payload
            high_priority: Whether to use high priority
            icon: URL of the icon to display
            badge: URL of the badge to display
            tag: Tag for replacing notifications
            ttl: Time to live in seconds
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "web_push",
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
            
            # Get private key
            private_key = self._get_private_key()
            if not private_key:
                error_message = "Failed to get VAPID private key"
                result["message"] = error_message
                
                self._log_notification_event(
                    "error",
                    notification_id,
                    user_id,
                    "multiple_devices",
                    "credentials_error",
                    {"error": error_message}
                )
                
                return result
            
            # Prepare payload
            payload = self._prepare_web_push_payload(
                title=title,
                body=body,
                data=data,
                icon=icon,
                badge=badge,
                tag=tag
            )
            
            # Convert payload to JSON
            json_payload = json.dumps(payload)
            
            # Send to each device
            success_count = 0
            failure_count = 0
            device_results = []
            
            for device in device_subscriptions:
                device_id = device.get("device_id", "unknown")
                subscription_info = device.get("subscription")
                
                if not subscription_info:
                    device_results.append({
                        "device_id": device_id,
                        "success": False,
                        "message": "No subscription information provided"
                    })
                    failure_count += 1
                    continue
                
                # Validate subscription
                required_fields = ["endpoint", "keys"]
                if not all(field in subscription_info for field in required_fields):
                    device_results.append({
                        "device_id": device_id,
                        "success": False,
                        "message": "Missing required fields in subscription info"
                    })
                    failure_count += 1
                    continue
                
                try:
                    # Send the Web Push notification
                    response = webpush(
                        subscription_info=subscription_info,
                        data=json_payload,
                        vapid_private_key=private_key,
                        vapid_claims=self.vapid_claims.copy(),
                        ttl=ttl
                    )
                    
                    # Check response
                    if response.status_code >= 200 and response.status_code < 300:
                        success_count += 1
                        device_results.append({
                            "device_id": device_id,
                            "success": True,
                            "message": "Notification sent successfully",
                            "status_code": response.status_code
                        })
                        
                        # Log success with secure audit trail
                        self._log_notification_event(
                            "send",
                            notification_id,
                            user_id,
                            device_id,
                            "sent",
                            {"status_code": response.status_code}
                        )
                    else:
                        failure_count += 1
                        
                        # Check for subscription expiration
                        if response.status_code == 410:
                            status = "subscription_expired"
                        else:
                            status = "error"
                        
                        device_results.append({
                            "device_id": device_id,
                            "success": False,
                            "message": f"Web Push error: HTTP {response.status_code}",
                            "status": status,
                            "status_code": response.status_code,
                            "response": response.text
                        })
                        
                        # Log error with secure audit trail
                        self._log_notification_event(
                            "error",
                            notification_id,
                            user_id,
                            device_id,
                            status,
                            {"error": f"HTTP {response.status_code}", "response": response.text}
                        )
                except WebPushException as e:
                    failure_count += 1
                    
                    # Check if it's a subscription expiration
                    if hasattr(e, 'response') and e.response and e.response.status_code == 410:
                        status = "subscription_expired"
                    else:
                        status = "error"
                    
                    status_code = e.response.status_code if hasattr(e, 'response') and e.response else None
                    
                    device_results.append({
                        "device_id": device_id,
                        "success": False,
                        "message": f"Web Push exception: {str(e)}",
                        "status": status,
                        "status_code": status_code,
                        "error": str(e)
                    })
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        device_id,
                        status,
                        {"error": str(e), "status_code": status_code}
                    )
                except Exception as e:
                    failure_count += 1
                    
                    device_results.append({
                        "device_id": device_id,
                        "success": False,
                        "message": f"Unexpected error: {str(e)}",
                        "error": str(e)
                    })
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        user_id,
                        device_id,
                        "exception",
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

    def send_to_segment(self, notification_id: str, segment_id: int, title: str, body: str, 
                      data: Dict[str, Any] = None, high_priority: bool = False, icon: str = None,
                      badge: str = None, tag: str = None, ttl: int = 86400) -> Dict[str, Any]:
        """
        Send a Web Push notification to all devices in a specific segment.
        
        Args:
            notification_id: ID of the notification
            segment_id: ID of the segment to send to
            title: Notification title
            body: Notification body
            data: Custom data payload
            high_priority: Whether to use high priority
            icon: URL of the icon to display
            badge: URL of the badge to display
            tag: Tag for replacing notifications
            ttl: Time to live in seconds
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "web_push",
            "notification_id": notification_id,
            "segment_id": segment_id,
            "success": False,
            "status": "failed",
            "total_devices": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "message": "",
            "details": {}
        }
        
        try:
            # Import here to avoid circular imports
            from app.plugins.push_notifications.services.segment_service import get_segment, get_segment_devices
            from app.database.session import SessionLocal
            
            # Create a database session
            db = SessionLocal()
            try:
                # Get the segment
                segment = get_segment(db, segment_id)
                if not segment:
                    error_message = f"Segment with ID {segment_id} not found"
                    result["message"] = error_message
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        "segment",
                        str(segment_id),
                        "segment_not_found",
                        {"error": error_message}
                    )
                    
                    return result
                
                # Validate the notification payload
                if not self._validate_payload(title, body, data or {}):
                    error_message = "Notification payload validation failed"
                    result["message"] = error_message
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        "segment",
                        str(segment_id),
                        "validation_failed",
                        {"error": error_message}
                    )
                    
                    return result
                
                # Log the operation using secure approach
                self.security_handler.log_secure_operation(
                    "send_to_segment", 
                    f"Sending notification {notification_id} to segment '{segment.name}' (ID: {segment_id})"
                )
                
                # Check for PWA support
                if self.pwa_support_enabled and self.pwa_push_service:
                    return self._send_to_segment_with_pwa_support(
                        notification_id=notification_id,
                        segment=segment,
                        title=title,
                        body=body,
                        data=data,
                        high_priority=high_priority,
                        icon=icon,
                        badge=badge,
                        tag=tag,
                        ttl=ttl
                    )
                
                # Process segment devices in batches
                batch_size = 50
                offset = 0
                total_devices = 0
                successful_deliveries = 0
                
                while True:
                    # Get a batch of devices
                    devices = get_segment_devices(db, segment_id, skip=offset, limit=batch_size)
                    if not devices:
                        break
                    
                    total_devices += len(devices)
                    
                    # Process each device in the batch
                    for device in devices:
                        # Skip non-web devices
                        if device.device_type.value != "web":
                            continue
                        
                        # Get subscription info from device token
                        try:
                            subscription_info = json.loads(device.token)
                        except json.JSONDecodeError:
                            # Log error and skip
                            self._log_notification_event(
                                "error",
                                notification_id,
                                device.user_id,
                                str(device.id),
                                "invalid_subscription",
                                {"error": "Invalid subscription format"}
                            )
                            continue
                        
                        # Send notification to this device
                        device_result = self.send_notification(
                            notification_id=notification_id,
                            user_id=device.user_id,
                            device_id=str(device.id),
                            subscription_info=subscription_info,
                            title=title,
                            body=body,
                            data=data,
                            high_priority=high_priority,
                            icon=icon,
                            badge=badge,
                            tag=tag,
                            ttl=ttl
                        )
                        
                        if device_result.get("success", False):
                            successful_deliveries += 1
                    
                    # Move to next batch
                    offset += batch_size
                
                # Update result with summary
                result["success"] = successful_deliveries > 0
                result["status"] = "partial_success" if successful_deliveries > 0 else "failed"
                if total_devices == 0:
                    result["status"] = "no_devices"
                    result["message"] = "No devices found in segment"
                elif successful_deliveries == total_devices:
                    result["status"] = "success"
                    result["message"] = f"Successfully sent to all {total_devices} devices in segment"
                else:
                    result["message"] = f"Sent to {successful_deliveries} out of {total_devices} devices in segment"
                
                result["total_devices"] = total_devices
                result["successful_deliveries"] = successful_deliveries
                result["failed_deliveries"] = total_devices - successful_deliveries
                
                # Log final result with secure audit trail
                self._log_notification_event(
                    "segment_notification",
                    notification_id,
                    "segment",
                    str(segment_id),
                    result["status"],
                    {
                        "segment_name": segment.name,
                        "total_devices": total_devices,
                        "successful": successful_deliveries,
                        "failed": total_devices - successful_deliveries
                    }
                )
                
                return result
                
            finally:
                db.close()
        except Exception as e:
            error_message = f"Error sending to segment: {str(e)}"
            result["message"] = error_message
            result["details"] = {"error": str(e)}
            
            # Log error with secure audit trail
            self._log_notification_event(
                "error",
                notification_id,
                "segment",
                str(segment_id),
                "system_error",
                {"error": error_message}
            )
            
            return result

    def _send_to_segment_with_pwa_support(self, notification_id: str, segment, title: str, body: str, 
                                         data: Dict[str, Any] = None, high_priority: bool = False,
                                         icon: str = None, badge: str = None, tag: str = None, 
                                         ttl: int = 86400) -> Dict[str, Any]:
        """
        Send a Web Push notification to a segment using the PWA support module.
        
        Args:
            notification_id: ID of the notification
            segment: Segment object to send to
            title: Notification title
            body: Notification body
            data: Custom data payload
            high_priority: Whether to use high priority
            icon: URL of the icon to display
            badge: URL of the badge to display
            tag: Tag for replacing notifications
            ttl: Time to live in seconds
            
        Returns:
            Dict: Result containing status and details
        """
        result = {
            "provider": "web_push",
            "notification_id": notification_id,
            "segment_id": segment.id,
            "success": False,
            "status": "failed",
            "message": "",
            "details": {}
        }
        
        try:
            # Prepare notification data
            notification_data = {
                "title": title,
                "message": body,
                "icon": icon,
                "tag": tag,
                "url": data.get("url") if data else None,
                "ttl": ttl,
                "data": data
            }
            
            # Log the attempt with secure audit trail
            self._log_notification_event(
                "send_attempt",
                notification_id,
                "segment",
                str(segment.id),
                "using_pwa_support",
                {"segment_name": segment.name}
            )
            
            # Import here to avoid circular imports
            from app.database.session import SessionLocal
            
            # Create a database session
            db = SessionLocal()
            try:
                # Create a SegmentedNotificationSend object to pass to PWA support
                from app.plugins.pwa_support.schemas import SegmentedNotificationSend
                
                notification_send = SegmentedNotificationSend(
                    title=title,
                    message=body,
                    icon=icon,
                    tag=tag,
                    url=data.get("url") if data else None,
                    ttl=ttl,
                    segment_id=segment.id
                )
                
                # Send notification using PWA support
                try:
                    sent_count = self.pwa_push_service.send_segmented_notification(
                        db=db,
                        notification=notification_send
                    )
                    
                    # Update result with success
                    result["success"] = sent_count > 0
                    result["status"] = "success" if sent_count > 0 else "no_devices"
                    result["message"] = f"Sent to {sent_count} devices via PWA support"
                    result["details"] = {
                        "sent_count": sent_count,
                        "segment_name": segment.name,
                        "via": "pwa_support"
                    }
                    
                    # Log success with secure audit trail
                    self._log_notification_event(
                        "segment_notification",
                        notification_id,
                        "segment",
                        str(segment.id),
                        result["status"],
                        {"segment_name": segment.name, "sent_count": sent_count, "via": "pwa_support"}
                    )
                    
                except Exception as e:
                    error_message = f"PWA support error: {str(e)}"
                    result["message"] = error_message
                    result["details"] = {"error": str(e), "via": "pwa_support"}
                    
                    # Log error with secure audit trail
                    self._log_notification_event(
                        "error",
                        notification_id,
                        "segment",
                        str(segment.id),
                        "pwa_support_error",
                        {"error": error_message, "segment_name": segment.name}
                    )
            finally:
                db.close()
            
            return result
        except Exception as e:
            error_message = f"Error sending to segment via PWA support: {str(e)}"
            result["message"] = error_message
            result["details"] = {"error": str(e)}
            
            # Log error with secure audit trail
            self._log_notification_event(
                "error",
                notification_id,
                "segment",
                str(segment.id),
                "system_error",
                {"error": error_message}
            )
            
            return result
