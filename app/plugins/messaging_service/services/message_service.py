"""
Message Service

This module implements the core message handling service for the messaging plugin,
including message creation, retrieval, update, and deletion.
"""
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi import UploadFile, HTTPException

from ..models.message import MessageDB, MessageAttachmentDB, MessageReceiptDB
from ..models.conversation import ConversationDB, UserConversationSettingsDB
from ..schemas.message import MessageCreate, MessageUpdate, MessageSearchRequest

logger = logging.getLogger(__name__)


class MessageService:
    """
    Service for handling message operations, implementing the standardized
    security approach for all messaging functions.
    """
    
    def __init__(self):
        """Initialize the message service."""
        self.security_handler = None
        self.file_handler = None
        self.notification_handler = None
    
    def init_handlers(self, security_handler, file_handler, notification_handler):
        """
        Initialize handlers after they are available.
        
        Args:
            security_handler: Security handler for secure message handling
            file_handler: File handler for attachments
            notification_handler: Notification handler for real-time updates
        """
        self.security_handler = security_handler
        self.file_handler = file_handler
        self.notification_handler = notification_handler
        logger.info("Message service initialized with security, file, and notification handlers")
    
    async def create_message(self, db: Session, message_data: MessageCreate, 
                           sender_id: str, attachments: Optional[List[UploadFile]] = None) -> Dict[str, Any]:
        """
        Create a new message in a conversation.
        
        Args:
            db: Database session
            message_data: Message data
            sender_id: ID of the sending user
            attachments: Optional list of file attachments
            
        Returns:
            Created message
            
        Raises:
            HTTPException: If message creation fails
        """
        # Validate the message request using standardized security approach
        if self.security_handler:
            is_valid = self.security_handler.validate_message_request(message_data.dict())
            if not is_valid:
                if self.security_handler:
                    self.security_handler.secure_log(
                        "Message validation failed",
                        {"sender_id": sender_id},
                        "warning"
                    )
                raise HTTPException(status_code=400, detail="Invalid message request")
        
        # Verify the conversation exists and user has access
        conversation_id = message_data.conversation_id
        conversation_id_str = str(conversation_id)  
        conversation = db.query(ConversationDB).filter(
            ConversationDB.id == conversation_id_str
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Check if user is a member of the conversation
        user_id_uuid = uuid.UUID(sender_id) if isinstance(sender_id, str) else sender_id
        user_settings = db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.conversation_id == conversation_id_str,
            UserConversationSettingsDB.user_id == user_id_uuid
        ).first()
        
        if not user_settings:
            if self.security_handler:
                self.security_handler.secure_log(
                    "Unauthorized message attempt",
                    {"sender_id": sender_id, "conversation_id": conversation_id_str},
                    "warning"
                )
            raise HTTPException(status_code=403, detail="Not a member of this conversation")
        
        # Process content based on conversation encryption setting
        content = message_data.content
        is_encrypted = conversation.is_encrypted
        
        # Encrypt content if needed using standardized security approach
        if is_encrypted and content and self.security_handler:
            encrypted_content = self.security_handler.encrypt_message(content, conversation_id_str)
            content = encrypted_content
        
        # Process metadata using standardized security approach
        metadata = message_data.message_metadata
        metadata_str = None
        
        if metadata and self.security_handler:
            metadata_str = self.security_handler.encrypt_metadata(metadata)
        
        # Create the message
        new_message = MessageDB(
            conversation_id=conversation_id_str,
            sender_id=sender_id,
            message_type=message_data.message_type,
            content=content,
            message_metadata=metadata_str,
            is_encrypted=is_encrypted,
            reply_to_message_id=message_data.reply_to_message_id
        )
        
        db.add(new_message)
        db.flush()  # Flush to get the message ID
        
        # Process attachments if any
        message_attachments = []
        if attachments and self.file_handler:
            for attachment in attachments:
                try:
                    attachment_info = await self.file_handler.save_attachment(
                        attachment, sender_id, conversation_id_str
                    )
                    
                    # Create attachment record
                    attachment_db = MessageAttachmentDB(
                        message_id=new_message.id,
                        file_name=attachment_info["file_name"],
                        file_type=attachment_info["file_type"],
                        file_size=attachment_info["file_size"],
                        file_path=attachment_info["file_path"],
                        thumbnail_path=attachment_info.get("thumbnail_path"),
                        is_image=attachment_info["is_image"]
                    )
                    
                    db.add(attachment_db)
                    message_attachments.append(attachment_db)
                    
                except ValueError as e:
                    # Log error using standardized security approach
                    if self.security_handler:
                        self.security_handler.secure_log(
                            "Attachment processing failed",
                            {"error": str(e), "sender_id": sender_id},
                            "warning"
                        )
                    raise HTTPException(status_code=400, detail=str(e))
        
        # Create delivery receipts for all participants
        participant_settings = db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.conversation_id == conversation_id_str
        ).all()
        
        recipient_ids = []
        for participant in participant_settings:
            print(f"Processing participant: {participant}")
            # Create receipt for both sender and recipients
            # For recipients: status = "sent"
            # For sender: status = "sent" (will be used for tracking delivery/read status)
            receipt_status = "sent"
            
            receipt = MessageReceiptDB(
                message_id=new_message.id,
                user_id=participant.user_id,
                status=receipt_status
            )
            db.add(receipt)
            print(f"Receipt created for user {participant.user_id}")
            print(f"Sender user_id: {sender_id}")
            # Only add non-senders to the recipient list for notifications
            if participant.user_id != sender_id:
                recipient_ids.append(participant.user_id)
                print(f"Adding user {participant.user_id} to recipient list")
                print(f"Current unread_count for user {participant.user_id}: {(participant.unread_count or 0) - 1}")
                # Increment unread_count for recipients (but not for sender)
                participant.unread_count = (participant.unread_count or 0) + 1
                print(f"Incrementing unread_count for user {participant.user_id} in conversation {conversation_id_str}: {(participant.unread_count or 0) - 1} -> {participant.unread_count}")
        
        # Update conversation last_message_at
        conversation.last_message_at = datetime.utcnow()
        print(f"Updated last_message_at for conversation {conversation_id_str}")
        # Commit the transaction
        db.commit()
        db.refresh(new_message)
        

        # Send real-time notification using standardized security approach
        # if self.notification_handler:
        #     # Convert to dict for notification
        #     message_dict = self._message_to_dict(new_message, include_attachments=True)
            
        #     # Don't send the actual content in the notification for security
        #     if "content" in message_dict:
        #         message_dict["content_preview"] = "New message"
        #         del message_dict["content"]
                
        #     await self.notification_handler.notify_new_message(message_dict, recipient_ids)
        
        # # Log the message creation using standardized security approach
        # if self.security_handler:
        #     self.security_handler.secure_log(
        #         "Message created",
        #         {
        #             "sender_id": sender_id,
        #             "conversation_id": conversation_id_str,
        #             "message_id": new_message.id,
        #             "message_type": message_data.message_type,
        #             "has_attachments": len(message_attachments) > 0
        #         }
        #     )
        
        return self._message_to_dict(new_message, include_attachments=True)
    
    async def get_message(self, db: Session, message_id: str, user_id: str) -> Dict[str, Any]:
        """
        Retrieve a single message.
        
        Args:
            db: Database session
            message_id: ID of the message to retrieve
            user_id: ID of the requesting user
            
        Returns:
            Message data
            
        Raises:
            HTTPException: If message retrieval fails
        """
        # Fetch the message
        message = db.query(MessageDB).filter(MessageDB.id == message_id).first()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Check if user has access to the conversation
        user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user_settings = db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.conversation_id == message.conversation_id,
            UserConversationSettingsDB.user_id == user_id_uuid
        ).first()
        
        if not user_settings:
            if self.security_handler:
                self.security_handler.secure_log(
                    "Unauthorized message access attempt",
                    {"user_id": user_id, "message_id": message_id},
                    "warning"
                )
            raise HTTPException(status_code=403, detail="Not authorized to view this message")
        
        # Decrypt the message content if needed using standardized security approach
        message_dict = self._message_to_dict(message, user_id=user_id, include_attachments=True)
        print("==message_dict==1", message_dict)
       
        # Update message receipt status if necessary
        receipt = db.query(MessageReceiptDB).filter(
            MessageReceiptDB.message_id == message_id,
            MessageReceiptDB.user_id == user_id
        ).first()
        print("==receipt==", receipt)
        # If message was delivered but not read, mark as read
        if receipt and receipt.status in ["sent", "delivered"]:
            receipt.status = "read"
            receipt.updated_at = datetime.utcnow()
            print(f"==Updated receipt {receipt.id} for message {message_id} from 'sent' to 'read'==")
            db.commit()
            # Notify sender about read status using standardized security approach
            if self.notification_handler:
                await self.notification_handler.notify_message_status(
                    message_id, message.conversation_id, user_id, "read"
                )
        print("==message_dict==", message_dict)
        return message_dict
    
    async def get_conversation_messages(self, db: Session, conversation_id: str, 
                                      user_id: str, limit: int = 50, 
                                      before_message_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve messages from a conversation.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the requesting user
            limit: Maximum number of messages to retrieve
            before_message_id: Retrieve messages before this ID (for pagination)
            
        Returns:
            List of messages
            
        Raises:
            HTTPException: If message retrieval fails
        """
        # Check if user has access to the conversation
        user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
      
        
        # Convertir conversation_id en chaîne si ce n'est pas déjà le cas
        conversation_id_str = str(conversation_id)

        user_settings = db.query(UserConversationSettingsDB).filter(
            UserConversationSettingsDB.conversation_id == conversation_id_str,
            UserConversationSettingsDB.user_id == user_id_uuid
        ).first()
        print("==user_settings==", user_settings)
        
        if not user_settings:
            if self.security_handler:
                self.security_handler.secure_log(
                    "Unauthorized conversation access attempt",
                    {"user_id": user_id, "conversation_id": conversation_id},
                    "warning"
                )
            raise HTTPException(status_code=403, detail="Not authorized to view this conversation")
        
        # Build the query
        from sqlalchemy.orm import joinedload
        query = db.query(MessageDB).options(
            joinedload(MessageDB.receipts)
        ).filter(MessageDB.conversation_id == conversation_id_str)
        
        # Apply pagination if before_message_id is specified
        if before_message_id:
            # Get the created_at timestamp of the specified message
            before_message = db.query(MessageDB).filter(MessageDB.id == before_message_id).first()
            if before_message:
                query = query.filter(MessageDB.created_at < before_message.created_at)
        
        # Order by created_at (newest first) and limit
        messages = query.order_by(MessageDB.created_at.desc()).limit(limit).all()
        
        print("==messages==", messages)
        
        # Update receipt statuses to delivered (but not read)
        for message in messages:
            message_id_str = str(message.id)
            # Get and update message receipt status if necessary
            receipt = db.query(MessageReceiptDB).filter(
                MessageReceiptDB.message_id == message_id_str,
                MessageReceiptDB.user_id == user_id
            ).first()
            print("==receipt status before update==", receipt.status if receipt else None)
            
            # Only update from "sent" to "delivered" - let the client explicitly mark as "read"
            if receipt and receipt.status == "sent":
                receipt.status = "delivered"
                receipt.updated_at = datetime.utcnow()
                print(f"==Updated receipt {receipt.id} for message {message_id_str} from 'sent' to 'delivered'==")
            elif receipt and receipt.status == "read":
                print(f"==Message {message_id_str} already marked as 'read', leaving status unchanged==")
        
        # Commit receipt updates before converting messages to dict
        db.commit()
        
        # Force SQLAlchemy to clear cached objects
        db.expire_all()
        
        # Reload messages with updated receipts explicitly including receipts relationship
        query = db.query(MessageDB).options(
            joinedload(MessageDB.receipts)
        ).filter(MessageDB.conversation_id == conversation_id_str)
        
        # Apply pagination if before_message_id is specified
        if before_message_id:
            before_message = db.query(MessageDB).filter(MessageDB.id == before_message_id).first()
            if before_message:
                query = query.filter(MessageDB.created_at < before_message.created_at)
                
        # Get fresh message objects with updated receipts
        messages = query.order_by(MessageDB.created_at.desc()).limit(limit).all()
        
        # Print receipts for debugging
        for message in messages:
            message_id_str = str(message.id)
            print(f"==Message {message_id_str} has {len(message.receipts) if hasattr(message, 'receipts') and message.receipts else 0} receipts==")
            if hasattr(message, 'receipts') and message.receipts:
                for receipt in message.receipts:
                    print(f"==Receipt for message {message_id_str}: user {receipt.user_id}, status {receipt.status}==")
        
        # Convert to dict and decrypt if needed
        message_dicts = []
        for message in messages:
            message_dict = self._message_to_dict(message, user_id=user_id, include_attachments=True)
            message_dicts.append(message_dict)

        # If any messages were marked as read, send a batch notification
        # In a real app, this would be optimized to send a single notification for all messages
        return message_dicts
    
    async def mark_conversation_as_read(self, db: Session, conversation_id: str, user_id: str) -> bool:
        """
        Mark all unread messages in a conversation as read for a specific user.
        
        Args:
            db: Database session
            conversation_id: ID of the conversation
            user_id: ID of the user marking messages as read
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            HTTPException: If user doesn't have access to the conversation
        """
        try:
            # Convert IDs to UUIDs if necessary
            user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            conversation_id_str = str(conversation_id)
            
            # Check if user has access to the conversation
            user_settings = db.query(UserConversationSettingsDB).filter(
                UserConversationSettingsDB.conversation_id == conversation_id_str,
                UserConversationSettingsDB.user_id == user_id_uuid
            ).first()
            
            if not user_settings:
                if self.security_handler:
                    self.security_handler.secure_log(
                        "Unauthorized conversation access attempt",
                        {"user_id": user_id, "conversation_id": conversation_id},
                        "warning"
                    )
                raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
            
            # Find all unread messages in this conversation for this user
            receipts = db.query(MessageReceiptDB).join(
                MessageDB, MessageReceiptDB.message_id == MessageDB.id
            ).filter(
                MessageDB.conversation_id == conversation_id_str,
                MessageReceiptDB.user_id == user_id_uuid,
                MessageReceiptDB.status.in_(["sent", "delivered"])
            ).all()
            
        
            if not receipts:
                # No unread messages
                return True
            
            # Update all receipts in a single operation
            now = datetime.utcnow()
            message_ids = []
            
            for receipt in receipts:
                receipt.status = "read"
                receipt.updated_at = now
                message_ids.append(receipt.message_id)
            
            # Commit changes
            db.commit()
            
            # Send status notifications for each message
            if self.notification_handler and message_ids:
                # In an optimized system, we could send a single notification for all messages
                for message_id in message_ids:
                    await self.notification_handler.notify_message_status(
                        message_id, conversation_id_str, user_id, "read"
                    )
            
            # Log the operation
            if self.security_handler:
                self.security_handler.secure_log(
                    "Messages marked as read",
                    {
                        "user_id": user_id,
                        "conversation_id": conversation_id_str,
                        "message_count": len(message_ids)
                    }
                )
            
            return True
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking conversation as read: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to mark conversation as read: {str(e)}")
    
    def _message_to_dict(self, message, user_id=None, include_attachments=False):
        """
        Convert a MessageDB object to a dictionary.
        
        Args:
            message: MessageDB object to convert
            user_id: User ID requesting the message (for decryption if necessary)
            include_attachments: If True, include attachments in the response
            
        Returns:
            Dict containing the message data
        """
        if not message:
            return None
            
        # Convert object to dictionary
        message_dict = {
            "id": str(message.id),
            "sender_id": str(message.sender_id),
            "conversation_id": str(message.conversation_id),
            "message_type": message.message_type,
            "content": message.content,
            "is_deleted": message.is_deleted,
            "is_edited": message.is_edited if hasattr(message, 'is_edited') else False,
            "is_forwarded": message.is_forwarded if hasattr(message, 'is_forwarded') else False,
            "is_encrypted": message.is_encrypted if hasattr(message, 'is_encrypted') else False,
            "created_at": message.created_at,
            "updated_at": message.updated_at if hasattr(message, 'updated_at') else message.created_at,
            "reply_to_message_id": message.reply_to_message_id
        }
        
        # Determine message status
        # By default, all sent messages have the "sent" status
        message_dict["status"] = "sent"
        
        # If the message has receipts, use the most advanced status
        print(f"==message {message.id} has receipts: {hasattr(message, 'receipts') and message.receipts!=None} count: {len(message.receipts) if hasattr(message, 'receipts') and message.receipts else 0}==")
        
        if hasattr(message, 'receipts') and message.receipts:
            # For the sender, show the most advanced status among recipients
            if user_id and str(message.sender_id) == str(user_id):
                # Priorité: read > delivered > sent
                status_priority = {"read": 3, "delivered": 2, "sent": 1}
                highest_status = "sent"
                highest_priority = 1
                
                print(f"==Checking all receipts for message {message.id} as sender==")
                for receipt in message.receipts:
                    print(f"==Receipt: {receipt.id}, user_id: {receipt.user_id}, status: {receipt.status}, priority: {status_priority.get(receipt.status, 0)}==")
                    if status_priority.get(receipt.status, 0) > highest_priority:
                        highest_status = receipt.status
                        highest_priority = status_priority[receipt.status]
                        print(f"==Updated highest status to {highest_status} with priority {highest_priority}==")
                
                print(f"==Final status for message {message.id}: {highest_status}==")
                message_dict["status"] = highest_status
            # For a recipient, show their own read status
            elif user_id:
                print(f"==Checking own receipt for message {message.id} as recipient==")
                for receipt in message.receipts:
                    if str(receipt.user_id) == str(user_id):
                        print(f"==Found own receipt with status: {receipt.status}==")
                        message_dict["status"] = receipt.status
                        break
        
        # If the message is encrypted and a user ID is provided, try to decrypt
        if message.is_encrypted and message.content and user_id and self.security_handler:
            try:
                print(f"==Attempting to decrypt message {message.id}==")
                print(f"==Content type: {type(message.content)}, length: {len(message.content) if message.content else 0}")
                print(f"==Conversation ID: {str(message.conversation_id)}")
                print(f"==User ID: {str(user_id)}")
                
                # Use the content directly for development if decryption fails
                # In a production environment, you should remove this line
                message_dict["content"] = message.content
                
                # Attempt decryption
                decrypted_content = self.security_handler.decrypt_message(
                    message.content, 
                    str(message.conversation_id), 
                    str(user_id)
                )
                message_dict["content"] = decrypted_content
                print(f"==Successfully decrypted message: {decrypted_content[:30]}...")
            except Exception as e:
                print(f"==Decryption error: {str(e)}")
                logger.error(f"Failed to decrypt message {message.id}: {str(e)}")
                # For development, return the raw content if decryption fails
                if not message_dict.get("content"):
                    message_dict["content"] = f"[Encrypted content not decryptable]"
        
        # Include receipts in the response if available
        if hasattr(message, 'receipts') and message.receipts:
            message_dict["receipts"] = [
                {
                    "id": str(receipt.id),
                    "message_id": str(message.id),  
                    "user_id": str(receipt.user_id),
                    "status": receipt.status,
                    "created_at": receipt.created_at,
                    "updated_at": receipt.updated_at if hasattr(receipt, 'updated_at') else receipt.created_at
                }
                for receipt in message.receipts
            ]
        
        # Include attachments if requested
        if include_attachments and hasattr(message, 'attachments'):
            attachments = []
            for attachment in message.attachments:
                attachment_dict = {
                    "id": str(attachment.id),
                    "file_name": attachment.file_name,
                    "file_type": attachment.file_type,
                    "file_size": attachment.file_size,
                    "file_path": attachment.file_path,
                    "is_image": attachment.is_image,
                }
                
                if attachment.thumbnail_path:
                    attachment_dict["thumbnail_path"] = attachment.thumbnail_path
                    
                attachments.append(attachment_dict)
                
            message_dict["attachments"] = attachments
        return message_dict
        
    async def update_message(self, db: Session, message_id: str, user_id: str, 
                           update_data: MessageUpdate) -> Dict[str, Any]:
        """
        Update a message.
        
        Args:
            db: Database session
            message_id: ID of the message to update
            user_id: ID of the requesting user (must be the sender)
            update_data: Updated message data
            
        Returns:
            Updated message data
            
        Raises:
            HTTPException: If message update fails
        """
        # Fetch the message
        message = db.query(MessageDB).filter(MessageDB.id == message_id).first()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Check if user is the sender
        if message.sender_id != user_id:
            if self.security_handler:
                self.security_handler.secure_log(
                    "Unauthorized message update attempt",
                    {"user_id": user_id, "message_id": message_id},
                    "warning"
                )
            raise HTTPException(status_code=403, detail="Only the sender can update this message")
        
        # Handle deletion
        if update_data.is_deleted is not None:
            message.is_deleted = update_data.is_deleted
            
            # If deleting, no need to process content
            if update_data.is_deleted:
                message.updated_at = datetime.utcnow()
                db.commit()
                
                # Log the deletion using standardized security approach
                if self.security_handler:
                    self.security_handler.secure_log(
                        "Message deleted",
                        {"user_id": user_id, "message_id": message_id},
                        "info"
                    )
                
                # Notify other participants
                if self.notification_handler:
                    # Get other participants
                    participant_settings = db.query(UserConversationSettingsDB).filter(
                        UserConversationSettingsDB.conversation_id == message.conversation_id,
                        UserConversationSettingsDB.user_id != user_id
                    ).all()
                    
                    recipient_ids = [p.user_id for p in participant_settings]
                    
                    await self.notification_handler.notify_conversation_update(
                        message.conversation_id,
                        "message_deleted",
                        {"message_id": message_id},
                        recipient_ids
                    )
                
                return self._message_to_dict(message)
        
        # Handle content update
        if update_data.content is not None:
            # Validate updated content using standardized security approach
            if self.security_handler:
                is_valid = self.security_handler.validate_message_request({"content": update_data.content})
                if not is_valid:
                    raise HTTPException(status_code=400, detail="Invalid message content")
            
            # Process content based on conversation encryption setting
            content = update_data.content
            
            # Get conversation to check encryption setting
            conversation = db.query(ConversationDB).filter(
                ConversationDB.id == message.conversation_id
            ).first()
            
            is_encrypted = conversation and conversation.is_encrypted
            
            # Encrypt content if needed using standardized security approach
            if is_encrypted and content and self.security_handler:
                encrypted_content = self.security_handler.encrypt_message(content, message.conversation_id)
                content = encrypted_content
            
            message.content = content
            message.is_edited = True
            message.updated_at = datetime.utcnow()
            
            db.commit()
            
            # Log the update using standardized security approach
            if self.security_handler:
                self.security_handler.secure_log(
                    "Message updated",
                    {"user_id": user_id, "message_id": message_id},
                    "info"
                )
            
            # Notify other participants
            if self.notification_handler:
                # Get other participants
                participant_settings = db.query(UserConversationSettingsDB).filter(
                    UserConversationSettingsDB.conversation_id == message.conversation_id,
                    UserConversationSettingsDB.user_id != user_id
                ).all()
                
                recipient_ids = [p.user_id for p in participant_settings]
                
                await self.notification_handler.notify_conversation_update(
                    message.conversation_id,
                    "message_edited",
                    {"message_id": message_id},
                    recipient_ids
                )
        
        return self._message_to_dict(message, user_id=user_id, include_attachments=True)
