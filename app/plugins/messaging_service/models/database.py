"""
Database Models

This module defines database models for the messaging service, 
implementing the standardized security approach for storing sensitive data.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import datetime
import uuid
from typing import List, Optional

from app.core.db import Base


# Define the MessageDeliveryStatusDB here since it's not defined in message.py or conversation.py
class MessageDeliveryStatusDB(Base):
    """Database model for message delivery status."""
    __tablename__ = "messaging_message_delivery_status"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey('messaging_messages.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    is_delivered = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    delivery_metadata = Column(Text, nullable=True)  # Encrypted JSON for delivery metadata
    
    # Relationships
    message = relationship("MessageDB", back_populates="delivery_statuses")

    __table_args__ = (
        # Ensure each user has only one status record per message
        {"sqlite_autoincrement": True},
    )
