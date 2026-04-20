"""
Database models for secure timestamps.

This module contains SQLAlchemy models for storing cryptographic timestamps
that certify the existence of data at a specific point in time.
"""

import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.core.db import Base


class TimestampDB(Base):
    """
    Database model for secure timestamps.
    
    This model stores information about cryptographically secure timestamps,
    including references to the timestamped data, timestamp tokens,
    and verification metadata.
    """
    __tablename__ = "digital_timestamps"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    data_hash = Column(String, nullable=False, index=True, comment="Hash of the timestamped data")
    data_source = Column(String, nullable=True, comment="Source of the timestamped data (e.g., file name)")
    
    # Timestamp information
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, comment="Timestamp value")
    timestamp_token = Column(Text, nullable=False, comment="Cryptographic timestamp token in JSON format")
    
    # User and metadata
    user_id = Column(String, nullable=False, index=True, comment="User who created the timestamp")
    description = Column(Text, nullable=True, comment="Optional description of the timestamp")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, comment="When the timestamp record was created")
    
    # Status information
    is_valid = Column(Boolean, default=True, nullable=False, comment="Whether the timestamp is valid")
    verification_count = Column(Integer, default=0, nullable=False, comment="Number of times this timestamp has been verified")
    last_verified_at = Column(DateTime, nullable=True, comment="When the timestamp was last verified")
    
    # Certificate information
    certificate_id = Column(String, nullable=True, comment="Reference to the certificate used for timestamping")
    
    # For long-term verification
    long_term_verification_data = Column(Text, nullable=True, comment="Additional data for long-term verification in JSON format")
    
    def __repr__(self):
        return f"<TimestampDB(id={self.id}, timestamp={self.timestamp}, data_hash={self.data_hash})>"
