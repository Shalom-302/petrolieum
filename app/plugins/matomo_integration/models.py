"""
Database models for the Matomo integration plugin.
"""
import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.db import Base

class MatomoSettings(Base):
    """
    Stores Matomo integration settings.
    """
    __tablename__ = "matomo_settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matomo_url = Column(String, nullable=False, comment="URL of the Matomo instance")
    site_id = Column(Integer, nullable=False, comment="Matomo site ID for this Kaapi instance")
    auth_token = Column(String, nullable=True, comment="Authentication token for Matomo API")
    enabled = Column(Boolean, default=True, comment="Whether Matomo tracking is enabled")
    track_admin_users = Column(Boolean, default=False, comment="Whether to track admin users")
    heartbeat_timer = Column(Integer, default=15, comment="Heartbeat timer in seconds for tracking activity")
    additional_settings = Column(JSON, nullable=True, comment="Additional Matomo settings as JSON")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="Last update timestamp")

class MatomoUserMapping(Base):
    """
    Maps Kaapi users to Matomo users.
    """
    __tablename__ = "matomo_user_mappings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kaapi_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, comment="User ID in Kaapi")
    matomo_user_id = Column(String, nullable=False, comment="User ID in Matomo")
    matomo_login = Column(String, nullable=True, comment="Login username in Matomo")
    access_level = Column(String, nullable=False, default="view", comment="Access level in Matomo")
    last_sync = Column(DateTime(timezone=True), nullable=True, comment="Last synchronization timestamp")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="Last update timestamp")
    
    # Relationship to Kaapi user
    user = relationship("User", foreign_keys=[kaapi_user_id])

class MatomoEmbedConfig(Base):
    """
    Stores configuration for embedded Matomo dashboards and reports.
    """
    __tablename__ = "matomo_embed_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, comment="User-friendly name for this embed")
    embed_type = Column(String, nullable=False, comment="Type of embed (dashboard, report)")
    embed_id = Column(String, nullable=True, comment="ID of the dashboard or report in Matomo")
    date_range = Column(String, default="last7", comment="Default date range for this embed")
    filters = Column(JSON, nullable=True, comment="Default filters as JSON")
    position = Column(Integer, default=0, comment="Order position in UI")
    visible = Column(Boolean, default=True, comment="Whether this embed is visible in UI")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="Last update timestamp")
