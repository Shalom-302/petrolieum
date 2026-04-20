"""
Item Schemas

This module defines Pydantic schemas for item data in API requests and responses.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class ItemFeatureBase(BaseModel):
    """Base schema for item features"""
    item_id: int = Field(..., description="ID of the item")
    item_type: str = Field(..., description="Type of item (e.g., 'article', 'product', 'video')")
    title: Optional[str] = Field(None, description="Item title")
    description: Optional[str] = Field(None, description="Item description")
    categories: Optional[List[str]] = Field(None, description="List of categories the item belongs to")
    
    @validator('item_type')
    def validate_item_type(cls, v):
        allowed_types = ['article', 'product', 'video', 'music', 'image', 'document', 'event', 'course']
        if v not in allowed_types:
            raise ValueError(f"Item type must be one of {allowed_types}")
        return v


class ItemFeatureCreate(ItemFeatureBase):
    """Schema for creating a new item feature entry"""
    text_content: Optional[str] = Field(None, description="Full text content for feature extraction")
    numerical_features: Optional[Dict[str, float]] = Field(None, description="Dictionary of numerical features")
    categorical_features: Optional[Dict[str, str]] = Field(None, description="Dictionary of categorical features")
    tags: Optional[List[str]] = Field(None, description="List of tags associated with the item")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the item")


class ItemFeatureResponse(ItemFeatureBase):
    """Schema for item feature responses"""
    id: int
    popularity_score: float
    average_rating: float
    rating_count: int
    view_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ItemFeatureUpdate(BaseModel):
    """Schema for updating item features"""
    title: Optional[str] = None
    description: Optional[str] = None
    categories: Optional[List[str]] = None
    text_content: Optional[str] = None
    numerical_features: Optional[Dict[str, float]] = None
    categorical_features: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ItemSimilarityResponse(BaseModel):
    """Schema for item similarity responses"""
    item_id: int
    similar_item_id: int
    algorithm: str
    similarity_score: float
    similarity_context: Optional[str] = None
    
    class Config:
        from_attributes = True


class BatchItemFeatureCreate(BaseModel):
    """Schema for creating multiple item features at once"""
    items: List[ItemFeatureCreate] = Field(..., min_items=1, max_items=100)
