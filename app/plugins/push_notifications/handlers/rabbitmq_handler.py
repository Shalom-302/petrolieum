"""
RabbitMQ Handler for Push Notifications

This module provides RabbitMQ integration for high-performance asynchronous
processing of push notifications, with standardized security practices.
"""

import json
import logging
import time
from typing import Dict, Any, Callable, List, Optional
import asyncio
import threading
import uuid

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker

logger = logging.getLogger(__name__)

class RabbitMQHandler:
    """
    Handler for RabbitMQ operations to enable high-throughput asynchronous
    processing of push notifications.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the RabbitMQ handler.
        
        Args:
            config: RabbitMQ configuration dictionary
        """
        self.config = config
        self.connection = None
        self.channel = None
        self.is_connected = False
        self.consumer_threads = {}
        self.retry_delay = 5  # seconds
        self.max_retries = 5
        
        # Queues configuration
        self.queues = {
            "notifications": f"{config.get('queue_prefix', '')}notifications",
            "scheduled": f"{config.get('queue_prefix', '')}scheduled",
            "delivery_status": f"{config.get('queue_prefix', '')}delivery_status",
            "analytics": f"{config.get('queue_prefix', '')}analytics"
        }
        
        # Exchange name
        self.exchange = config.get("exchange", "push_notifications")
        
    
    def _connect(self) -> bool:
        """
        Establish connection to RabbitMQ server.
        
        Returns:
            bool: Connection success status
        """
        try:
            # Get connection parameters from config
            credentials = pika.PlainCredentials(
                self.config.get("username", "guest"),
                self.config.get("password", "guest")
            )
            
            parameters = pika.ConnectionParameters(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 5672),
                virtual_host=self.config.get("virtual_host", "/"),
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            # Establish connection
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare exchange
            self.channel.exchange_declare(
                exchange=self.exchange,
                exchange_type='topic',
                durable=True
            )
            
            # Declare queues
            for queue_name in self.queues.values():
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=True
                )
                # Bind queue to exchange
                self.channel.queue_bind(
                    exchange=self.exchange,
                    queue=queue_name,
                    routing_key=queue_name
                )
            
            self.is_connected = True
            logger.info("Connected to RabbitMQ server")
            return True
            
        except Exception as e:
            self.is_connected = False
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            return False
    
    def _ensure_connection(self) -> bool:
        """
        Ensure that the connection to RabbitMQ is active.
        
        Returns:
            bool: Connection status
        """
        if not self.is_connected or not self.connection or self.connection.is_closed:
            return self._connect()
        return True
    
    def publish_message(self, queue_key: str, message: Dict[str, Any], 
                       priority: int = 0, expiration: int = None) -> bool:
        """
        Publish a message to a specified queue.
        
        Args:
            queue_key: Key of the queue to publish to (must be in self.queues)
            message: Message dictionary to publish
            priority: Message priority (0-9)
            expiration: Message expiration time in milliseconds
            
        Returns:
            bool: Success status
        """
        if queue_key not in self.queues:
            logger.error(f"Invalid queue key: {queue_key}")
            return False
            
        queue = self.queues[queue_key]
        retries = 0
        
        while retries < self.max_retries:
            try:
                if not self._ensure_connection():
                    raise ConnectionError("Could not establish RabbitMQ connection")
                
                # Add message metadata
                if "id" not in message:
                    message["id"] = str(uuid.uuid4())
                if "timestamp" not in message:
                    message["timestamp"] = int(time.time())
                
                # Prepare message properties
                properties = pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json',
                    priority=priority
                )
                
                if expiration:
                    properties.expiration = str(expiration)
                
                # Convert message to JSON and publish
                message_body = json.dumps(message)
                self.channel.basic_publish(
                    exchange=self.exchange,
                    routing_key=queue,
                    body=message_body,
                    properties=properties
                )
                
                logger.debug(f"Published message to queue {queue}: {message['id']}")
                return True
                
            except (AMQPConnectionError, ConnectionError) as e:
                retries += 1
                logger.warning(f"Connection error publishing to {queue}, attempt {retries}: {str(e)}")
                time.sleep(self.retry_delay)
                self._connect()
                
            except Exception as e:
                logger.error(f"Error publishing message to {queue}: {str(e)}")
                return False
        
        logger.error(f"Failed to publish message after {self.max_retries} attempts")
        return False
    
    def start_consumer(self, queue_key: str, callback: Callable[[Dict[str, Any]], None],
                     prefetch_count: int = 10) -> bool:
        """
        Start a consumer for a specified queue in a separate thread.
        
        Args:
            queue_key: Key of the queue to consume from (must be in self.queues)
            callback: Function to call when a message is received
            prefetch_count: Number of messages to prefetch
            
        Returns:
            bool: Success status
        """
        if queue_key not in self.queues:
            logger.error(f"Invalid queue key: {queue_key}")
            return False
        
        if queue_key in self.consumer_threads and self.consumer_threads[queue_key].is_alive():
            logger.warning(f"Consumer for {queue_key} is already running")
            return True
        
        # Create consumer thread
        consumer_thread = threading.Thread(
            target=self._consume_messages,
            args=(queue_key, callback, prefetch_count),
            daemon=True
        )
        
        # Start thread
        consumer_thread.start()
        self.consumer_threads[queue_key] = consumer_thread
        
        logger.info(f"Started consumer for {queue_key}")
        return True
    
    def _consume_messages(self, queue_key: str, callback: Callable[[Dict[str, Any]], None], 
                        prefetch_count: int = 10) -> None:
        """
        Consume messages from a queue with automatic reconnection.
        
        Args:
            queue_key: Key of the queue to consume from
            callback: Function to call when a message is received
            prefetch_count: Number of messages to prefetch
        """
        queue = self.queues[queue_key]
        
        while True:
            try:
                # Create a new connection for the consumer
                credentials = pika.PlainCredentials(
                    self.config.get("username", "guest"),
                    self.config.get("password", "guest")
                )
                
                parameters = pika.ConnectionParameters(
                    host=self.config.get("host", "localhost"),
                    port=self.config.get("port", 5672),
                    virtual_host=self.config.get("virtual_host", "/"),
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
                
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                
                # Set QoS
                channel.basic_qos(prefetch_count=prefetch_count)
                
                def message_callback(ch, method, properties, body):
                    try:
                        # Parse message
                        message = json.loads(body)
                        
                        # Process the message with user callback
                        callback(message)
                        
                        # Acknowledge the message
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in message: {body}")
                        # Negative acknowledgement with requeue=False
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                        
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        # Negative acknowledgement with requeue=True
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                
                # Start consuming
                channel.basic_consume(
                    queue=queue,
                    on_message_callback=message_callback
                )
                
                logger.info(f"Consumer ready for queue {queue}")
                channel.start_consuming()
                
            except (AMQPConnectionError, ChannelClosedByBroker, ConnectionError) as e:
                logger.warning(f"Connection error in consumer for {queue}: {str(e)}")
                time.sleep(self.retry_delay)
                
            except Exception as e:
                logger.error(f"Error in consumer for {queue}: {str(e)}")
                time.sleep(self.retry_delay)
    
    def schedule_message(self, queue_key: str, message: Dict[str, Any], 
                       delay_seconds: int) -> bool:
        """
        Schedule a message to be delivered after a specified delay.
        
        Args:
            queue_key: Key of the queue to publish to (must be in self.queues)
            message: Message dictionary to publish
            delay_seconds: Delay in seconds before the message should be delivered
            
        Returns:
            bool: Success status
        """
        # Add scheduling information to the message
        message["scheduled_time"] = int(time.time() + delay_seconds)
        
        # Publish to the scheduled queue
        return self.publish_message("scheduled", {
            "target_queue": queue_key,
            "message": message,
            "scheduled_time": message["scheduled_time"]
        })
    
    def batch_publish(self, queue_key: str, messages: List[Dict[str, Any]],
                    batch_size: int = 100) -> Dict[str, Any]:
        """
        Publish multiple messages in batches for better performance.
        
        Args:
            queue_key: Key of the queue to publish to (must be in self.queues)
            messages: List of message dictionaries to publish
            batch_size: Size of each batch
            
        Returns:
            Dict: Results with counts of successful and failed messages
        """
        if queue_key not in self.queues:
            logger.error(f"Invalid queue key: {queue_key}")
            return {"success": 0, "failure": len(messages)}
        
        results = {"success": 0, "failure": 0, "failed_ids": []}
        
        # Process messages in batches
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i+batch_size]
            
            try:
                if not self._ensure_connection():
                    raise ConnectionError("Could not establish RabbitMQ connection")
                
                # Prepare all messages
                for message in batch:
                    if "id" not in message:
                        message["id"] = str(uuid.uuid4())
                    if "timestamp" not in message:
                        message["timestamp"] = int(time.time())
                
                # Use the transaction to publish all messages
                try:
                    self.channel.tx_select()
                    
                    for message in batch:
                        # Prepare message properties
                        properties = pika.BasicProperties(
                            delivery_mode=2,  # Make message persistent
                            content_type='application/json'
                        )
                        
                        # Convert message to JSON and publish
                        message_body = json.dumps(message)
                        self.channel.basic_publish(
                            exchange=self.exchange,
                            routing_key=self.queues[queue_key],
                            body=message_body,
                            properties=properties
                        )
                    
                    # Commit the transaction
                    self.channel.tx_commit()
                    results["success"] += len(batch)
                    
                except Exception as e:
                    # Rollback the transaction
                    try:
                        self.channel.tx_rollback()
                    except Exception:
                        pass
                    
                    logger.error(f"Transaction error in batch publish: {str(e)}")
                    results["failure"] += len(batch)
                    results["failed_ids"].extend([msg.get("id", "unknown") for msg in batch])
                    
            except Exception as e:
                logger.error(f"Error in batch publish: {str(e)}")
                results["failure"] += len(batch)
                results["failed_ids"].extend([msg.get("id", "unknown") for msg in batch])
        
        return results
    
    def close(self) -> None:
        """Close the RabbitMQ connection."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            self.is_connected = False
            logger.info("RabbitMQ connection closed")
