"""
Notification Handler for Messaging Service

This module implements notification handling for the messaging service,
including real-time notifications, push notifications, and email notifications.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

# Get main messaging service instance
from ..main import messaging_service

logger = logging.getLogger(__name__)


class NotificationHandler:
    """
    Handler for managing notifications for the messaging service,
    implementing the standardized security approach.
    """
    
    def __init__(self):
        """Initialize the notification handler."""
        self.security_handler = None
        self.websocket_manager = None
    
    def init_handlers(self, security_handler, websocket_manager):
        """
        Initialize handlers after they are available.
        
        Args:
            security_handler: Security handler for secure message handling
            websocket_manager: WebSocket manager for real-time notifications
        """
        self.security_handler = security_handler
        self.websocket_manager = websocket_manager
        logger.info("Notification handler initialized with security and websocket managers")
    
    async def notify_new_message(self, message: Dict[str, Any], recipient_ids: List[str]):
        """
        Send notification for a new message to recipients.
        
        Args:
            message: Message data
            recipient_ids: List of recipient user IDs
        """
        if not self.security_handler:
            logger.warning("Security handler not available, notification may not be secure")
            
        # Create secure notification payload
        payload = self._create_secure_payload(
            event_type="new_message",
            data={
                "message_id": message.get("id"),
                "conversation_id": message.get("conversation_id"),
                "sender_id": message.get("sender_id"),
                "message_type": message.get("message_type"),
                "timestamp": datetime.utcnow().isoformat(),
                # We don't include the actual message content in the notification for security
                "has_attachments": bool(message.get("attachments", []))
            }
        )
        
        # Log the notification using standardized approach
        if self.security_handler:
            self.security_handler.secure_log(
                "Sending new message notification",
                {
                    "recipient_count": len(recipient_ids),
                    "conversation_id": message.get("conversation_id"),
                    "message_id": message.get("id")
                }
            )
        
        # Send real-time notification via WebSocket if available
        if self.websocket_manager:
            for recipient_id in recipient_ids:
                await self.websocket_manager.send_to_user(recipient_id, payload)
        
        # Here we could also integrate with external push notification services
        # or email services for offline users
    
    async def notify_message_status(self, message_id: str, conversation_id: str, 
                                   user_id: str, status: str):
        """
        Send notification about message status change (delivered, read).
        
        Args:
            message_id: ID of the message
            conversation_id: ID of the conversation
            user_id: ID of the user who changed the status
            status: New status ('delivered' or 'read')
        """
        # Create secure payload
        payload = self._create_secure_payload(
            event_type="message_status",
            data={
                "message_id": message_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Log the status update using standardized approach
        if self.security_handler:
            self.security_handler.secure_log(
                f"Message {status} notification",
                {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "user_id": user_id
                }
            )
        
        # Get participants to notify (this would usually come from a database query)
        # For now, just notify the sender of the message
        if self.websocket_manager:
            # In a real implementation, we would query for the sender_id
            # For now, we'll just assume the sender is connected to the websocket
            # await self.websocket_manager.send_to_user(sender_id, payload)
            pass
    
    async def notify_typing_status(self, conversation_id: str, user_id: str, is_typing: bool):
        """
        Send notification about typing status.
        
        Args:
            conversation_id: ID of the conversation
            user_id: ID of the user who is typing
            is_typing: Whether the user is typing or stopped typing
        """
        # Create secure payload
        payload = self._create_secure_payload(
            event_type="typing_status",
            data={
                "conversation_id": conversation_id,
                "user_id": user_id,
                "is_typing": is_typing,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # No need to log every typing notification as it would create too much noise
        
        # Get other participants to notify
        if self.websocket_manager:
            # In a real implementation, we would query for other participants
            # For now, we'll just broadcast to the conversation
            await self.websocket_manager.broadcast_to_conversation(conversation_id, payload, exclude_user_id=user_id)
    
    async def notify_conversation_update(self, conversation_id: str, update_type: str, 
                                       data: Dict[str, Any], user_ids: List[str]):
        """
        Send notification about conversation updates (new member, title change, etc.).
        
        Args:
            conversation_id: ID of the conversation
            update_type: Type of update (e.g., 'member_added', 'title_changed')
            data: Update data
            user_ids: List of user IDs to notify
        """
        # Create secure payload
        payload = self._create_secure_payload(
            event_type="conversation_update",
            data={
                "conversation_id": conversation_id,
                "update_type": update_type,
                "update_data": data,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Log the conversation update using standardized approach
        if self.security_handler:
            self.security_handler.secure_log(
                f"Conversation {update_type} notification",
                {
                    "conversation_id": conversation_id,
                    "recipient_count": len(user_ids)
                }
            )
        
        # Send notification to all recipients
        if self.websocket_manager:
            for user_id in user_ids:
                await self.websocket_manager.send_to_user(user_id, payload)
    
    def _create_secure_payload(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a secure notification payload using the standardized security approach.
        
        Args:
            event_type: Type of event
            data: Event data
            
        Returns:
            Secure notification payload
        """
        payload = {
            "event": event_type,
            "data": data
        }
        
        # Encrypt sensitive data if security handler is available
        if self.security_handler:
            # For particularly sensitive data, we can encrypt it
            if "content" in data:
                # Use the standardized encryption approach
                data["content"] = self.security_handler.encrypt_message(
                    data["content"], 
                    "notification"
                )
        
        return payload
