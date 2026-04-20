"""
Models for the AI/ML integration plugin.

This module defines the database models for the AI integration plugin,
including AI service providers, credentials, models, and usage tracking.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, TypeVar, Generic, Union

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, UniqueConstraint, Enum, JSON, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from enum import Enum as PyEnum

from app.core.db import Base


class AIProviderType(str, PyEnum):
    """Enum for supported AI service providers."""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    GOOGLE_VERTEX = "google_vertex"
    CUSTOM = "custom"


class AIModelType(str, PyEnum):
    """Enum for AI model categories."""
    TEXT = "text"
    EMBEDDING = "embedding"
    IMAGE = "image"
    AUDIO = "audio"
    MULTIMODAL = "multimodal"


class AIProvider(Base):
    """Model for AI service providers."""
    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    provider_type = Column(Enum(AIProviderType), nullable=False, index=True)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Provider-specific configuration
    base_url = Column(String(255), nullable=True)
    config = Column(JSON, nullable=True)
    
    # Credentials (should be encrypted in production)
    api_key = Column(String(255), nullable=True)
    api_secret = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    models = relationship("AIModel", back_populates="provider", cascade="all, delete-orphan")
    usage_records = relationship("AIUsageRecord", back_populates="provider", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('name', name='uq_ai_provider_name'),
    )


class AIModel(Base):
    """Model for AI models from different providers."""
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("ai_providers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    model_type = Column(Enum(AIModelType), nullable=False, index=True)
    model_id = Column(String(255), nullable=False)  # Provider's model ID (e.g., "gpt-4")
    version = Column(String(50), nullable=True)
    
    # Model capabilities and configuration
    capabilities = Column(JSON, nullable=True)
    default_params = Column(JSON, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    
    # Usage information
    is_active = Column(Boolean, default=True)
    cost_per_1k_tokens = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    provider = relationship("AIProvider", back_populates="models")
    usage_records = relationship("AIUsageRecord", back_populates="model", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('provider_id', 'model_id', name='uq_provider_model_id'),
    )


class AIUsageRecord(Base):
    """Model for tracking AI service usage."""
    __tablename__ = "ai_usage_records"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("ai_providers.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    
    # Usage details
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Request details
    request_type = Column(String(50), nullable=False)  # e.g., "completion", "embedding"
    request_id = Column(String(255), nullable=True)  # Provider's request ID
    prompt_summary = Column(String(1000), nullable=True)
    
    # Cost tracking
    cost = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    provider = relationship("AIProvider", back_populates="usage_records")
    model = relationship("AIModel", back_populates="usage_records")


class TextAnalysisResult(Base):
    """Model for storing text analysis results."""
    __tablename__ = "ai_text_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)  # e.g., "document", "comment"
    entity_id = Column(Integer, nullable=False)
    
    # Analysis results
    language = Column(String(10), nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_magnitude = Column(Float, nullable=True)  # 0.0 to +inf
    sentiment_label = Column(String(20), nullable=True)  # e.g., "positive", "negative", "neutral"
    
    # Content classification
    categories = Column(JSON, nullable=True)  # List of categories with confidence scores
    entities = Column(JSON, nullable=True)  # Named entities extracted
    keywords = Column(JSON, nullable=True)  # Key phrases/terms
    summary = Column(Text, nullable=True)  # AI-generated summary
    
    # Processing metadata
    model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow)
    processing_time_ms = Column(Integer, nullable=True)
    
    # Relationships
    model = relationship("AIModel")

    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', name='uq_entity_analysis'),
    )


class ContentRecommendation(Base):
    """Model for storing AI-generated content recommendations."""
    __tablename__ = "ai_content_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    
    # Recommendation details
    content_type = Column(String(50), nullable=False)  # e.g., "document", "article"
    content_id = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)  # Relevance score
    reason = Column(String(500), nullable=True)  # Why this was recommended
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_dismissed = Column(Boolean, default=False)
    
    # Tracking
    model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=False)
    
    # Relationships
    model = relationship("AIModel")

    __table_args__ = (
        UniqueConstraint('user_id', 'content_type', 'content_id', name='uq_user_content_recommendation'),
    )


class AIEmbedding(Base):
    """Model for storing pre-computed vector embeddings."""
    __tablename__ = "ai_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)  # e.g., "document", "user"
    entity_id = Column(Integer, nullable=False)
    
    # Embedding data
    embedding_vector = Column(Text, nullable=False)  # Stored as base64-encoded string
    dimensions = Column(Integer, nullable=False)
    
    # Metadata
    model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    model = relationship("AIModel")

    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', 'model_id', name='uq_entity_model_embedding'),
    )
