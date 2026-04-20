"""
SQLAlchemy models for the API versioning plugin.

This module defines the database models for tracking API versions, 
endpoints, and changes for changelog purposes.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class APIVersion(Base):
    """
    Model for tracking API versions.
    
    This model stores information about different API versions, including
    version number, release date, and description.
    """
    __tablename__ = "api_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    release_date = Column(DateTime, default=func.now())
    is_current = Column(Boolean, default=False)  # Only one version should be current
    
    # Relationships
    endpoints = relationship("APIEndpoint", back_populates="version", cascade="all, delete-orphan")
    changes_to = relationship("APIChange", foreign_keys="APIChange.new_version_id", back_populates="new_version")
    changes_from = relationship("APIChange", foreign_keys="APIChange.previous_version_id", back_populates="previous_version")


class APIEndpoint(Base):
    """
    Model for tracking API endpoints.
    
    This model stores information about API endpoints in a specific version,
    including path, method, and implementation details.
    """
    __tablename__ = "api_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, index=True)
    method = Column(String, index=True)
    version_id = Column(Integer, ForeignKey("api_versions.id"))
    description = Column(String, nullable=True)
    handler_module = Column(String, nullable=True)
    handler_function = Column(String, nullable=True)
    parameters = Column(JSON, nullable=True)
    response_model = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    version = relationship("APIVersion", back_populates="endpoints")


class APIChange(Base):
    """
    Model for tracking changes between API versions.
    
    This model stores information about what changed between API versions,
    making it easy to generate changelogs.
    """
    __tablename__ = "api_changes"

    id = Column(Integer, primary_key=True, index=True)
    previous_version_id = Column(Integer, ForeignKey("api_versions.id"))
    new_version_id = Column(Integer, ForeignKey("api_versions.id"))
    endpoint_path = Column(String, index=True)
    change_type = Column(String)  # 'added', 'modified', 'removed'
    description = Column(String)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    previous_version = relationship("APIVersion", foreign_keys=[previous_version_id], back_populates="changes_from")
    new_version = relationship("APIVersion", foreign_keys=[new_version_id], back_populates="changes_to")
