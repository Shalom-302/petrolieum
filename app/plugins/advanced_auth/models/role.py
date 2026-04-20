"""
Role model for the advanced authentication plugin.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Table, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.core.db import Base

# Association table for role-permissions
role_permission = Table(
    "auth_role_permission",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("auth_role.id"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("auth_permission.id"), primary_key=True)
)

class Role(Base):
    """
    Role model for granular permission management.
    """
    __tablename__ = "auth_role"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    is_system_role = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", secondary=role_permission, back_populates="roles")
    
    def __repr__(self):
        return f"<Role {self.name} ({self.id})>"
