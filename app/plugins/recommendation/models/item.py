"""
Item Features Database Models

This module defines database models for storing item features and metadata 
that are used for content-based filtering and hybrid recommendation algorithms.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text, Index
from sqlalchemy.sql import func
from app.core.db import Base


class ItemFeatureDB(Base):
    """
    Stores features and metadata about recommendation items (articles, products, etc.)
    Used for content-based filtering and enriching recommendations with metadata.
    """
    __tablename__ = "recommendation_item_features"
    
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, index=True, unique=True, nullable=False)
    item_type = Column(String(50), index=True, nullable=False)  # e.g., 'article', 'product', 'video'
    
    # Basic metadata
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    categories = Column(String(512), nullable=True)  # Comma-separated list of categories
    
    # Text features for NLP-based recommendations (TF-IDF, Word2Vec, etc.)
    text_features = Column(Text, nullable=True)  # JSON string or serialized vector
    
    # Numerical features
    feature_vector = Column(String(4096), nullable=True)  # JSON string of numerical features
    
    # Statistics and popularity metrics
    popularity_score = Column(Float, default=0.0, nullable=False)
    average_rating = Column(Float, default=0.0, nullable=False)
    rating_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_feature_update = Column(DateTime, nullable=True)
    
    # Create indices for efficient querying
    __table_args__ = (
        Index('idx_item_type_popularity', 'item_type', 'popularity_score'),
        Index('idx_item_type_rating', 'item_type', 'average_rating'),
    )
    
    def __repr__(self):
        return f"<ItemFeature(item_id={self.item_id}, type={self.item_type})>"
