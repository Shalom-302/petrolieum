"""
Recommendation Schemas

This module defines Pydantic schemas for recommendation requests and responses.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AlgorithmType(str, Enum):
    """Supported recommendation algorithm types"""
    COLLABORATIVE_USER_BASED = "collaborative_user_based"
    COLLABORATIVE_ITEM_BASED = "collaborative_item_based"
    MATRIX_FACTORIZATION = "matrix_factorization"
    CONTENT_BASED = "content_based"
    HYBRID = "hybrid"
    POPULARITY = "popularity"
    TRENDING = "trending"
    RANDOM = "random"


class RecommendationRequest(BaseModel):
    """Base schema for recommendation requests"""
    user_id: int = Field(..., description="ID of the user to generate recommendations for")
    count: int = Field(10, ge=1, le=100, description="Number of recommendations to generate")
    algorithm: AlgorithmType = Field(AlgorithmType.HYBRID, description="Recommendation algorithm to use")
    context: Optional[str] = Field(None, description="Context for the recommendation (e.g., 'homepage', 'article')")
    exclude_items: Optional[List[int]] = Field(None, description="Item IDs to exclude from recommendations")
    diversity_level: Optional[float] = Field(0.5, ge=0.0, le=1.0, description="Level of diversity in recommendations (0-1)")
    category_filters: Optional[List[str]] = Field(None, description="Categories to filter recommendations by")


class SimilarItemsRequest(BaseModel):
    """Request for similar items recommendations"""
    item_id: int = Field(..., description="ID of the item to find similar items for")
    count: int = Field(10, ge=1, le=100, description="Number of similar items to return")
    algorithm: Optional[str] = Field("hybrid", description="Algorithm to use for similarity calculation")
    min_similarity: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score (0-1)")


class RecommendedItem(BaseModel):
    """Schema for a single recommended item with metadata"""
    item_id: int
    score: float
    rank: int
    algorithm: str
    title: Optional[str] = None
    description: Optional[str] = None
    categories: Optional[List[str]] = None
    image_url: Optional[str] = None
    reason: Optional[str] = None  # Explanation for the recommendation


class RecommendationResponse(BaseModel):
    """Response schema for recommendation requests"""
    user_id: int
    items: List[RecommendedItem]
    context: Optional[str] = None
    total_items: int
    algorithm: str
    generation_time: float  # Time taken to generate recommendations in milliseconds
    recommendation_id: Optional[str] = None  # Unique ID for this set of recommendations
    
    class Config:
        from_attributes = True


class UserPreferenceUpdate(BaseModel):
    """Schema for updating user preferences"""
    preferred_categories: Optional[List[str]] = None
    preferred_tags: Optional[List[str]] = None
    disliked_items: Optional[List[int]] = None
    diversity_preference: Optional[float] = Field(None, ge=0.0, le=1.0)
    novelty_preference: Optional[float] = Field(None, ge=0.0, le=1.0)


class RecommendationFeedback(BaseModel):
    """Schema for user feedback on recommendations"""
    recommendation_id: str = Field(..., description="ID of the recommendation set")
    item_id: int = Field(..., description="ID of the item receiving feedback")
    user_id: int = Field(..., description="ID of the user providing feedback")
    feedback_type: str = Field(..., description="Type of feedback (e.g., 'click', 'dismiss', 'like')")
    timestamp: datetime = Field(default_factory=datetime.now)
    context: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    
    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        allowed_types = ['click', 'view', 'dismiss', 'like', 'dislike', 'purchase', 'share']
        if v not in allowed_types:
            raise ValueError(f"Feedback type must be one of {allowed_types}")
        return v
