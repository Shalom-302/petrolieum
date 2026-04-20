"""
Permission model for the advanced authentication plugin.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.core.db import Base
from .role import role_permission

class Permission(Base):
    """
    Permission model for fine-grained access control.
    """
    __tablename__ = "auth_permission"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    code = Column(String(100), unique=True, nullable=False)
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)  # create, read, update, delete, etc.
    is_system_permission = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    roles = relationship("Role", secondary=role_permission, back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission {self.name} ({self.code})>"
