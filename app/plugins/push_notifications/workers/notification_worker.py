"""
Notification Worker for Push Notifications

This module implements the worker for asynchronous processing of push notifications,
following the standardized security approach.
"""

import logging
import json
import time
import os
import signal
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
import pika
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker

from app.core.db.session import SessionLocal
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler
from app.plugins.push_notifications.handlers.redis_handler import RedisHandler
from app.plugins.push_notifications.handlers.rabbitmq_handler import RabbitMQHandler
from app.plugins.push_notifications.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

class NotificationWorker:
    """
    Worker for processing push notifications asynchronously,
    implementing the standardized security approach.
    """
    
    def __init__(self):
        """Initialize the notification worker."""
        self.running = False
        self.connection = None
        self.channel = None
        self.security_handler = SecurityHandler()
        self.redis_handler = None
        self.rabbitmq_handler = None
        
        try:
            # Initialize Redis if available
            self.redis_handler = RedisHandler()
            logger.info("Redis handler initialized successfully")
        except Exception as e:
            # Log as a warning, as Redis might not be essential for all operations
            logger.warning(f"Could not initialize Redis handler: {e}. Scheduled notifications might not work.")
        
        try:
            # Initialize RabbitMQ handler
            self.rabbitmq_handler = RabbitMQHandler()
            logger.info("RabbitMQ handler initialized successfully")
        except Exception as e:
            # This is critical for the worker, so we log an error and raise an exception
            logger.error(f"Fatal: RabbitMQ handler initialization failed: {e}")
            # The worker cannot run without RabbitMQ, so we stop initialization.
            raise RuntimeError("Failed to initialize RabbitMQ handler. Worker cannot start.") from e
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)
        
        logger.info("Notification worker initialized")
    
    def connect(self) -> bool:
        """
        Connect to RabbitMQ.
        
        Returns:
            bool: Success status
        """
        try:
            # Use the RabbitMQ handler to get configuration
            self.connection = self.rabbitmq_handler.get_connection()
            self.channel = self.connection.channel()
            
            # Ensure the queue exists
            self.channel.queue_declare(
                queue="push_notifications",
                durable=True,
                arguments={"x-max-priority": 10}  # Support message priorities
            )
            
            # Set QoS prefetch to control concurrency
            self.channel.basic_qos(prefetch_count=1)
            
            logger.info("Connected to RabbitMQ")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            return False
    
    def process_message(self, ch, method, properties, body) -> None:
        """
        Process a message from the queue.
        
        Args:
            ch: Channel object
            method: Method frame
            properties: Properties
            body: Message body
        """
        try:
            # Log secure audit trail
            logger.info(f"Received message: {method.delivery_tag}")
            
            # Parse message
            message = json.loads(body)
            action = message.get("action")
            
            # Create database session
            db = SessionLocal()
            
            try:
                # Create notification service
                notification_service = NotificationService(
                    db,
                    self.security_handler,
                    self.redis_handler,
                    self.rabbitmq_handler
                )
                
                # Process based on action
                if action == "send_notification":
                    notification_id = message.get("notification_id")
                    user_ids = message.get("user_ids", [])
                    title = message.get("title")
                    body = message.get("body")
                    data = message.get("data")
                    high_priority = message.get("priority", False)
                    
                    if not all([notification_id, user_ids, title, body]):
                        raise ValueError("Missing required fields for send_notification")
                    
                    # Send notification to users
                    result = notification_service.send_notification_to_users(
                        notification_id=notification_id,
                        user_ids=user_ids,
                        title=title,
                        body=body,
                        data=data,
                        high_priority=high_priority
                    )
                    
                    # Log result securely
                    logger.info(
                        f"Processed notification {notification_id}: "
                        f"Success: {result['success_devices']}, Failed: {result['failed_devices']}"
                    )
                elif action == "check_scheduled":
                    # Check Redis for scheduled notifications
                    if self.redis_handler:
                        scheduled_count = self.redis_handler.process_scheduled_notifications()
                        logger.info(f"Processed {scheduled_count} scheduled notifications")
                    else:
                        logger.warning("Redis handler not available, cannot process scheduled notifications")
                else:
                    logger.warning(f"Unknown action: {action}")
                
                # Acknowledge message
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                # Log error securely
                logger.error(f"Error processing message: {str(e)}")
                
                # Nack message and requeue if recoverable
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                
                # Add to dead letter queue if too many failures
                # This would typically be handled by RabbitMQ configuration
            finally:
                # Close database session
                db.close()
        except Exception as e:
            # Log error securely
            logger.error(f"Fatal error processing message: {str(e)}")
            
            # Nack message and don't requeue to avoid poison message
            if ch and method:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def consume(self) -> None:
        """Start consuming messages from the queue."""
        try:
            # Register consumer
            self.channel.basic_consume(
                queue="push_notifications",
                on_message_callback=self.process_message
            )
            
            logger.info("Starting to consume messages")
            self.running = True
            
            # Start consuming
            self.channel.start_consuming()
        except Exception as e:
            logger.error(f"Error in consume loop: {str(e)}")
            self.running = False
    
    def schedule_checker(self) -> None:
        """Publish a message to check scheduled notifications."""
        try:
            if self.rabbitmq_handler:
                self.rabbitmq_handler.publish_message(
                    queue_key="push_notifications",
                    message={"action": "check_scheduled"},
                    priority=0
                )
                logger.info("Scheduled check message published")
            else:
                logger.warning("RabbitMQ handler not available, cannot publish scheduled check")
        except Exception as e:
            logger.error(f"Error publishing scheduled check: {str(e)}")
    
    def run(self) -> None:
        """Run the worker with automatic reconnection."""
        while True:
            try:
                if not self.connect():
                    logger.warning("Could not connect to RabbitMQ, retrying...")
                    time.sleep(5)
                    continue
                
                # Start consuming
                self.consume()
                
                # If we reached here, consuming has stopped
                if not self.running:
                    break
            except AMQPConnectionError:
                logger.warning("RabbitMQ connection lost, reconnecting...")
                time.sleep(5)
            except ChannelClosedByBroker:
                logger.warning("RabbitMQ channel closed, reconnecting...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                time.sleep(5)
                
                # If we've tried too many times, exit
                if not self.running:
                    break
    
    def shutdown(self, signum, frame) -> None:
        """
        Handle shutdown signals.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
        if self.channel:
            try:
                self.channel.stop_consuming()
            except Exception as e:
                logger.error(f"Error stopping consumption: {str(e)}")
        
        if self.connection:
            try:
                self.connection.close()
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")
        
        logger.info("Notification worker shutdown complete")
        sys.exit(0)


def main():
    """Main entry point for the worker."""
    try:
        logger.info("Starting notification worker")
        worker = NotificationWorker()
        worker.run()
    except Exception as e:
        logger.error(f"Error in notification worker: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run worker
    main()
