# app/plugins/advanced_audit/models.py

from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from app.core.db import Base  # Use the central Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)  # Optional, if you want to record which user performed the action
    action = Column(String(100), nullable=False)  # e.g., "user.created", "order.updated"
    resource = Column(String(100), nullable=False)  # e.g., "user", "order"
    details = Column(Text, nullable=True)  # Extra information about the event
    created_at = Column(DateTime, default=datetime.utcnow)
