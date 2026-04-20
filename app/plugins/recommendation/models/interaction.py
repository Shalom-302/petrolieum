"""
User-Item Interaction Database Models

This module defines database models for storing user interactions with items,
which are used for training collaborative filtering recommendation algorithms.
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.core.db import Base
from datetime import datetime


class InteractionDB(Base):
    """
    Stores user interactions with items, including ratings, views, and other engagement metrics.
    Used as the primary data source for collaborative filtering algorithms.
    """
    __tablename__ = "recommendation_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    item_id = Column(Integer, index=True, nullable=False)
    interaction_type = Column(String(50), nullable=False)  # e.g., 'view', 'rating', 'purchase'
    value = Column(Float, nullable=False)  # For ratings: 1-5, for views: 1.0, etc.
    context = Column(String(255), nullable=True)  # Optional contextual info (device, location)
    interaction_metadata = Column(String(1024), nullable=True)  # JSON string for additional metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Create indices for efficient querying
    __table_args__ = (
        Index('idx_user_item', 'user_id', 'item_id'),
        Index('idx_interaction_type', 'interaction_type'),
    )
    
    def __repr__(self):
        return f"<Interaction(user_id={self.user_id}, item_id={self.item_id}, type={self.interaction_type})>"
