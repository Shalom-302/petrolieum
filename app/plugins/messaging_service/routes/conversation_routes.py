"""
Conversation Routes

This module defines API routes for conversation handling in the messaging service,
implementing the standardized security approach across all endpoints.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from fastapi import status

from ..services.conversation_service import ConversationService
from ..schemas.conversation import (
    DirectConversationCreate, GroupConversationCreate,
    ConversationUpdate, GroupConversationUpdate, ConversationMemberAction,
    ConversationResponse, GroupConversationResponse, ConversationListResponse,
    UserConversationSettingsUpdate, UserBlockBase, UserBlockResponse,
    ChatUserResponse
)
from ..main import messaging_service, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter()
conversation_service = ConversationService()


@router.post("/conversations/direct", response_model=ConversationResponse)
async def create_direct_conversation(
    conversation_data: DirectConversationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new direct (one-to-one) conversation.
    
    Security:
    - Authentication required
    - Validation of recipient ID
    - Check for blocked users
    - Secure conversation key generation if encrypted
    """
    # Get user ID
    print("===Current user:", conversation_data)
    user_id = current_user.id
    
    try:

        # Securely create the conversation using the standardized approach
        conversation = await conversation_service.create_direct_conversation(
            db, conversation_data, user_id
        )
        print("===Conversation created:", conversation)
        return conversation
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error creating direct conversation",
                {"user_id": user_id, "recipient_id": conversation_data.recipient_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@router.post("/conversations/group", response_model=GroupConversationResponse)
async def create_group_conversation(
    conversation_data: GroupConversationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new group conversation.
    
    Security:
    - Authentication required
    - Validation of participant IDs
    - Check for blocked users
    - Secure conversation key generation if encrypted
    - Validation of group settings
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # Securely create the group conversation using the standardized approach
        conversation = await conversation_service.create_group_conversation(
            db, conversation_data, user_id
        )
        return conversation
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error creating group conversation",
                {
                    "user_id": user_id, 
                    "participant_count": len(conversation_data.participant_ids), 
                    "error": str(e)
                },
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to create group conversation")


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    archived: bool = Query(False),
    conversation_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all conversations for the current user.
    
    Security:
    - Authentication required
    - Pagination to prevent abuse
    - Secure decryption of sensitive data
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # Securely retrieve conversations using the standardized approach
        conversations = await conversation_service.get_conversations(
            db, user_id, limit, offset, archived, conversation_type
        )
        return conversations
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error retrieving conversations",
                {"user_id": user_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to retrieve conversations")


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get a single conversation by ID.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    - Secure decryption of sensitive data
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # Securely retrieve the conversation using the standardized approach
        conversation = await conversation_service.get_conversation(
            db, conversation_id, user_id
        )
        return conversation
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Securely log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error retrieving conversation",
                {"user_id": user_id, "conversation_id": conversation_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation")


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    update_data: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update a conversation's basic details.
    
    Security:
    - Authentication required
    - Authorization check (must be admin for groups)
    - Secure encryption of sensitive metadata
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing an update method in the conversation service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Conversation update requested",
            {
                "user_id": user_id, 
                "conversation_id": conversation_id
            }
        )
    
    raise HTTPException(status_code=501, detail="Conversation update not implemented yet")


@router.patch("/conversations/group/{conversation_id}", response_model=GroupConversationResponse)
async def update_group_conversation(
    conversation_id: str,
    update_data: GroupConversationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update a group conversation's settings.
    
    Security:
    - Authentication required
    - Authorization check (must be admin)
    - Validation of group settings
    - Secure encryption of sensitive metadata
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing a group update method in the conversation service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Group conversation update requested",
            {
                "user_id": user_id, 
                "conversation_id": conversation_id
            }
        )
    
    raise HTTPException(status_code=501, detail="Group conversation update not implemented yet")


@router.patch("/conversations/{conversation_id}/settings", response_model=ConversationResponse)
async def update_conversation_settings(
    conversation_id: str,
    settings_update: UserConversationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update user-specific settings for a conversation.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    - Validation of setting values
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing a settings update method in the conversation service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Conversation settings update requested",
            {
                "user_id": user_id, 
                "conversation_id": conversation_id
            }
        )
    
    raise HTTPException(status_code=501, detail="Conversation settings update not implemented yet")


@router.post("/conversations/{conversation_id}/members", response_model=ConversationResponse)
async def add_conversation_member(
    conversation_id: str,
    member_data: ConversationMemberAction,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Add a new member to a group conversation.
    
    Security:
    - Authentication required
    - Authorization check (must have permission to invite)
    - Check for blocked users
    - Validation of member role
    """
    # Get user ID
    user_id = current_user.id
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Add conversation member requested",
            {
                "user_id": user_id, 
                "conversation_id": conversation_id,
                "new_member_id": member_data.user_id
            }
        )
    
    # Call the service method to add the member
    return await conversation_service.add_conversation_member(
        db, conversation_id, user_id, member_data.user_id
    )


@router.delete("/conversations/{conversation_id}/members/{member_id}", response_model=ConversationResponse)
async def remove_conversation_member(
    conversation_id: str,
    member_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Remove a member from a group conversation.
    
    Security:
    - Authentication required
    - Authorization check (must have permission to remove)
    - Validation of target member
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing a member remove method in the conversation service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Remove conversation member requested",
            {
                "user_id": user_id, 
                "conversation_id": conversation_id,
                "member_id": member_id
            }
        )
    
    raise HTTPException(status_code=501, detail="Remove conversation member not implemented yet")


@router.delete("/conversations/{conversation_id}", response_model=Dict[str, Any])
async def leave_or_delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Leave a group conversation or delete a direct conversation.
    
    Security:
    - Authentication required
    - Authorization check
    - Secure cleanup of conversation data
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # Call the service method to handle the deletion logic
        result = await conversation_service.delete_conversation(db, conversation_id, user_id)
        
        # Securely log the action using standardized approach
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Conversation deleted or left",
                {
                    "user_id": user_id, 
                    "conversation_id": conversation_id,
                    "result": result["message"]
                }
            )
        
        return result
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error deleting/leaving conversation",
                {
                    "user_id": user_id, 
                    "conversation_id": conversation_id,
                    "error": str(e)
                },
                "error"
            )
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")


@router.post("/conversations/{conversation_id}/read", response_model=Dict[str, bool])
async def mark_conversation_as_read(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Mark all messages in a conversation as read for the current user.
    
    Security:
    - Authentication required
    - Authorization check for conversation access
    """
    # Get user ID
    user_id = current_user.id
    
    try:
        # Call the service method to mark the conversation as read
        success = await conversation_service.mark_conversation_as_read(
            db, conversation_id, user_id
        )
        
        # Securely log the action using standardized approach
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Conversation marked as read",
                {
                    "user_id": user_id, 
                    "conversation_id": conversation_id
                }
            )
        
        return {"success": success}
    except HTTPException as e:
        # Rethrow HTTP exceptions
        raise e
    except Exception as e:
        # Log the error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error marking conversation as read",
                {"user_id": user_id, "conversation_id": conversation_id, "error": str(e)},
                "error"
            )
        raise HTTPException(status_code=500, detail=f"Failed to mark conversation as read: {str(e)}")


@router.post("/blocks", response_model=UserBlockResponse)
async def block_user(
    block_data: UserBlockBase,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Block a user from messaging.
    
    Security:
    - Authentication required
    - Validation of blocked user ID
    - Secure logging of block action
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing a block user method in the conversation service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Block user requested",
            {
                "user_id": user_id, 
                "blocked_id": block_data.blocked_id
            }
        )
    
    raise HTTPException(status_code=501, detail="Block user not implemented yet")


@router.get("/blocks", response_model=List[UserBlockResponse])
async def get_blocked_users(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all users blocked by the current user.
    
    Security:
    - Authentication required
    - Secure retrieval of block data
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing a get blocked users method in the conversation service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Get blocked users requested",
            {"user_id": user_id}
        )
    
    raise HTTPException(status_code=501, detail="Get blocked users not implemented yet")


@router.delete("/blocks/{blocked_id}", response_model=Dict[str, Any])
async def unblock_user(
    blocked_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Unblock a previously blocked user.
    
    Security:
    - Authentication required
    - Validation of blocked user ID
    - Secure logging of unblock action
    """
    # Get user ID
    user_id = current_user.id
    
    # This would require implementing an unblock user method in the conversation service
    # For now, we'll raise a not implemented error
    
    # Securely log the request using standardized approach
    if messaging_service.security_handler:
        messaging_service.security_handler.secure_log(
            "Unblock user requested",
            {
                "user_id": user_id, 
                "blocked_id": blocked_id
            }
        )
    
    raise HTTPException(status_code=501, detail="Unblock user not implemented yet")


@router.get("/users/search", response_model=List[ChatUserResponse])
async def search_chat_users(
    query: str = Query(None, min_length=1, max_length=50, description="Search term for username, first name, or last name"),
    limit: int = Query(20, gt=0, le=50, description="Maximum number of results to return"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Search for users to chat with based on username or name.
    
    Security:
    - Authentication required
    - Input validation
    - Rate limiting
    - Does not expose sensitive user information
    """
    # Get user ID
    print("===Current-- user:", current_user)
    user_id = current_user.id
    
    logger.info(f"Searching users with query: '{query}', limit: {limit}, current user ID: {user_id}")
    
    try:
        users = await conversation_service.search_users_for_chat(
            db, user_id, query, limit
        )
        logger.info(f"Found {len(users)} users matching query '{query}'")
        return users
    except HTTPException as e:
        logger.error(f"Error searching users: {str(e)}")
        db.rollback()  # Rollback transaction to allow future queries to work
        raise
    except Exception as e:
        logger.error(f"Unexpected error in search_chat_users: {str(e)}")
        db.rollback()  # Rollback transaction to allow future queries to work
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for users"
        )


def init_routes(service: ConversationService):
    """Initialize conversation service routes with the service instance."""
    global conversation_service
    conversation_service = service
    return router
