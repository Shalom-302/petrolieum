"""
Business alert model definition.

This module contains the database model for business alerts which are used
to notify users about important business events or issues.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.core.db import Base
from app.core.utils import generate_uuid

logger = logging.getLogger(__name__)


class BusinessAlertDB(Base):
    """
    Database model for business alerts.
    
    Alerts are notifications about business-related issues that require attention,
    such as missing financial data, compliance issues, etc.
    """
    __tablename__ = "business_alerts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    entity_type = Column(String(50), nullable=False, index=True)  # 'company', 'user', etc.
    entity_id = Column(String(36), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False, index=True)  # 'missing_financial_data', etc.
    severity = Column(String(20), nullable=False)  # 'critical', 'warning', 'info'
    message = Column(String(500), nullable=False)
    details = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="active")  # 'active', 'acknowledged', 'resolved'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(36), nullable=True)  # User ID
    
    # Optional: Define relationships with other tables
    # rule_id = Column(String(36), ForeignKey("alert_rules.id"), nullable=True)
    # rule = relationship("AlertRuleDB", back_populates="alerts")
    
    def __repr__(self) -> str:
        """String representation of the business alert."""
        return f"<BusinessAlert(id={self.id}, type={self.alert_type}, status={self.status})>"
    
    @property
    def is_active(self) -> bool:
        """Check if the alert is still active."""
        return self.status == "active"
    
    @property
    def is_resolved(self) -> bool:
        """Check if the alert has been resolved."""
        return self.status == "resolved"
    
    @property
    def time_since_creation(self) -> int:
        """Calculate the time in hours since the alert was created."""
        if not self.created_at:
            return 0
        delta = datetime.utcnow() - self.created_at
        return int(delta.total_seconds() / 3600)  # Return hours
