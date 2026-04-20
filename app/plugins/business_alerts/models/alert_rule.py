"""
Alert rule model definition.

This module contains the database model for alert rules which define
the conditions and parameters for generating business alerts.
"""

import logging
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer
from sqlalchemy.orm import relationship

from app.core.db import Base
from app.core.utils import generate_uuid

logger = logging.getLogger(__name__)


class AlertRuleDB(Base):
    """
    Database model for alert rules.
    
    Alert rules define when and how business alerts should be generated,
    including the conditions to check, message templates, and severity levels.
    """
    __tablename__ = "alert_rules"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    entity_type = Column(String(50), nullable=False)  # Type of entity this rule applies to
    alert_type = Column(String(50), nullable=False)   # Type of alert this rule generates
    condition = Column(JSON, nullable=False)          # JSON structure containing the detection logic
    severity = Column(String(20), nullable=False)     # 'critical', 'warning', 'info'
    message_template = Column(String(500), nullable=False)  # Template for alert messages
    is_active = Column(Boolean, default=True)         # Whether this rule is currently active
    check_frequency = Column(String(50), default="daily")  # 'hourly', 'daily', 'weekly'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(36), nullable=True)    # User ID of creator
    priority = Column(Integer, default=100)           # Priority for execution order
    
    # Optional: Define relationships with other tables
    # alerts = relationship("BusinessAlertDB", back_populates="rule")
    
    def __repr__(self) -> str:
        """String representation of the alert rule."""
        return f"<AlertRule(id={self.id}, name={self.name}, type={self.alert_type})>"
    
    @property
    def condition_type(self) -> str:
        """Get the type of condition from the condition JSON."""
        if not self.condition or not isinstance(self.condition, dict):
            return "unknown"
        return self.condition.get("type", "custom")
    
    @property
    def is_sql_condition(self) -> bool:
        """Check if this rule uses a SQL condition."""
        return self.condition_type == "sql"
    
    @property
    def is_python_condition(self) -> bool:
        """Check if this rule uses a Python code condition."""
        return self.condition_type == "python"
