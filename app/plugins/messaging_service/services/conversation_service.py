"""
Conversation Service

This module implements the conversation handling service for the messaging plugin,
including conversation creation, retrieval, update, and management.
"""
import logging
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy import or_, and_

from ..models.conversation import (
    ConversationDB, UserConversationSettingsDB, GroupChatDB, UserBlockDB
)
from ..models.message import MessageDB, MessageReceiptDB
from ..schemas.conversation import (
    DirectConversationCreate, GroupConversationCreate,
    ChatUserResponse
)

# Import User model from auth plugin
from app.plugins.advanced_auth.models import User

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Service for handling conversation operations, implementing the standardized
    security approach for all conversation management functions.
    """
    
    def __init__(self):
        """Initialize the conversation service."""
        self.security_handler = None
        self.notification_handler = None
        self.websocket_manager = None
    
    def init_handlers(self, security_handler, notification_handler, websocket_manager):
        """
        Initialize handlers after they are available.
        
        Args:
            security_handler: Security handler for secure conversation handling
            notification_handler: Notification handler for real-time updates
            websocket_manager: WebSocket manager for real-time connections
        """
        self.security_handler = security_handler
        self.notification_handler = notification_handler
        self.websocket_manager = websocket_manager
        logger.info("Conversation service initialized with security, notification, and websocket handlers")
    
    async def create_direct_conversation(self, db: Session, conversation_data: DirectConversationCreate, user_id: str) -> Dict[str, Any]:
        """
        Create a new direct conversation between two users.
        
        Args:
            db: Database session
            conversation_data: Conversation data
            user_id: ID of the creating user
            
        Returns:
            Newly created conversation data
            
        Raises:
            HTTPException: If conversation creation fails
        """
        try:
            # Verify recipient exists
            recipient_id = conversation_data.recipient_id
            # Ensure we're not blocking each other
            await self._check_blocks(db, user_id, recipient_id)
            
            # Check if direct conversation already exists
            existing_conversation = await self._find_direct_conversation(db, user_id, recipient_id)
            if existing_conversation:
                print(f"Direct conversation already exists between {user_id} and {recipient_id}")
                # Return existing conversation
                return await self.get_conversation(db, existing_conversation.id, user_id)
            
            # All participants for a direct conversation
            all_participants = [user_id, recipient_id]
    
            
            # Create conversation
            conversation_id = str(uuid.uuid4())
            conversation = ConversationDB(
                id=conversation_id,
                conversation_type="direct",
                title=None,  # Direct conversations don't need titles
                is_encrypted=conversation_data.is_encrypted,
                created_by=user_id
            )
            
            db.add(conversation)

          
            
            # Add all participants to the conversation with appropriate roles
            for participant_id in all_participants:
                is_creator = participant_id == user_id
                user_settings = UserConversationSettingsDB(
                    id=uuid.uuid4(),
                    user_id=participant_id,
                    conversation_id=conversation_id,
                    is_muted=False,
                    is_pinned=False,
                    is_archived=False,
                    notification_level="all" if is_creator else "mentions",
                    role="admin" if is_creator else "member"
                )
                db.add(user_settings)
            
            # If there's an initial message, add it
            if conversation_data.initial_message:
                message_id = str(uuid.uuid4())
                message = MessageDB(
                    id=message_id,
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    content=conversation_data.initial_message,
                    message_type="text"
                )
                db.add(message)
                
                # Update conversation's last message timestamp
                conversation.last_message_at = message.created_at
            
            db.commit()
            
            # Log the creation using standardized security approach
            if self.security_handler:
                self.security_handler.secure_log(
                    "Direct conversation created",
                    {
                        "conversation_id": conversation_id,
                        "participant_ids": all_participants,
                        "is_encrypted": conversation_data.is_encrypted
                    }
                )
            
            # Return the created conversation
            conversation_result = await self.get_conversation(db, conversation_id, user_id)
            print("===Conversation created:", conversation_result)
            return conversation_result
        
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating direct conversation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating conversation: {str(e)}"
            )
    
    async def create_group_conversation(self, db: Session, conversation_data: GroupConversationCreate, user_id: str) -> Dict[str, Any]:
        """
        Create a new group conversation.
        
        Args:
            db: Database session
            conversation_data: Conversation data
            user_id: ID of the creating user
            
        Returns:
            Created conversation
            
        Raises:
            HTTPException: If conversation creation fails
        """
        # Validate participant list
        participant_ids = list(set(conversation_data.participant_ids))  # Remove duplicates
        
        # Check if creator is in the participant list, add if not
        if user_id not in participant_ids:
            participant_ids.append(user_id)
        
        # Validate group size
        if len(participant_ids) > conversation_data.max_participants:
            raise HTTPException(
                status_code=400, 
                detail=f"Group size exceeds maximum ({len(participant_ids)} > {conversation_data.max_participants})"
            )
        
        # Check for blocked users
        blocks = db.query(UserBlockDB).filter(
            or_(
                and_(UserBlockDB.blocker_id == user_id, UserBlockDB.blocked_id.in_(participant_ids)),
                and_(UserBlockDB.blocker_id.in_(participant_ids), UserBlockDB.blocked_id == user_id)
            )
        ).all()
        
        if blocks:
            blocked_ids = [block.blocked_id if block.blocker_id == user_id else block.blocker_id 
                          for block in blocks]
            
            if self.security_handler:
                self.security_handler.secure_log(
                    "Group includes blocked users",
                    {"user_id": user_id, "blocked_users": blocked_ids},
                    "warning"
                )
            
            # Filter out blocked users
            participant_ids = [pid for pid in participant_ids 
                              if pid == user_id or pid not in blocked_ids]
            
            if len(participant_ids) <= 1:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot create group with only blocked users"
                )
        
        # Create a new conversation
        conversation_id = str(uuid.uuid4())
        
        # Generate encryption key for the conversation if needed
        encryption_key = None
        if conversation_data.is_encrypted and self.security_handler:
            encryption_key = self.security_handler.generate_conversation_key(conversation_id)
            self.security_handler.store_conversation_key(conversation_id, encryption_key)
        
        print("===Conversation data:", conversation_data)
        # Create conversation record
        new_conversation = ConversationDB(
            id=conversation_id,
            conversation_type="group",
            title=conversation_data.title,
            avatar_url=conversation_data.avatar_url,
            created_by=user_id,
            is_encrypted=conversation_data.is_encrypted,
            conversation_metadata=conversation_data.conversation_metadata or {}
        )
        
        db.add(new_conversation)
        db.flush()  # Flush to get the conversation ID
        
        # Create group chat settings
        group_settings = GroupChatDB(
            conversation_id=conversation_id,
            description=conversation_data.description,
            max_participants=conversation_data.max_participants,
            is_public=conversation_data.is_public,
            join_mode=conversation_data.join_mode,
            message_permission=conversation_data.message_permission,
            who_can_invite=conversation_data.who_can_invite,
            who_can_remove=conversation_data.who_can_remove
        )
        
        db.add(group_settings)
        
        # Add participants
        for idx, participant_id in enumerate(participant_ids):
            # Creator is admin, others are members
            role = "admin" if participant_id == user_id else "member"
            
            settings = UserConversationSettingsDB(
                user_id=participant_id,
                conversation_id=conversation_id,
                role=role
            )
            db.add(settings)
        
        # Commit the transaction
        db.commit()
        db.refresh(new_conversation)
        
        # Retrieve the group settings for the response
        group_settings = db.query(GroupChatDB).filter(
            GroupChatDB.conversation_id == conversation_id
        ).first()
        
        # Register the conversation with the WebSocket manager
        if self.websocket_manager:
            self.websocket_manager.register_conversation(conversation_id, participant_ids)
        
        # Log the conversation creation using standardized security approach
        if self.security_handler:
            self.security_handler.secure_log(
                "Group conversation created",
                {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "participant_count": len(participant_ids),
                    "is_encrypted": conversation_data.is_encrypted
                }
            )
        
        conversation_dict = self._conversation_to_dict(
            new_conversation, 
            user_id, 
            include_group_settings=True, 
            group_settings=group_settings, 
            db=db
        )
        
        # Notify other participants about new conversation
        if self.notification_handler:
            recipient_ids = [pid for pid in participant_ids if pid != user_id]
            
            if recipient_ids:
                await self.notification_handler.notify_conversation_update(
                    conversation_id,
                    "conversation_created",
                    conversation_dict,
                    recipient_ids
                )
        
        return conversation_dict
    
    async def get_conversation(self, db: Session, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a single conversation by ID.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation to retrieve
            user_id: ID of the requesting user
            
        Returns:
            Conversation data
            
        Raises:
            HTTPException: If conversation retrieval fails
        """
        try:
            user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            print("===User ID:", user_id_uuid)
            # Vérifier si la conversation existe
            conversation = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            print("===Conversation:", conversation)
            # Vérifier si l'utilisateur est participant
            user_settings = db.query(UserConversationSettingsDB).filter(
                UserConversationSettingsDB.conversation_id == conversation_id,
                UserConversationSettingsDB.user_id == user_id_uuid
            ).first()
            print("===User settings:", user_settings)
            if not user_settings:
                raise HTTPException(status_code=403, detail="You are not a participant in this conversation")
            
            # Si la conversation est une conversation directe et a été supprimée par l'utilisateur
            # mais qu'il essaie d'y accéder à nouveau, on réactive l'accès à la conversation
            if conversation.conversation_type == "direct" and user_settings.is_deleted:
                user_settings.is_deleted = False
                db.add(user_settings)
                db.commit()
            print("===User settings after check:", user_settings)
            # Fetch the conversation
            conversation = db.query(ConversationDB).filter(
                ConversationDB.id == conversation_id
            ).first()
            
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            # Get the last message for this conversation
            last_message = db.query(MessageDB).filter(
                MessageDB.conversation_id == conversation_id
            ).order_by(MessageDB.created_at.desc()).first()

            # Get count of unread messages
            unread_count = db.query(MessageDB).join(
                MessageReceiptDB, 
                and_(
                    str(MessageReceiptDB.message_id) == str(MessageDB.id),
                    str(MessageReceiptDB.user_id) == str(user_id_uuid),
                    MessageReceiptDB.status.in_(["sent", "delivered"])
                )
            ).filter(
                str(MessageDB.conversation_id) == str(conversation_id),
                str(MessageDB.sender_id) != str(user_id_uuid)
            ).count()
            print("===Unread count:", unread_count)
            
            # Convert to dict and include additional data
            include_group_settings = conversation.conversation_type == "group"
            conversation_dict = self._conversation_to_dict(
                conversation, 
                user_id, 
                include_group_settings=include_group_settings,
                last_message=last_message,
                unread_count=unread_count,
                user_settings=user_settings,
                db=db
            )
            
            # Récupération manuelle des participants pour garantir le format correct
            participants = []
            participant_settings = db.query(UserConversationSettingsDB).filter(
                UserConversationSettingsDB.conversation_id == conversation_id
            ).all()
            
            for setting in participant_settings:
                participant = {
                    "id": str(setting.id),
                    "user_id": str(setting.user_id),
                    "conversation_id": str(setting.conversation_id),
                    "is_muted": setting.is_muted,
                    "is_pinned": setting.is_pinned,
                    "is_archived": setting.is_archived,
                    "custom_name": setting.custom_name,
                    "theme_color": setting.theme_color,
                    "notification_level": setting.notification_level,
                    "role": setting.role,
                    "last_read_message_id": str(setting.last_read_message_id) if setting.last_read_message_id else None,
                    "created_at": setting.created_at,
                    "updated_at": setting.updated_at
                }
                participants.append(participant)
            
            conversation_dict["participants"] = participants
            
            return conversation_dict
        
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error getting conversation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error getting conversation: {str(e)}"
            )
    
    async def get_conversations(self, db: Session, user_id: str,
                               filter_type: str = "all",
                               filter_archived: bool = False,
                               search_query: Optional[str] = None,
                               limit: Optional[int] = 20,
                               offset: Optional[int] = 0) -> Dict[str, Any]:
        """
        Get all conversations for a user, with filtering and pagination.
        
        Args:
            db: Database session
            user_id: ID of the requesting user
            filter_type: Type of conversations to filter by (direct, group, all)
            filter_archived: Whether to include archived conversations
            search_query: Optional search term to filter conversations by title
            limit: Maximum number of conversations to return
            offset: Offset for pagination
            
        Returns:
            List of conversations
        """
        # Conversion de user_id en UUID pour les comparaisons avec les colonnes UUID
        user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        
        # Build the base query to get conversations the user is in
        query = db.query(ConversationDB) \
            .join(UserConversationSettingsDB) \
            .filter(UserConversationSettingsDB.user_id == user_id_uuid,
                    UserConversationSettingsDB.is_deleted == False)
        
        # Apply archive filter if needed
        if filter_archived:
            query = query.filter(UserConversationSettingsDB.is_archived == True)
            
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        conversations = query.order_by(
            UserConversationSettingsDB.is_pinned.desc(),
            UserConversationSettingsDB.updated_at.desc()
        ).offset(offset).limit(limit).all()
        
        # Get all conversation IDs
        conversation_ids = [c.id for c in conversations]
        
        # Get all group chat settings for group conversations
        group_chat_ids = [c.id for c in conversations if c.conversation_type == "group"]
        group_settings_map = {}
        
        if group_chat_ids:
            group_settings = db.query(GroupChatDB).filter(
                GroupChatDB.conversation_id.in_(group_chat_ids)
            ).all()
            
            group_settings_map = {gs.conversation_id: gs for gs in group_settings}
        
        # Get last messages for conversations
        last_messages_map = {}
        
        for conversation_id in conversation_ids:
            # Convert to string explicitly to ensure compatibility
            conversation_id_str = str(conversation_id)
            
            last_message = db.query(MessageDB).filter(
                MessageDB.conversation_id == conversation_id_str
            ).order_by(MessageDB.created_at.desc()).first()
            
            if last_message:
                last_messages_map[conversation_id] = last_message
        
        # Get unread counts for conversations
        unread_counts_map = {}
        
        for conversation_id in conversation_ids:
            # Convert user_id to UUID for comparison with sender_id column
            user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            conversation_id_str = str(conversation_id)
            
            # Get all messages from other users in this conversation
            messages_query = db.query(MessageDB).filter(
                MessageDB.conversation_id == conversation_id_str,
                MessageDB.sender_id != str(user_id_uuid)
            )

            # From these messages, find ones with receipts that are not "read"
            unread_messages = messages_query.join(
                MessageReceiptDB,
                MessageReceiptDB.message_id == MessageDB.id
            ).filter(
                MessageReceiptDB.user_id == user_id_uuid,
                MessageReceiptDB.status.in_(["sent", "delivered"])
            ).all()

            unread_count = len(unread_messages)

            unread_counts_map[conversation_id] = unread_count
            
            # Update unread_count in UserConversationSettingsDB
            user_settings = db.query(UserConversationSettingsDB).filter(
                str(UserConversationSettingsDB.conversation_id) == str(conversation_id),
                str(UserConversationSettingsDB.user_id) == str(user_id_uuid)
            ).first()
            
            if user_settings and user_settings.unread_count != unread_count:
                user_settings.unread_count = unread_count
        
        # Save updates
        db.commit()
        
        # Create response items
        conversation_dicts = []
        
        for conversation in conversations:
            conversation_id = conversation.id
            
            # Get user settings for this conversation
            user_setting = db.query(UserConversationSettingsDB).filter(
                str(UserConversationSettingsDB.conversation_id) == str(conversation_id),
                str(UserConversationSettingsDB.user_id) == str(user_id_uuid)
            ).first()
            
            include_group_settings = conversation.conversation_type == "group"
            last_message = last_messages_map.get(conversation_id)
            unread_count = unread_counts_map.get(conversation_id, 0)
            
            conversation_dict = self._conversation_to_dict(
                conversation, 
                user_id, 
                include_group_settings=include_group_settings,
                user_settings=user_setting,
                last_message=last_message,
                unread_count=unread_count,
                group_settings=group_settings_map.get(conversation_id),
                db=db
            )
            
            # Ensure last_message contains all required fields for MessageResponse
            if conversation_dict.get('last_message'):
                last_msg = conversation_dict['last_message']
                if 'updated_at' not in last_msg:
                    last_msg['updated_at'] = last_msg.get('created_at')
                if 'is_edited' not in last_msg:
                    last_msg['is_edited'] = False
                if 'is_forwarded' not in last_msg:
                    last_msg['is_forwarded'] = False
                if 'is_encrypted' not in last_msg:
                    last_msg['is_encrypted'] = False
                if 'conversation_id' not in last_msg:
                    last_msg['conversation_id'] = str(conversation_id)
            
            conversation_dicts.append(conversation_dict)
        
        # Sort by last message time (if available) or updated time
        conversation_dicts.sort(
            key=lambda x: (
                x.get("is_pinned", False),
                x.get("last_message_at") or x.get("updated_at")
            ),
            reverse=True
        )
        
        # Log the retrieval using standardized security approach
        if self.security_handler:
            self.security_handler.secure_log(
                "Retrieved user conversations",
                {
                    "user_id": user_id,
                    "count": len(conversation_dicts),
                    "total": total_count,
                    "filter_type": filter_type,
                    "filter_archived": filter_archived
                }
            )
        
        # Ensure size is always an integer, even if limit is None
        # Use a default value of 20 if limit is None
        page_size = limit if limit is not None else 20
        
        return {
            "conversations": conversation_dicts,
            "total": total_count,
            "page": offset // page_size + 1 if page_size else 1,
            "size": page_size
        }
    
    async def get_blocked_users(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all users blocked by the specified user.
        
        Args:
            db: Database session
            user_id: ID of the user
            
        Returns:
            List of blocked user records
        """
        blocks = db.query(UserBlockDB).filter(UserBlockDB.blocker_id == user_id).all()
        
        result = []
        for block in blocks:
            blocked_user = db.query(User).filter(User.id == block.blocked_id).first()
            if blocked_user:
                result.append({
                    "id": str(block.id),
                    "user_id": str(block.blocker_id),
                    "blocked_id": str(block.blocked_id),
                    "reason": block.reason,
                    "created_at": block.created_at,
                    "updated_at": block.updated_at if hasattr(block, 'updated_at') else None,
                    "blocked_user": {
                        "id": str(blocked_user.id),
                        "username": blocked_user.username,
                        "first_name": blocked_user.first_name,
                        "last_name": blocked_user.last_name,
                        "profile_picture": blocked_user.profile_picture
                    }
                })
        
        return result
    
    async def add_conversation_member(self, db: Session, conversation_id: str, user_id: str, new_member_id: str) -> Dict[str, Any]:
        """
        Add a new member to a group conversation.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user adding the member
            new_member_id: ID of the user to add
            
        Returns:
            Updated conversation data
            
        Raises:
            HTTPException: If member addition fails
        """
        # Verify the conversation exists and is a group conversation
        conversation = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        if conversation.conversation_type != "group":
            raise HTTPException(status_code=400, detail="Cannot add members to a direct conversation")
        
        # Check user permission (must be a member with appropriate role)
        user_settings = db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.conversation_id == conversation_id,
            UserConversationSettingsDB.user_id == user_id
        ).first()
        
        if not user_settings:
            raise HTTPException(status_code=403, detail="Not authorized to add members to this conversation")
            
        # Only admins or members with appropriate permissions can add members
        if user_settings.role != "admin" and user_settings.role != "moderator":
            raise HTTPException(status_code=403, detail="Not authorized to add members to this conversation")
        
        # Check if the new member exists
        new_member = db.query(User).filter(User.id == new_member_id).first()
        if not new_member:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Check if the new member is already in the conversation
        existing_member = db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.conversation_id == conversation_id,
            UserConversationSettingsDB.user_id == new_member_id
        ).first()
        
        if existing_member:
            if existing_member.is_deleted:
                # If the user previously left or was removed, re-activate their membership
                existing_member.is_deleted = False
                existing_member.updated_at = datetime.utcnow()
                db.commit()
                
                # Create a system message about rejoining
                now = datetime.utcnow()
                system_message = MessageDB(
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    message_type="system",
                    content=f"User {new_member.username} has been re-added to the conversation",
                    message_metadata={"action": "member_readded", "member_id": str(new_member_id), "added_by": str(user_id)},
                    is_encrypted=False,
                    is_edited=False,
                    is_forwarded=False,
                    updated_at=now
                )
                db.add(system_message)
                db.commit()
                
                # Update the conversation with latest message info for response validation
                conversation.last_message_at = now
                db.commit()
            else:
                raise HTTPException(status_code=400, detail="User is already a member of this conversation")
        else:
            # Add the new member to the conversation
            new_member_settings = UserConversationSettingsDB(
                conversation_id=conversation_id,
                user_id=new_member_id,
                role="member",
                is_muted=False,
                is_archived=False,
                is_pinned=False,
                notification_level="all",
                is_deleted=False
            )
            db.add(new_member_settings)
            
            # Create a system message about the new member
            now = datetime.utcnow()
            system_message = MessageDB(
                conversation_id=conversation_id,
                sender_id=user_id,
                message_type="system",
                content=f"User {new_member.username} has been added to the conversation",
                message_metadata={"action": "member_added", "member_id": str(new_member_id), "added_by": str(user_id)},
                is_encrypted=False,
                is_edited=False,
                is_forwarded=False,
                updated_at=now
            )
            db.add(system_message)
            db.commit()
            
            # Update the conversation with latest message info
            conversation.last_message_at = now
            db.commit()
            
        # Notify all participants about the new member
        if self.websocket_manager:
            await self.websocket_manager.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "member_added",
                    "data": {
                        "conversation_id": str(conversation_id),
                        "member_id": str(new_member_id),
                        "added_by": str(user_id)
                    }
                }
            )
        
        print("===Conversation after adding member:", conversation)
        try:
            # Return the updated conversation - handle if the response validation fails
            return await self.get_conversation(db, conversation_id, user_id)
            
        except Exception as e:
            # Log the error but still return success since the member was added
            print(f"Error getting conversation after adding member: {str(e)}")
            return {"success": True, "message": f"User {new_member.username} added to conversation", "conversation_id": conversation_id}
    
    async def search_users_for_chat(self, db: Session, current_user_id: str, search_query: str, limit: int = 20) -> List[ChatUserResponse]:
        """
        Search for users to start a chat with.
        
        Args:
            db: Database session
            current_user_id: ID of the current user
            search_query: Search string to match against username, first or last name
            limit: Maximum number of results to return
            
        Returns:
            List of users matching the search criteria
            
        Security:
            - Excludes the current user
            - Excludes blocked users
            - Only returns non-sensitive user data
            - Limited number of results
        """
        logger.info(f"Starting user search with query: '{search_query}', current_user_id: {current_user_id}")
        
        # Get blocked users
        blocked_users = await self.get_blocked_users(db, current_user_id)
        blocked_ids = [block.blocked_id for block in blocked_users]
        logger.info(f"Found {len(blocked_ids)} blocked users for current user")
        
        # Build query with search conditions
        search_filter = or_(
            User.username.ilike(f"%{search_query}%"),
            User.first_name.ilike(f"%{search_query}%"),
            User.last_name.ilike(f"%{search_query}%"),
            User.email.ilike(f"%{search_query}%") # Optionally include email
        )
        logger.info(f"Created search filter for query: '{search_query}'")
        
        # Query users
        query = db.query(
            User.id,
            User.username,
            User.first_name, 
            User.last_name,
            User.profile_picture,
            User.last_login.label("last_seen")
        ).filter(
            and_(
                User.id != current_user_id,  # Exclude current user
                User.is_active == True       # Only active users
            )
        )
        
        # Add blocked users filter only if there are blocked users
        if blocked_ids:
            query = query.filter(~User.id.in_(blocked_ids))
            
        logger.info("Created base query excluding current user and blocked users")
        
        # Add search filter if query provided
        if search_query:
            query = query.filter(search_filter)
            logger.info("Applied search filter to query")
        
        # Get results with limit
        logger.info(f"Executing query with limit: {limit}")
        try:
            # Print SQL query for debugging
            sql_query = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
            logger.info(f"SQL Query: {sql_query}")
            
            results = query.limit(limit).all()
            logger.info(f"Query returned {len(results)} results")
            
            # Debug result details
            for i, user in enumerate(results):
                logger.info(f"Result {i+1}: id={user.id}, username={user.username}, first_name={user.first_name}, last_name={user.last_name}")
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            db.rollback()  # Rollback transaction to allow future queries to work
            raise
        
        # Convert to response schema
        chat_users = []
        for user in results:
            chat_users.append(
                ChatUserResponse(
                    id=str(user.id),
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    profile_picture=user.profile_picture,
                    last_seen=user.last_seen
                )
            )
        
        logger.info(f"Returning {len(chat_users)} users in response")
        return chat_users
    
    async def delete_conversation(self, db: Session, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """
        Delete a conversation or leave a group conversation.
        
        For direct conversations:
         - The conversation is deleted from the user's view
         - If both participants delete it, it's removed from the database
        
        For group conversations:
         - If the user is an admin, the entire conversation is deleted for all users
         - If the user is a regular member, they just leave the conversation
        
        Args:
            db: Database session
            conversation_id: ID of the conversation to delete
            user_id: ID of the user performing the action
            
        Returns:
            Status message
            
        Raises:
            HTTPException: If conversation deletion fails
        """
        # Conversion de user_id en UUID pour les comparaisons avec les colonnes UUID
        user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        conversation_id_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
        
        print("===Deleting conversation:", conversation_id_uuid)
        # Check if conversation exists and if user is a participant
        conversation = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
        print("===Conversation found:", conversation)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Check if user is a participant
        user_settings = db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.conversation_id == conversation_id,
            UserConversationSettingsDB.user_id == user_id_uuid
        ).first()
        print("===User settings found:", user_settings)
        
        if not user_settings:
            raise HTTPException(status_code=403, detail="You are not a participant in this conversation")
            
        # Different behavior based on conversation type
        if conversation.conversation_type == "direct":
            # Pour les conversations directes, on marque la conversation comme supprimée pour cet utilisateur
            # Au lieu de vraiment supprimer l'entrée, ce qui permettra de conserver les informations
            
            user_settings.is_deleted = True
            db.add(user_settings)
            print("===User settings marked as deleted rather than removed")
            
            # Vérifier si l'autre utilisateur a aussi supprimé la conversation
            other_user_settings = db.query(UserConversationSettingsDB).filter(
                UserConversationSettingsDB.conversation_id == conversation_id,
                UserConversationSettingsDB.user_id != user_id_uuid
            ).first()
            print("===Other user settings found:", other_user_settings)
            
            if not other_user_settings or other_user_settings.is_deleted:
                print("===Both users have deleted the conversation or no other user exists")
                # Les deux utilisateurs ont supprimé la conversation ou il n'y a pas d'autre utilisateur
                await self._hard_delete_conversation(db, conversation_id)
                print("===Conversation permanently deleted")
                message = "Conversation permanently deleted"
            else:
                # L'autre utilisateur a encore accès à la conversation
                db.commit()
                message = "Conversation deleted from your view"
                
        else:  # Group conversation
            # Check if user is an admin
            is_admin = user_settings.role == "admin"
            
            if is_admin:
                # Admin can delete the entire conversation
                print("===Deleting group conversation for all participants")
                await self._hard_delete_conversation(db, conversation_id)
                print("===Conversation deleted for all participants")
                message = "Group conversation deleted for all participants"
            else:
                print("===Non-admin just leaves the conversation")
                # Non-admin just leaves the conversation
                
                # Get user info for the system message
                user = db.query(User).filter(User.id == user_id_uuid).first()
                username = user.username if user else "A user"
                
                # Create a system message about the user leaving
                now = datetime.utcnow()
                system_message = MessageDB(
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    message_type="system",
                    content=f"{username} has left the conversation",
                    message_metadata={"action": "member_left", "member_id": str(user_id)},
                    is_encrypted=False,
                    is_edited=False,
                    is_forwarded=False,
                    updated_at=now
                )
                db.add(system_message)
                
                # Update the conversation with latest message timestamp
                conversation.last_message_at = now
                db.add(conversation)
                
                # Now remove the user from the conversation
                db.delete(user_settings)
                db.commit()
                message = "You left the group conversation"
                
            # Notify participants about the change
            if self.notification_handler:
                # Get remaining participants
                participants = db.query(UserConversationSettingsDB).filter(
                    UserConversationSettingsDB.conversation_id == conversation_id,
                    UserConversationSettingsDB.user_id != user_id_uuid
                ).all()
                
                recipient_ids = [str(p.user_id) for p in participants]
                print("===Recipient IDs:", recipient_ids)
                
                if recipient_ids:
                    event_type = "conversation_deleted" if is_admin else "member_left"
                    
                    await self.notification_handler.notify_conversation_update(
                        conversation_id,
                        event_type,
                        {"user_id": user_id, "conversation_id": conversation_id},
                        recipient_ids
                    )
        
        # Log the action
        if self.security_handler:
            action = "Deleted conversation" if conversation.conversation_type == "direct" or is_admin else "Left group conversation"
            self.security_handler.secure_log(
                action,
                {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "conversation_type": conversation.conversation_type
                }
            )
            
        return {"message": message, "status": "success"}
    
    async def _hard_delete_conversation(self, db: Session, conversation_id: str) -> None:
        """
        Completely remove a conversation and all related data from the database.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation to delete
        """
        conversation_id_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
        
        # Delete all messages first (cascade delete for message reactions, etc.)
        db.query(MessageDB).filter(MessageDB.conversation_id == conversation_id).delete()
        print("===Messages deleted")
        # Delete user conversation settings
        db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.conversation_id == conversation_id
        ).delete()
        print("===User conversation settings deleted")
        # Delete group settings if it's a group conversation
        db.query(GroupChatDB).filter(GroupChatDB.conversation_id == conversation_id).delete()
        print("===Group settings deleted")
        # Finally, delete the conversation itself
        db.query(ConversationDB).filter(ConversationDB.id == conversation_id).delete()
        print("===Conversation deleted")
        
        # Commit the changes
        db.commit()
        
        # Unregister from WebSocket manager
        if self.websocket_manager:
            self.websocket_manager.unregister_conversation(conversation_id)
    
    async def _find_direct_conversation(self, db: Session, user_id: str, other_user_id: str) -> Optional[ConversationDB]:
        """
        Find a direct conversation between two users if it exists.
        
        Args:
            db: Database session
            user_id: First user ID
            other_user_id: Second user ID
            
        Returns:
            Conversation if found, None otherwise
        """
        # Conversion des user_id en UUID pour les comparaisons avec les colonnes UUID
        user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        other_user_id_uuid = uuid.UUID(other_user_id) if isinstance(other_user_id, str) else other_user_id
        
        # Get all conversation IDs that user_id participates in
        user_conversation_ids = db.query(UserConversationSettingsDB.conversation_id).filter(
            UserConversationSettingsDB.user_id == user_id_uuid
        ).all()
        
        user_conversation_ids = [c[0] for c in user_conversation_ids]
        
        if not user_conversation_ids:
            return None
        
        # Find conversations that both users participate in
        other_user_settings = db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.user_id == other_user_id_uuid,
            UserConversationSettingsDB.conversation_id.in_(user_conversation_ids)
        ).all()
        
        other_user_conversation_ids = [s.conversation_id for s in other_user_settings]
        
        if not other_user_conversation_ids:
            return None
        
        # Find a direct conversation among these shared conversations
        conversation = db.query(ConversationDB).filter(
            ConversationDB.id.in_(other_user_conversation_ids),
            ConversationDB.conversation_type == "direct"
        ).first()
        
        return conversation
    
    async def _check_blocks(self, db: Session, user_id: str, recipient_id: str) -> None:
        """
        Check if there are any blocks between the two users.
        
        Args:
            db: Database session
            user_id: First user ID
            recipient_id: Second user ID
            
        Raises:
            HTTPException: If users are blocking each other
        """
        if not recipient_id:
            raise HTTPException(
                status_code=400,
                detail="Un destinataire doit être spécifié"
            )
        
        # Conversion des user_id en UUID pour les comparaisons avec les colonnes UUID
        user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        recipient_id_uuid = uuid.UUID(recipient_id) if isinstance(recipient_id, str) else recipient_id
            
        # Check for user blocks (in both directions)
        block_exists = (
            db.query(UserBlockDB)
            .filter(
                or_(
                    and_(UserBlockDB.blocker_id == user_id_uuid, UserBlockDB.blocked_id == recipient_id_uuid),
                    and_(UserBlockDB.blocker_id == recipient_id_uuid, UserBlockDB.blocked_id == user_id_uuid)
                )
            )
            .first()
        ) is not None
        
        if block_exists:
            if self.security_handler:
                self.security_handler.secure_log(
                    "Conversation creation blocked due to user block",
                    {"user_id": user_id, "recipient_id": recipient_id},
                    "warning"
                )
            raise HTTPException(
                status_code=403,
                detail="Cannot create conversation with blocked user"
            )
    
    def _conversation_to_dict(self, conversation: ConversationDB, user_id: str,
                             include_group_settings: bool = False,
                             user_settings: Optional[UserConversationSettingsDB] = None,
                             last_message: Optional[MessageDB] = None,
                             unread_count: int = 0,
                             group_settings: Optional[GroupChatDB] = None,
                             db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Convert a conversation model to a dictionary with additional data.
        
        Args:
            conversation: Conversation model
            user_id: ID of the requesting user
            include_group_settings: Whether to include group chat settings
            user_settings: Optional user conversation settings
            last_message: Optional last message in the conversation
            unread_count: Number of unread messages
            group_settings: Optional group chat settings
            db: Optional database session for fetching participants
            
        Returns:
            Dictionary representation of the conversation
        """
        # Helper function to convert UUID to string safely
        def _safe_str(value):
            if hasattr(value, 'hex'):  # UUID object has hex attribute
                return str(value)
            return value
            
        # Get basic conversation data
        result = {
            "id": _safe_str(conversation.id),
            "conversation_type": conversation.conversation_type,
            "title": conversation.title,
            "avatar_url": conversation.avatar_url,
            "is_encrypted": conversation.is_encrypted,
            "created_by": _safe_str(conversation.created_by),
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "last_message_at": conversation.last_message_at,
            "unread_count": unread_count
        }
        
        # Add metadata if available, using standardized security approach
        if conversation.conversation_metadata and self.security_handler:
            try:
                result["metadata"] = self.security_handler.decrypt_metadata(conversation.conversation_metadata)
            except Exception as e:
                logger.error(f"Error decrypting conversation metadata: {str(e)}")
                result["metadata"] = {}
        else:
            result["metadata"] = {}
        
        # Add user settings if available
        if user_settings:
            result.update({
                "is_muted": user_settings.is_muted,
                "is_pinned": user_settings.is_pinned,
                "is_archived": user_settings.is_archived,
                "custom_name": user_settings.custom_name,
                "theme_color": user_settings.theme_color,
                "notification_level": user_settings.notification_level,
                "role": user_settings.role,
                "last_read_message_id": _safe_str(user_settings.last_read_message_id)
            })
        
        # Add group settings if this is a group and we should include them
        if include_group_settings and conversation.conversation_type == "group":
            # Use provided group settings if available, otherwise fetch from DB
            if not group_settings:
                # This would require a database session, which we might not have
                # In a real implementation, this should be handled by passing group_settings
                pass
                
            if group_settings:
                result.update({
                    "description": group_settings.description,
                    "max_participants": group_settings.max_participants,
                    "is_public": group_settings.is_public,
                    "join_mode": group_settings.join_mode,
                    "message_permission": group_settings.message_permission,
                    "who_can_invite": group_settings.who_can_invite,
                    "who_can_remove": group_settings.who_can_remove
                })
        
        # Add last message if available
        if last_message:
            # In a real implementation, we would convert the message to a dict
            # and possibly decrypt its content
            content = last_message.content
            if last_message.is_encrypted and self.security_handler:
                try:
                    content = self.security_handler.decrypt_message(
                        content, user_id
                    )
                except Exception as e:
                    logger.error(f"Error decrypting message content: {str(e)}")
                    content = None
                    
            result["last_message"] = {
                "id": last_message.id,
                "sender_id": last_message.sender_id,
                "message_type": last_message.message_type,
                "content": content,
                "is_deleted": last_message.is_deleted,
                "created_at": last_message.created_at
            }
        
        # Récupérer et ajouter les participants
        if db:
            participant_settings = db.query(UserConversationSettingsDB).filter(
                UserConversationSettingsDB.conversation_id == conversation.id
            ).all()
            
            participants = []
            for setting in participant_settings:
                # Récupérer les informations de l'utilisateur
                user = db.query(User).filter(User.id == setting.user_id).first()
                
                participant = {
                    "id": _safe_str(setting.id),
                    "user_id": _safe_str(setting.user_id),
                    "conversation_id": _safe_str(setting.conversation_id),
                    "is_muted": setting.is_muted,
                    "is_pinned": setting.is_pinned,
                    "is_archived": setting.is_archived,
                    "custom_name": setting.custom_name,
                    "theme_color": setting.theme_color,
                    "notification_level": setting.notification_level,
                    "role": setting.role,
                    "last_read_message_id": _safe_str(setting.last_read_message_id),
                    "created_at": setting.created_at,
                    "updated_at": setting.updated_at
                }
                
                # Ajouter les informations utilisateur si disponibles
                if user:
                    participant.update({
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "username": user.username,
                        "email": user.email,
                        "profile_picture": user.profile_picture
                    })
                
                participants.append(participant)
            
            result["participants"] = participants
        
        return result
    
    async def mark_conversation_as_read(self, db: Session, conversation_id: str, user_id: str) -> bool:
        """
        Mark all messages in a conversation as read for the specified user.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user marking messages as read
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            HTTPException: If conversation not found or user is not a participant
        """
        try:
            # Ensure user_id is in the correct format for database comparisons
            user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            
            # Check if conversation exists
            conversation = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            # Check if user is a participant in the conversation
            user_settings = db.query(UserConversationSettingsDB).filter(
                UserConversationSettingsDB.conversation_id == conversation_id,
                UserConversationSettingsDB.user_id == user_id_uuid
            ).first()
            
            if not user_settings:
                raise HTTPException(status_code=403, detail="You are not a participant in this conversation")
            
            # Find all unread messages from other users in this conversation
            unread_messages = db.query(MessageDB).outerjoin(
                MessageReceiptDB,
                and_(
                    MessageReceiptDB.message_id == MessageDB.id,
                    MessageReceiptDB.user_id == user_id_uuid
                )
            ).filter(
                MessageDB.conversation_id == conversation_id,
                MessageDB.sender_id != str(user_id_uuid),
                or_(
                    MessageReceiptDB.status.in_(["sent", "delivered"]),
                    MessageReceiptDB.id == None
                )
            ).all()
            
            # Get the most recent message for updating last_read_message_id
            last_message = db.query(MessageDB).filter(
                MessageDB.conversation_id == conversation_id
            ).order_by(MessageDB.created_at.desc()).first()
            
            # Update user's conversation settings with the latest message ID
            if last_message:
                user_settings.last_read_message_id = last_message.id
                user_settings.unread_count = 0
                db.add(user_settings)
            
            # Mark each message as read
            for message in unread_messages:
                # Check if a receipt exists
                receipt = db.query(MessageReceiptDB).filter(
                    MessageReceiptDB.message_id == message.id,
                    MessageReceiptDB.user_id == user_id_uuid
                ).first()
                
                if receipt:
                    # Update existing receipt
                    receipt.status = "read"
                    receipt.updated_at = datetime.utcnow()
                    db.add(receipt)
                else:
                    # Create new receipt
                    new_receipt = MessageReceiptDB(
                        message_id=message.id,
                        user_id=user_id_uuid,
                        status="read",
                        updated_at=datetime.utcnow()
                    )
                    db.add(new_receipt)
            
            # Commit changes
            db.commit()
            
            # Notify sender(s) that their messages have been read via WebSocket
            if self.websocket_manager:
                # Group messages by sender
                sender_message_map = {}
                for message in unread_messages:
                    sender_id = str(message.sender_id)
                    if sender_id not in sender_message_map:
                        sender_message_map[sender_id] = []
                    sender_message_map[sender_id].append(str(message.id))
                
                # Send read receipts to each sender
                for sender_id, message_ids in sender_message_map.items():
                    if sender_id != str(user_id_uuid):  # Don't send to self
                        await self.websocket_manager.send_to_user(
                            sender_id,
                            {
                                "type": "read_receipt",
                                "data": {
                                    "conversation_id": str(conversation_id),
                                    "reader_id": str(user_id_uuid),
                                    "message_ids": message_ids
                                }
                            }
                        )
                
                # Get conversation data to broadcast update
                conversation_data = await self.get_conversation(db, str(conversation_id), str(user_id_uuid))
                
                # Broadcast conversation update to all participants to update their conversation list
                await self.websocket_manager.broadcast_to_conversation(
                    str(conversation_id),
                    {
                        "type": "conversation_update",
                        "data": {
                            "conversation_id": str(conversation_id),
                            "unread_count": 0,  # For the reader, will be calculated client-side for others
                            "last_message": conversation_data.get("last_message"),
                            "last_message_at": conversation_data.get("last_message_at")
                        }
                    }
                )
            
            return True
            
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking conversation as read: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error marking conversation as read: {str(e)}"
            )
