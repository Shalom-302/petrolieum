"""
WebSocket Manager for Messaging Service

This module implements WebSocket management for real-time messaging,
including connection handling and secure message distribution.
"""
import logging
import json
import asyncio
from typing import Dict, Any, List, Set, Optional
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageWebSocketManager:
    """
    WebSocket manager for real-time messaging, ensuring secure and efficient 
    delivery of messages following the standardized security approach.
    """
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        self.active_connections = {}  # user_id -> conversation_id -> websocket
        self.connection_active = {}  # user_id -> conversation_id -> bool
        self.user_conversations = {}  # user_id -> set of conversation_ids
        self.conversation_users = {}  # conversation_id -> set of user_ids
        self.security_handler = None
    
    def set_security_handler(self, security_handler):
        """
        Set the security handler for secure WebSocket communications.
        
        Args:
            security_handler: Security handler from the messaging service
        """
        self.security_handler = security_handler
        logger.info("WebSocket manager initialized with security handler")
    
    async def connect(self, websocket, user_id: str, conversation_id: str, already_accepted: bool = False):
        """Register a new WebSocket connection for a user in a specific conversation."""
        try:
            if not already_accepted:
                await websocket.accept()
            
            if user_id not in self.active_connections:
                self.active_connections[user_id] = {}
                self.connection_active[user_id] = {}
                
            # Store the connection for this conversation
            self.active_connections[user_id][conversation_id] = websocket
            self.connection_active[user_id][conversation_id] = True
            
            # Maintenir les mappages utilisateur-conversation bidirectionnels
            if user_id not in self.user_conversations:
                self.user_conversations[user_id] = set()
            self.user_conversations[user_id].add(conversation_id)
            
            # Ajouter l'utilisateur à la liste des utilisateurs de la conversation
            if conversation_id not in self.conversation_users:
                self.conversation_users[conversation_id] = set()
            self.conversation_users[conversation_id].add(user_id)
            
            # Log la liste complète des utilisateurs pour debugging
            users_in_conversation = self.conversation_users.get(conversation_id, set())
            logger.info(f"Users in conversation {conversation_id}: {users_in_conversation}")
            
            # Log the connection
            active_users = len(self.active_connections)
            logger.info(f"New WebSocket connection: user_id={user_id}, conversation_id={conversation_id}")
            logger.info(f"Current active users count: {active_users}")
            
            # Log connection securely
            if self.security_handler:
                self.security_handler.secure_log(
                    "WebSocket connection established",
                    {
                        "user_id": user_id,
                        "conversation_id": conversation_id
                    }
                )
            else:
                logger.info(f"WebSocket connection established for user {user_id} in conversation {conversation_id}")
            
            return str(uuid.uuid4())
        except Exception as e:
            logger.error(f"Error in connect: {str(e)}")
            if user_id in self.connection_active and conversation_id in self.connection_active.get(user_id, {}):
                self.connection_active[user_id][conversation_id] = False
            raise
    
    async def disconnect(self, user_id: str, conversation_id: str, connection_id: str = None):
        """
        Remove a WebSocket connection when a user disconnects.
        
        Args:
            user_id: ID of the disconnecting user
            conversation_id: ID of the conversation
            connection_id: ID of the connection to remove (optional)
        """
        logger.info(f"Déconnexion en cours: user_id={user_id}, conversation_id={conversation_id}")
        
        try:
            # Supprimer l'utilisateur de la conversation
            if conversation_id in self.conversation_users:
                if user_id in self.conversation_users[conversation_id]:
                    self.conversation_users[conversation_id].discard(user_id)
                    logger.info(f"Utilisateur {user_id} supprimé de la conversation {conversation_id}")
                
                # Si la conversation n'a plus d'utilisateurs, la supprimer
                if not self.conversation_users[conversation_id]:
                    del self.conversation_users[conversation_id]
                    logger.info(f"Conversation {conversation_id} supprimée car vide")
            
            # Supprimer la conversation des associations de l'utilisateur
            if user_id in self.user_conversations:
                self.user_conversations[user_id].discard(conversation_id)
                logger.info(f"Conversation {conversation_id} supprimée des associations de l'utilisateur {user_id}")
                
                # Si l'utilisateur n'a plus de conversations, le supprimer
                if not self.user_conversations[user_id]:
                    del self.user_conversations[user_id]
                    logger.info(f"Utilisateur {user_id} supprimé car plus de conversations")
            
            # Supprimer la connexion spécifique
            if user_id in self.active_connections:
                if conversation_id in self.active_connections[user_id]:
                    # Fermer la connexion si elle est encore active
                    try:
                        websocket = self.active_connections[user_id][conversation_id]
                        if websocket and hasattr(websocket, 'close'):
                            await websocket.close(code=1000, reason="User disconnected")
                    except Exception as e:
                        logger.error(f"Erreur lors de la fermeture du WebSocket: {str(e)}")
                    
                    # Supprimer la référence à la connexion
                    del self.active_connections[user_id][conversation_id]
                    logger.info(f"Connexion supprimée pour l'utilisateur {user_id} dans la conversation {conversation_id}")
                
                # Si l'utilisateur n'a plus de connexions actives, le supprimer
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    logger.info(f"Utilisateur {user_id} supprimé des connexions actives")
            
            # Mettre à jour l'état de la connexion
            if user_id in self.connection_active and conversation_id in self.connection_active.get(user_id, {}):
                self.connection_active[user_id][conversation_id] = False
            
            # Log disconnection securely
            if self.security_handler:
                self.security_handler.secure_log(
                    "WebSocket connection closed",
                    {
                        "user_id": user_id,
                        "conversation_id": conversation_id
                    }
                )
            else:
                logger.info(f"WebSocket connection closed for user {user_id} in conversation {conversation_id}")
                
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion: {str(e)}")
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """
        Send a message to a specific user on all their active connections.
        
        Args:
            user_id: ID of the user to send to
            message: Message data to send
        """
        if user_id not in self.active_connections:
            logger.warning(f"User {user_id} has no active connections")
            return
            
        # Prepare the message
        message_json = self._prepare_message(message, user_id)
        
        # Get all active conversations for this user
        active_conversations = list(self.active_connections[user_id].keys())
        
        logger.info(f"Sending message to user {user_id} on {len(active_conversations)} connections")
        
        # Send to all active connections for this user
        for conversation_id in active_conversations:
            websocket = self.active_connections[user_id].get(conversation_id)
            
            # Vérifier que la connexion est active
            if not websocket or not self.connection_active.get(user_id, {}).get(conversation_id, False):
                logger.warning(f"Skipping inactive connection for user {user_id} in conversation {conversation_id}")
                continue
                
            try:
                logger.info(f"Sending to user {user_id} in conversation {conversation_id}")
                
                # Vérifier que la connexion est toujours ouverte et valide
                if hasattr(websocket, 'client_state') and websocket.client_state.name == 'DISCONNECTED':
                    logger.warning(f"WebSocket for user {user_id} in conversation {conversation_id} is disconnected")
                    self.connection_active[user_id][conversation_id] = False
                    continue
                
                await websocket.send_text(message_json)
                logger.info(f"Message sent to user {user_id} in conversation {conversation_id}")
            except Exception as e:
                logger.error(f"Error sending to user {user_id} in conversation {conversation_id}: {str(e)}")
                # Marquer la connexion comme inactive
                if user_id in self.connection_active and conversation_id in self.connection_active.get(user_id, {}):
                    self.connection_active[user_id][conversation_id] = False
                
                # Tentative de nettoyage
                try:
                    # Si la connexion est fermée, nettoyons les structures de données
                    if conversation_id in self.active_connections.get(user_id, {}):
                        del self.active_connections[user_id][conversation_id]
                        logger.info(f"Removed closed connection for user {user_id} in conversation {conversation_id}")
                except Exception as cleanup_error:
                    logger.error(f"Error during connection cleanup: {str(cleanup_error)}")
    
    async def broadcast_to_conversation(self, conversation_id: str, message: Dict[str, Any], 
                                       exclude_user_id: Optional[str] = None):
        """
        Broadcast a message to all users in a conversation.
        
        Args:
            conversation_id: ID of the conversation
            message: Message data to send
            exclude_user_id: Optional user ID to exclude from broadcast
        """
        logger.info(f"Broadcasting to conversation {conversation_id}: {message}")
        
        # Vérification des types de données dans le message pour débogage
        if isinstance(message, dict) and "data" in message:
            logger.info(f"Message type: {message.get('type')}")
            data = message.get("data")
            if isinstance(data, dict):
                logger.info(f"Message data structure: {list(data.keys())}")
                logger.info(f"Message data types: {[(k, type(v).__name__) for k, v in data.items()]}")
                
                # Vérifier spécifiquement les champs problématiques
                if "timestamp" in data:
                    logger.info(f"Timestamp type: {type(data['timestamp']).__name__}, Value: {data['timestamp']}")
        
        if conversation_id not in self.conversation_users:
            logger.warning(f"No users found for conversation {conversation_id}. Available conversations: {list(self.conversation_users.keys())}")
            return
        
        user_ids = self.conversation_users[conversation_id]
        logger.info(f"Broadcasting to {len(user_ids)} users in conversation {conversation_id}: {user_ids}")
        
        for user_id in user_ids:
            # Skip the excluded user if specified
            if exclude_user_id and user_id == exclude_user_id:
                logger.info(f"Skipping excluded user {exclude_user_id}")
                continue
                
            if user_id in self.active_connections:
                logger.info(f"Sending message to user {user_id}")
                try:
                    await self.send_to_user(user_id, message)
                    logger.info(f"Message successfully sent to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {str(e)}")
            else:
                logger.warning(f"User {user_id} has no active connections")
    
    async def broadcast_to_all(self, message: Dict[str, Any], exclude_user_id: Optional[str] = None):
        """
        Broadcast a message to all connected users (system announcements).
        
        Args:
            message: Message data to send
            exclude_user_id: Optional user ID to exclude from broadcast
        """
        for user_id in list(self.active_connections.keys()):
            # Skip the excluded user if specified
            if exclude_user_id and user_id == exclude_user_id:
                continue
                
            await self.send_to_user(user_id, message)
    
    def register_conversation(self, conversation_id: str, user_ids: List[str]):
        """
        Register a conversation and its participants for WebSocket routing.
        
        Args:
            conversation_id: ID of the conversation
            user_ids: List of participant user IDs
        """
        # Update conversation_users mapping
        if conversation_id not in self.conversation_users:
            self.conversation_users[conversation_id] = set()
        
        self.conversation_users[conversation_id].update(user_ids)
        
        # Update user_conversations mapping
        for user_id in user_ids:
            if user_id not in self.user_conversations:
                self.user_conversations[user_id] = set()
            
            self.user_conversations[user_id].add(conversation_id)
        
        # Log registration securely
        if self.security_handler:
            self.security_handler.secure_log(
                "Conversation registered for WebSocket routing",
                {
                    "conversation_id": conversation_id,
                    "participant_count": len(user_ids)
                }
            )
    
    def unregister_conversation(self, conversation_id: str):
        """
        Unregister a conversation when it's deleted.
        
        Args:
            conversation_id: ID of the conversation to unregister
        """
        if conversation_id in self.conversation_users:
            # Get the users in this conversation
            user_ids = self.conversation_users[conversation_id]
            
            # Remove the conversation from each user's list
            for user_id in user_ids:
                if user_id in self.user_conversations:
                    self.user_conversations[user_id].discard(conversation_id)
            
            # Remove the conversation from the mapping
            del self.conversation_users[conversation_id]
    
    def add_user_to_conversation(self, conversation_id: str, user_id: str):
        """
        Add a user to a conversation for WebSocket routing.
        
        Args:
            conversation_id: ID of the conversation
            user_id: ID of the user to add
        """
        # Update conversation_users mapping
        if conversation_id not in self.conversation_users:
            self.conversation_users[conversation_id] = set()
        
        self.conversation_users[conversation_id].add(user_id)
        
        # Update user_conversations mapping
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = set()
        
        self.user_conversations[user_id].add(conversation_id)
    
    def remove_user_from_conversation(self, conversation_id: str, user_id: str):
        """
        Remove a user from a conversation for WebSocket routing.
        
        Args:
            conversation_id: ID of the conversation
            user_id: ID of the user to remove
        """
        # Update conversation_users mapping
        if conversation_id in self.conversation_users:
            self.conversation_users[conversation_id].discard(user_id)
        
        # Update user_conversations mapping
        if user_id in self.user_conversations:
            self.user_conversations[user_id].discard(conversation_id)
    
    def get_online_users(self, conversation_id: str) -> List[str]:
        """
        Get a list of users who are currently online in a conversation.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            List of online user IDs
        """
        if conversation_id not in self.conversation_users:
            return []
        
        # Get all users in the conversation
        user_ids = self.conversation_users[conversation_id]
        
        # Filter to only include users with active connections
        online_user_ids = [
            user_id for user_id in user_ids
            if user_id in self.active_connections and conversation_id in self.active_connections[user_id] and self.connection_active.get(user_id, {}).get(conversation_id, False)
        ]
        
        return online_user_ids
    
    def _prepare_message(self, message, target_user_id=None):
        """
        Prepare a message for sending, optionally with encryption.
        
        Args:
            message: The message to prepare
            target_user_id: Optional user ID for user-specific formatting
            
        Returns:
            JSON string ready for transmission
        """
        # Vérifier si le message est déjà une chaîne JSON
        if isinstance(message, str):
            return message
            
        try:
            # Vérifier que toutes les valeurs dans le message sont sérialisables
            logger.info(f"Preparing message for transmission: {message}")
            
            # Si c'est un message de type "message", effectuer une vérification supplémentaire des données
            if isinstance(message, dict) and message.get("type") == "message" and "data" in message:
                # S'assurer que toutes les dates sont converties en ISO format
                data = message["data"]
                if isinstance(data, dict):
                    # Convertir explicitement les objets datetime en chaînes ISO
                    for key, value in data.items():
                        if isinstance(value, datetime):
                            data[key] = value.isoformat()
                    
                    # Vérifier les types non sérialisables
                    logger.info(f"Message data after date conversion: {data}")
            
            # Convertir le message en JSON avec des paramètres plus détaillés
            message_json = json.dumps(message, default=str)
            logger.info(f"Message JSON prepared: {message_json[:100]}...")
            
            return message_json
        except Exception as e:
            logger.error(f"Error preparing message: {str(e)}, Message: {message}")
            # Retourner un message d'erreur en cas d'échec
            error_message = {
                "type": "error",
                "data": {
                    "error": "Failed to prepare message",
                    "details": str(e)
                }
            }
            
            # Essayer de sérialiser un message d'erreur simplifié
            try:
                return json.dumps(error_message)
            except:
                # En cas d'échec complet, retourner une chaîne d'erreur simple
                return '{"type":"error","data":{"error":"Critical serialization error"}}'
        
    def is_user_online(self, user_id: str) -> bool:
        """
        Check if a user is currently online.
        
        Args:
            user_id: ID of the user to check
            
        Returns:
            True if the user is online, False otherwise
        """
        return user_id in self.active_connections and any(self.connection_active.get(user_id, {}).values())
