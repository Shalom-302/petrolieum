"""
Group model for the advanced authentication plugin.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.core.db import Base
from .user import user_group

class Group(Base):
    """
    Group model for organizing users.
    """
    __tablename__ = "auth_group"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    is_system_group = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", secondary=user_group, back_populates="groups")
    
    def __repr__(self):
        return f"<Group {self.name} ({self.id})>"
