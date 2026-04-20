# backend/app/models/user.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.db import Base
# from uuid import UUID
from datetime import datetime
from sqlalchemy.types import Boolean

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    refresh_count = Column(Integer, default=0)  # Counter for rotations
    user_id = Column(String, nullable=False)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(255))
    expires_at = Column(DateTime, nullable=False)
    mfa_authenticated = Column(Boolean, default=False)
    revoked = Column(Boolean, default=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
