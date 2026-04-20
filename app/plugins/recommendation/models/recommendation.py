"""
Recommendation Results Database Models

This module defines database models for storing generated recommendations 
to optimize performance and enable analysis of recommendation quality.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text, Index, ForeignKey
from sqlalchemy.sql import func
from app.core.db import Base


class RecommendationDB(Base):
    """
    Stores generated recommendations for users and tracks their effectiveness.
    Used for caching recommendations and evaluating algorithm performance.
    """
    __tablename__ = "recommendation_results"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    
    # The recommended item
    item_id = Column(Integer, index=True, nullable=False)
    
    # Recommendation metadata
    algorithm = Column(String(50), index=True, nullable=False)  # 'collaborative', 'content-based', etc.
    score = Column(Float, nullable=False)  # Recommendation score/confidence
    rank = Column(Integer, nullable=False)  # Position in recommendation list
    
    # Context of the recommendation
    context = Column(String(255), nullable=True)  # e.g., 'homepage', 'article-page', 'email'
    
    # Effectiveness tracking
    was_clicked = Column(Integer, default=0, nullable=False)  # 0=no, 1=yes
    click_time = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=True)  # When this recommendation becomes stale
    
    # Create indices for efficient querying
    __table_args__ = (
        Index('idx_user_context', 'user_id', 'context'),
        Index('idx_algorithm_score', 'algorithm', 'score'),
        Index('idx_created_expires', 'created_at', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<Recommendation(user_id={self.user_id}, item_id={self.item_id}, algorithm={self.algorithm})>"


class UserPreferenceDB(Base):
    """
    Stores user preferences and profile information for personalized recommendations.
    """
    __tablename__ = "recommendation_user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, unique=True, nullable=False)
    
    # Explicit preferences
    preferred_categories = Column(String(1024), nullable=True)  # JSON array of category IDs
    preferred_tags = Column(String(1024), nullable=True)  # JSON array of tags
    disliked_items = Column(String(1024), nullable=True)  # JSON array of item IDs
    
    # Learned preferences (from algorithms)
    interest_vector = Column(Text, nullable=True)  # Serialized vector of interests
    latent_factors = Column(Text, nullable=True)  # From matrix factorization
    
    # Personalization settings
    diversity_preference = Column(Float, default=0.5, nullable=False)  # 0-1, how diverse recommendations should be
    novelty_preference = Column(Float, default=0.5, nullable=False)  # 0-1, preference for new vs. familiar items
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<UserPreference(user_id={self.user_id})>"
