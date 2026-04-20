"""
Similarity Matrix Database Models

This module defines database models for storing precomputed similarity matrices
between users and items, which are used to accelerate recommendation generation.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, LargeBinary, Index, Text
from sqlalchemy.sql import func
from app.core.db import Base


class SimilarityMatrixDB(Base):
    """
    Stores precomputed similarity matrices for users or items.
    Used to accelerate item-based and user-based collaborative filtering.
    """
    __tablename__ = "recommendation_similarity_matrices"
    
    id = Column(Integer, primary_key=True, index=True)
    matrix_type = Column(String(50), index=True, nullable=False)  # 'user-user', 'item-item'
    algorithm = Column(String(50), index=True, nullable=False)  # 'cosine', 'pearson', etc.
    
    # Compressed and serialized similarity matrix
    # Could be stored as a compressed numpy array or sparse matrix
    matrix_data = Column(LargeBinary, nullable=False)
    
    # Matrix dimensions and metadata
    rows = Column(Integer, nullable=False)  # Number of users/items in the matrix
    columns = Column(Integer, nullable=False)  # Number of users/items in the matrix
    matrix_metadata = Column(String(1024), nullable=True)  # JSON with additional params
    
    # Performance metrics
    training_duration = Column(Float, nullable=True)  # seconds
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<SimilarityMatrix(type={self.matrix_type}, algorithm={self.algorithm})>"


class ItemSimilarityDB(Base):
    """
    Stores precomputed similarities between specific item pairs.
    Used for quick lookup of similar items without loading entire matrices.
    """
    __tablename__ = "recommendation_item_similarities"
    
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, index=True, nullable=False)
    similar_item_id = Column(Integer, index=True, nullable=False)
    algorithm = Column(String(50), index=True, nullable=False)  # 'cosine', 'content-based', etc.
    similarity_score = Column(Float, nullable=False)
    
    # Additional context or features that explain the similarity
    similarity_context = Column(String(512), nullable=True)  # e.g., 'same-category', 'similar-content' 
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Create indices for efficient querying
    __table_args__ = (
        Index('idx_item_similar', 'item_id', 'similar_item_id'),
        Index('idx_item_algorithm_score', 'item_id', 'algorithm', 'similarity_score'),
    )
    
    def __repr__(self):
        return f"<ItemSimilarity(item_id={self.item_id}, similar_item_id={self.similar_item_id}, score={self.similarity_score})>"
