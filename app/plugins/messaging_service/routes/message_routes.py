"""
Message Routes

This module defines API routes for message handling in the messaging service,
implementing the standardized security approach across all endpoints.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, Query
from sqlalchemy.orm import Session
from datetime import datetime

from ..services.message_service import MessageService
from ..schemas.message import (
    MessageCreate, MessageUpdate, MessageResponse, MessageSearchRequest,
    BulkMessagesRequest, ForwardMessageRequest, BulkDeleteMessagesRequest,
    MessageStatusUpdateRequest
)
from ..main import messaging_service, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter()
message_service = MessageService()


@router.post("/messages", response_model=MessageResponse)
async def create_message(
    message_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new message in a conversation.
    
    Security: 
    - Authentication required
    - Content validation for XSS and other attacks
    - Message encryption if conversation is encrypted
    """
    # Get user ID
    user_id = current_user.id
    logger.info(f"Creating message with user_id: {user_id}")
    logger.info(f"Message data received: {message_data}")
    
    try:
        # Convertir en objet MessageCreate
        message_create = MessageCreate(**message_data)
        
        # Securely create the message using the standardized approach
        message = await message_service.create_message(
            db, message_create, user_id, None
        )
        logger.info(f"Message created successfully with ID: {message.get('id', 'unknown')}")
        
        # S'assurer que tous les champs requis par MessageResponse sont présents
        if 'updated_at' not in message:
            message['updated_at'] = message.get('created_at')
        if 'is_edited' not in message:
            message['is_edited'] = False
        if 'is_forwarded' not in message:
            message['is_forwarded'] = False
        if 'is_encrypted' not in message:
            message['is_encrypted'] = False
        if 'conversation_id' not in message:
            message['conversation_id'] = message_create.conversation_id
            
        # Diffuser le message par WebSocket à tous les utilisateurs de la conversation
        try:
            if messaging_service.websocket_manager:
                logger.info(f"Diffusion WebSocket du message {message.get('id')} à la conversation {message['conversation_id']}")
                await messaging_service.websocket_manager.broadcast_to_conversation(
                    message['conversation_id'],
                    {
                        "type": "message",  # Type attendu par le frontend
                        "data": message
                    },
                    exclude_user_id=user_id  # Exclure l'expéditeur qui a déjà le message
                )
                logger.info(f"Message diffusé avec succès par WebSocket")
        except Exception as ws_error:
            # Log l'erreur mais ne pas interrompre la réponse HTTP
            logger.error(f"Erreur lors de la diffusion WebSocket: {str(ws_error)}")
            
        return message
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error creating message",
                {"user_id": user_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to create message")


@router.post("/messages/with-attachment", response_model=MessageResponse)
async def create_message_with_attachment(
    message_data: MessageCreate = Body(...),
    attachments: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new message in a conversation with attachments.
    
    Security: 
    - Authentication required
    - Content validation for XSS and other attacks
    - Message encryption if conversation is encrypted
    """
    # Get user ID
    user_id = current_user.id
    logger.info(f"Creating message with user_id: {user_id}")
    logger.info(f"Message data received: {message_data.dict()}")
    
    try:
        # Securely create the message using the standardized approach
        message = await message_service.create_message(
            db, message_data, user_id, attachments
        )
        logger.info(f"Message created successfully with ID: {message.get('id', 'unknown')}")
        
        # Diffuser le message par WebSocket à tous les utilisateurs de la conversation
        try:
            if messaging_service.websocket_manager:
                logger.info(f"Diffusion WebSocket du message {message.get('id')} à la conversation {message['conversation_id']}")
                await messaging_service.websocket_manager.broadcast_to_conversation(
                    message['conversation_id'],
                    {
                        "type": "message",  # Type attendu par le frontend
                        "data": message
                    },
                    exclude_user_id=user_id  # Exclure l'expéditeur qui a déjà le message
                )
                logger.info(f"Message diffusé avec succès par WebSocket")
        except Exception as ws_error:
            # Log l'erreur mais ne pas interrompre la réponse HTTP
            logger.error(f"Erreur lors de la diffusion WebSocket: {str(ws_error)}")
            
        return message
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error creating message",
                {"user_id": user_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to create message")


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get a single message by ID.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    - Secure decryption of message content
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # Securely retrieve the message using the standardized approach
        message = await message_service.get_message(db, message_id, user_id)
        return message
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error retrieving message",
                {"user_id": user_id, "message_id": message_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to retrieve message")


@router.post("/messages/bulk", response_model=List[MessageResponse])
async def get_messages(
    request: BulkMessagesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get multiple messages from a conversation.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    - Secure decryption of message content
    - Rate limiting and pagination to prevent abuse
    """
    # Get user ID
    user_id = current_user.id
    try:
        # Securely retrieve messages using the standardized approach
        messages = await message_service.get_conversation_messages(
            db, 
            request.conversation_id, 
            user_id, 
            request.limit, 
            request.before_message_id
        )
        return messages
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error retrieving messages",
                {
                    "user_id": user_id, 
                    "conversation_id": request.conversation_id, 
                    "error": str(e)
                },
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: str,
    update_data: MessageUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update a message (edit content or delete).
    
    Security:
    - Authentication required
    - Authorization check (only sender can update)
    - Content validation for XSS and other attacks
    - Secure encryption of updated content
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # Securely update the message using the standardized approach
        message = await message_service.update_message(
            db, message_id, user_id, update_data
        )
        return message
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error updating message",
                {"user_id": user_id, "message_id": message_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to update message")


@router.post("/messages/search", response_model=List[MessageResponse])
async def search_messages(
    search_request: MessageSearchRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Search for messages with specific criteria.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    - Rate limiting to prevent abuse
    - Secure decryption of message content
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing a search method in the message service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Message search requested",
            {
                "user_id": user_id, 
                "conversation_id": search_request.conversation_id,
                "query": search_request.query
            }
        )
    
    raise HTTPException(status_code=501, detail="Message search not implemented yet")


@router.post("/messages/forward", response_model=List[MessageResponse])
async def forward_message(
    forward_request: ForwardMessageRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Forward a message to other conversations.
    
    Security:
    - Authentication required
    - Authorization check for both source and target conversations
    - Secure handling of message content
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing a forward method in the message service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Message forward requested",
            {
                "user_id": user_id, 
                "message_id": forward_request.message_id,
                "target_count": len(forward_request.target_conversation_ids)
            }
        )
    
    raise HTTPException(status_code=501, detail="Message forwarding not implemented yet")


@router.post("/messages/status", response_model=Dict[str, Any])
async def update_message_status(
    status_request: MessageStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update message delivery/read status.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    - Validation of status values
    """
    # Get user ID
    user_id = current_user.id
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Message status update requested",
            {
                "user_id": user_id, 
                "message_count": len(status_request.message_ids),
                "status": status_request.status
            }
        )
    
    # Validate the status value
    valid_statuses = ["sent", "delivered", "read"]
    if status_request.status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    # Update the status for each message
    updated_count = 0
    conversation_updates = {}  # Pour suivre les mises à jour par conversation
    
    for message_id in status_request.message_ids:
        try:
            # Get the message to check access rights
            message = db.query(MessageDB).filter(MessageDB.id == message_id).first()
            if not message:
                continue
                
            # Check if user has access to the conversation
            user_settings = db.query(UserConversationSettingsDB).filter(
                UserConversationSettingsDB.conversation_id == message.conversation_id,
                UserConversationSettingsDB.user_id == user_id
            ).first()
            
            if not user_settings:
                continue  # Skip if no access
            
            # Update or create receipt
            receipt = db.query(MessageReceiptDB).filter(
                MessageReceiptDB.message_id == message_id,
                MessageReceiptDB.user_id == user_id
            ).first()
            
            if receipt:
                # Seulement mettre à jour si le nouveau statut est plus "élevé"
                status_priority = {"read": 3, "delivered": 2, "sent": 1}
                current_status = receipt.status.lower() if receipt.status else "sent"
                new_status = status_request.status.lower()
                
                if status_priority.get(new_status, 0) > status_priority.get(current_status, 0):
                    old_status = receipt.status
                    receipt.status = new_status
                    receipt.updated_at = datetime.now(datetime.timezone.utc)
                    
                    # Si on passe à "read", compter pour la mise à jour du unread_count
                    if new_status == "read" and current_status != "read":
                        # Ajouter à notre dict de suivi par conversation
                        conv_id = str(message.conversation_id)
                        if conv_id not in conversation_updates:
                            conversation_updates[conv_id] = 1
                        else:
                            conversation_updates[conv_id] += 1
            else:
                # Create new receipt
                receipt = MessageReceiptDB(
                    message_id=message_id,
                    user_id=user_id,
                    status=status_request.status.lower()
                )
                db.add(receipt)
                
                # Si le nouveau statut est "read", compter pour le unread_count
                if status_request.status.lower() == "read":
                    conv_id = str(message.conversation_id)
                    if conv_id not in conversation_updates:
                        conversation_updates[conv_id] = 1
                    else:
                        conversation_updates[conv_id] += 1
            
            updated_count += 1
        except Exception as e:
            logger.error(f"Error updating message status: {str(e)}")
            # Continue with other messages even if one fails
    
    # Commit changes
    db.commit()
    
    # Mettre à jour les compteurs de messages non lus pour chaque conversation
    if status_request.status.lower() == "read" and conversation_updates:
        for conv_id, count in conversation_updates.items():
            settings = db.query(UserConversationSettingsDB).filter(
                UserConversationSettingsDB.conversation_id == conv_id,
                UserConversationSettingsDB.user_id == user_id
            ).first()
            
            if settings:
                # Calculer le nouveau nombre de messages non lus (ne jamais descendre en dessous de 0)
                current_unread = settings.unread_count or 0
                settings.unread_count = max(0, current_unread - count)
                print(f"Mise à jour unread_count pour conversation {conv_id}: {current_unread} -> {settings.unread_count}")
        
        # Enregistrer les mises à jour des compteurs
        db.commit()
    
    # Notify about the status changes
    if messaging_service.notification_handler and updated_count > 0:
        for message_id in status_request.message_ids:
            message = db.query(MessageDB).filter(MessageDB.id == message_id).first()
            if message:
                await messaging_service.notification_handler.notify_message_status(
                    message_id, 
                    message.conversation_id, 
                    str(user_id), 
                    status_request.status.lower()
                )
    
    return {"success": True, "updated_count": updated_count}


@router.post("/messages/delete-bulk", response_model=Dict[str, Any])
async def delete_messages_bulk(
    delete_request: BulkDeleteMessagesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete multiple messages at once.
    
    Security:
    - Authentication required
    - Authorization check (only sender can delete for everyone)
    - Rate limiting to prevent abuse
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing a bulk delete method in the message service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Bulk message delete requested",
            {
                "user_id": user_id, 
                "message_count": len(delete_request.message_ids),
                "delete_for_everyone": delete_request.delete_for_everyone
            }
        )
    
    raise HTTPException(status_code=501, detail="Bulk message deletion not implemented yet")


@router.get("/messages/typing/{conversation_id}")
async def send_typing_notification(
    conversation_id: str,
    is_typing: bool = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Send typing status notification to conversation participants.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    - Rate limiting to prevent abuse
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # This requires integration with the notification handler
        if messaging_service.notification_handler:
            await messaging_service.notification_handler.notify_typing_status(
                conversation_id, user_id, is_typing
            )
            
            return {"status": "success"}
        else:
            raise HTTPException(status_code=503, detail="Notification service not available")
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error sending typing notification",
                {
                    "user_id": user_id, 
                    "conversation_id": conversation_id, 
                    "error": str(e)
                },
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to send typing notification")


@router.post("/conversations/{conversation_id}/mark-read", response_model=Dict[str, bool])
async def mark_conversation_as_read(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Mark all unread messages in a conversation as read.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    - Rate limiting to prevent abuse
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # Marquer les messages comme lus
        success = await message_service.mark_conversation_as_read(db, conversation_id, user_id)
        return {"success": success}
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error marking conversation as read",
                {"user_id": user_id, "conversation_id": conversation_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to mark conversation as read")


def init_routes(service: MessageService):
    """Initialize message service routes with the service instance."""
    global message_service
    message_service = service
    return router
