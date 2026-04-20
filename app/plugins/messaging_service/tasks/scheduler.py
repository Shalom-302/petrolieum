"""
Task Scheduler

This module defines scheduled tasks for the messaging service,
implementing the standardized security approach for background operations.
"""
import logging
import asyncio
import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.core.db import get_db
from ..models import (
    MessageDB, ConversationDB, MessageAttachmentDB,
    MessageDeliveryStatusDB, UserConversationSettingsDB
)
from ..main import messaging_service

logger = logging.getLogger(__name__)


async def cleanup_old_messages():
    """
    Clean up messages older than the retention period.
    Implements standardized security approach for sensitive data cleanup.
    """
    # Get retention period from configuration
    retention_days = messaging_service.config.get("message_retention_days", 365)
    cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
    
    try:
        # Use dependency injection to get database session
        db = next(get_db())
        
        # Securely log task start using standardized approach
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Starting old message cleanup task",
                {"retention_days": retention_days, "cutoff_date": cutoff_date.isoformat()}
            )
        
        # Find messages to delete
        old_messages = db.query(MessageDB).filter(
            MessageDB.created_at < cutoff_date
        ).all()
        
        if not old_messages:
            logger.info("No old messages to clean up")
            return
        
        # Securely log the number of messages to be deleted
        message_count = len(old_messages)
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Found old messages to clean up",
                {"message_count": message_count}
            )
        
        # Delete message attachments first (if file handler available)
        if messaging_service.file_handler:
            for message in old_messages:
                for attachment in message.attachments:
                    # Delete the actual file securely
                    await messaging_service.file_handler.delete_file(
                        attachment.file_path, 
                        secure_delete=True
                    )
                    
                    # Delete thumbnail if exists
                    if attachment.thumbnail_path:
                        await messaging_service.file_handler.delete_file(
                            attachment.thumbnail_path,
                            secure_delete=True
                        )
        
        # Delete messages from database
        for message in old_messages:
            db.delete(message)
            
        db.commit()
        
        # Securely log task completion
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Completed old message cleanup task",
                {"messages_deleted": message_count}
            )
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up old messages: {str(e)}")
        
        # Securely log error using standardized approach
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error in old message cleanup task",
                {"error": str(e)},
                "error"
            )


async def process_pending_notifications():
    """
    Process pending notifications that may have failed to send immediately.
    Implements standardized security approach for notification handling.
    """
    try:
        # Only proceed if notification handler is available
        if not messaging_service.notification_handler:
            return
            
        # Securely log task start
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Starting pending notification processing task"
            )
            
        # Process pending notifications
        processed_count = await messaging_service.notification_handler.process_pending_notifications()
        
        # Securely log task completion
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Completed pending notification processing task",
                {"notifications_processed": processed_count}
            )
            
    except Exception as e:
        logger.error(f"Error processing pending notifications: {str(e)}")
        
        # Securely log error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error in pending notification processing task",
                {"error": str(e)},
                "error"
            )


async def update_conversation_last_activity():
    """
    Update last activity timestamps for conversations.
    Ensures accurate tracking of conversation activity.
    """
    try:
        # Get database session
        db = next(get_db())
        
        # Securely log task start
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Starting conversation last activity update task"
            )
            
        # Find conversations with messages newer than their last_message_at
        conversations_to_update = db.query(ConversationDB).filter(
            ConversationDB.id.in_(
                db.query(MessageDB.conversation_id).filter(
                    or_(
                        ConversationDB.last_message_at.is_(None),
                        MessageDB.created_at > ConversationDB.last_message_at
                    )
                ).distinct()
            )
        ).all()
        
        if not conversations_to_update:
            logger.info("No conversations need last_message_at updates")
            return
            
        update_count = 0
        
        # Update each conversation with the timestamp of its most recent message
        for conversation in conversations_to_update:
            last_message = db.query(MessageDB).filter(
                MessageDB.conversation_id == conversation.id
            ).order_by(desc(MessageDB.created_at)).first()
            
            if last_message:
                conversation.last_message_at = last_message.created_at
                update_count += 1
                
        db.commit()
        
        # Securely log task completion
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Completed conversation last activity update task",
                {"conversations_updated": update_count}
            )
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating conversation activity: {str(e)}")
        
        # Securely log error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error in conversation last activity update task",
                {"error": str(e)},
                "error"
            )


async def run_scheduled_tasks():
    """Runs all scheduled tasks in sequence."""
    logger.info("Running scheduled messaging service tasks")
    
    try:
        # Run all tasks in sequence
        await cleanup_old_messages()
        await process_pending_notifications()
        await update_conversation_last_activity()
        
        logger.info("Scheduled messaging service tasks completed")
        
    except Exception as e:
        logger.error(f"Error running scheduled tasks: {str(e)}")
        
        # Securely log error
        if messaging_service.security_handler:
            messaging_service.security_handler.secure_log(
                "Error running scheduled messaging tasks",
                {"error": str(e)},
                "error"
            )


def initialize_scheduled_tasks():
    """
    Initialize all scheduled tasks for the messaging service.
    This would typically integrate with the application's task scheduler.
    """
    logger.info("Initializing messaging service scheduled tasks")
    
    # In a real implementation, this would register the tasks with the
    # application's task scheduler system (like Celery, APScheduler, etc.)
    #
    # Example with a hypothetical scheduler:
    # 
    # scheduler.add_job(
    #     cleanup_old_messages,
    #     'interval',
    #     hours=24,
    #     id='messaging_cleanup_old_messages'
    # )
    #
    # scheduler.add_job(
    #     process_pending_notifications,
    #     'interval',
    #     minutes=15,
    #     id='messaging_process_pending_notifications'
    # )
    #
    # scheduler.add_job(
    #     update_conversation_last_activity,
    #     'interval',
    #     hours=1,
    #     id='messaging_update_conversation_activity'
    # )
    
    logger.info("Messaging service scheduled tasks initialized")
    
    return True
