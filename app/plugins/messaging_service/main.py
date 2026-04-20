"""
Messaging Service Plugin

A comprehensive messaging service for user-to-user communication within the KAAPI application.
Features include direct messaging, group chats, file sharing, message encryption, and real-time
notifications.
"""
import logging
import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.config import settings

# Initialize router
router = APIRouter()

logger = logging.getLogger(__name__)


class MessagingService:
    """
    Messaging Service Plugin main class that handles initialization,
    configuration and provides core messaging functionalities.
    """
    
    def __init__(self):
        """Initialize the messaging service plugin."""
        self.router = APIRouter()
        self.encryption_handler = None
        self.security_handler = None
        self.notification_handler = None
        self.file_handler = None
        self.websocket_manager = None
        self._is_initialized = False
        
        # Default configuration values
        self.config = {
            "max_message_length": 5000,
            "max_file_size_mb": 20,
            "allowed_file_types": ["image/jpeg", "image/png", "image/gif", "application/pdf", 
                                 "text/plain", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
            "message_retention_days": 365,
            "encryption_enabled": True,
            "delivery_receipts_enabled": True,
            "read_receipts_enabled": True,
            "typing_indicators_enabled": True,
            "message_reactions_enabled": True,
            "group_chats_enabled": True,
            "max_group_members": 100,
            "message_search_enabled": True,
            "message_editing_enabled": True,
            "message_deletion_enabled": True,
            "message_forwarding_enabled": True,
            "message_translation_enabled": False,
            "profanity_filter_enabled": True,
            "spam_filter_enabled": True,
            "attachment_preview_enabled": True
        }
    
    def init_app(self, app, prefix: str = "/messaging", encryption_handler=None):
        """
        Initialize the plugin with the main application.
        
        Args:
            app: FastAPI application instance
            prefix: API route prefix
            encryption_handler: Application's encryption handler for securing messages
        """
        if self._is_initialized:
            logger.warning("Messaging service plugin already initialized")
            return
            
        # Store encryption handler
        self.encryption_handler = encryption_handler
        
        # Initialize sub-modules
        self._init_security_handler()
        self._init_notification_handler()
        self._init_file_handler()
        self._init_websocket_manager()
        
        # Setup routes
        self._setup_routes()
        
        # Register routes with the application
        app.include_router(self.router, prefix=prefix, tags=["Messaging"])
        
        # Initialize scheduled tasks
        self._init_scheduled_tasks()
        
        logger.info("Messaging service plugin initialized")
        self._is_initialized = True
        
    def _init_security_handler(self):
        """Initialize the security handler for message encryption and security."""
        from .utils.security import MessageSecurity
        self.security_handler = MessageSecurity(self.encryption_handler)
        logger.info("Messaging security handler initialized")
        
    def _init_notification_handler(self):
        """Initialize the notification handler for message notifications."""
        from .utils.notifications import NotificationHandler
        self.notification_handler = NotificationHandler()
        logger.info("Messaging notification handler initialized")
        
    def _init_file_handler(self):
        """Initialize the file handler for message attachments."""
        from .utils.file_handler import MessageFileHandler
        self.file_handler = MessageFileHandler(
            max_file_size_mb=self.config["max_file_size_mb"],
            allowed_file_types=self.config["allowed_file_types"]
        )
        logger.info("Messaging file handler initialized")
        
    def _init_websocket_manager(self):
        """Initialize the WebSocket manager for real-time messaging."""
        from .utils.websocket_manager import MessageWebSocketManager
        self.websocket_manager = MessageWebSocketManager()
        logger.info("Messaging WebSocket manager initialized")
        
    def _setup_routes(self):
        """Set up all API routes for the messaging service."""
        # Import our route modules
        from .routes import message_routes, conversation_routes, websocket_routes
        
        # Initialize services
        from .services.message_service import MessageService
        from .services.conversation_service import ConversationService
        
        message_service = MessageService()
        message_service.init_handlers(
            security_handler=self.security_handler,
            file_handler=self.file_handler,
            notification_handler=self.notification_handler
        )
        
        conversation_service = ConversationService()
        conversation_service.init_handlers(
            security_handler=self.security_handler,
            notification_handler=self.notification_handler,
            websocket_manager=self.websocket_manager
        )
        
        # Initialize routes with services
        message_router = message_routes.init_routes(message_service)
        conversation_router = conversation_routes.init_routes(conversation_service)
        websocket_router = websocket_routes.init_routes(message_service)
        
        # Include all routers
        self.router.include_router(message_router)
        self.router.include_router(conversation_router)
        self.router.include_router(websocket_router)
        
        logger.info("Messaging routes configured")
        
    def _init_scheduled_tasks(self):
        """Initialize scheduled tasks for the messaging service."""
        from .tasks.scheduler import initialize_scheduled_tasks
        initialize_scheduled_tasks()
        logger.info("Messaging scheduled tasks initialized")
        
    def update_config(self, new_config: Dict[str, Any]):
        """
        Update plugin configuration.
        
        Args:
            new_config: Dictionary containing new configuration values
        """
        for key, value in new_config.items():
            if key in self.config:
                self.config[key] = value
                
        logger.info("Messaging configuration updated", extra={"updated_keys": list(new_config.keys())})
        
    def get_config(self) -> Dict[str, Any]:
        """
        Get current plugin configuration.
        
        Returns:
            Dictionary containing current configuration values
        """
        return self.config
        
    def encrypt_message(self, message_content: str, recipient_id: str) -> str:
        """
        Encrypt a message for secure transmission.
        
        Args:
            message_content: Plain text message content
            recipient_id: Recipient user ID
            
        Returns:
            Encrypted message content
        """
        if not self.config["encryption_enabled"] or not self.security_handler:
            return message_content
            
        return self.security_handler.encrypt_message(message_content, recipient_id)
        
    def decrypt_message(self, encrypted_content: str, user_id: str) -> str:
        """
        Decrypt a message for the recipient.
        
        Args:
            encrypted_content: Encrypted message content
            user_id: User ID of the recipient
            
        Returns:
            Decrypted message content
        """
        if not self.config["encryption_enabled"] or not self.security_handler:
            return encrypted_content
            
        return self.security_handler.decrypt_message(encrypted_content, user_id)


# Create singleton instance
messaging_service = MessagingService()

# Function pour être compatible avec le gestionnaire de plugins
def get_router():
    """
    Retourne le routeur du service de messagerie.
    Cette fonction est nécessaire pour que le plugin soit correctement chargé 
    par le gestionnaire de plugins.
    """
    if not messaging_service._is_initialized:
        # Initialiser les handlers nécessaires mais sans attacher le routeur à l'app
        messaging_service._init_security_handler()
        messaging_service._init_notification_handler()
        messaging_service._init_file_handler()
        messaging_service._init_websocket_manager()
        messaging_service._setup_routes()
        messaging_service._is_initialized = True
        
    return messaging_service.router

messaging_service_router = get_router()