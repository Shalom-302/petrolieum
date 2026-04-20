# app/plugins/webhooks/model.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, text, JSON
from datetime import datetime
from app.core.db import Base  # import the shared Base from your main DB setup

class WebhookSubscription(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)         # descriptive name
    event = Column(String(100), nullable=False)        # e.g. "resource.created", "order.placed"
    url = Column(String(500), nullable=False)          # the endpoint to call
    secret = Column(String(200), nullable=True)        # optional signing secret
    is_enabled = Column(Boolean, default=True, nullable=False)

    # optional JSON for additional settings
    config = Column(JSON, server_default=text("'{}'")) 

    created_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
