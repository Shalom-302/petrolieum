"""
Interaction Schemas

This module defines Pydantic schemas for validating user-item interactions
in API requests and responses.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class InteractionBase(BaseModel):
    """Base schema for user-item interactions"""
    user_id: int = Field(..., description="ID of the user who interacted with the item")
    item_id: int = Field(..., description="ID of the item the user interacted with")
    interaction_type: str = Field(..., description="Type of interaction (e.g., 'view', 'rating', 'purchase')")
    value: float = Field(..., description="Value of the interaction (e.g., rating value, view duration)")
    context: Optional[str] = Field(None, description="Optional context information")
    
    @validator('interaction_type')
    def validate_interaction_type(cls, v):
        allowed_types = ['view', 'rating', 'purchase', 'like', 'share', 'bookmark', 'click']
        if v not in allowed_types:
            raise ValueError(f"Interaction type must be one of {allowed_types}")
        return v
    
    @validator('value')
    def validate_value(cls, v, values):
        if 'interaction_type' in values:
            if values['interaction_type'] == 'rating' and (v < 1.0 or v > 5.0):
                raise ValueError("Rating value must be between 1.0 and 5.0")
            if values['interaction_type'] in ['view', 'click'] and v != 1.0:
                raise ValueError(f"Value for {values['interaction_type']} must be 1.0")
        return v


class InteractionCreate(InteractionBase):
    """Schema for creating a new interaction"""
    interaction_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional encrypted metadata for the interaction")


class InteractionResponse(InteractionBase):
    """Schema for interaction responses"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BatchInteractionCreate(BaseModel):
    """Schema for creating multiple interactions at once"""
    interactions: List[InteractionCreate] = Field(..., min_items=1, max_items=100)


class UserItemInteractionStats(BaseModel):
    """Schema for aggregated interaction statistics between a user and an item"""
    user_id: int
    item_id: int
    total_interactions: int
    last_interaction: datetime
    average_rating: Optional[float] = None
    view_count: int
    purchase_count: int
    
    class Config:
        from_attributes = True
