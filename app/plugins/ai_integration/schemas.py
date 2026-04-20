"""
Schemas for the AI/ML integration plugin.

This module defines the Pydantic schemas for validating requests and responses
for the AI integration plugin's API endpoints.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator, root_validator

from app.plugins.ai_integration.models import AIProviderType, AIModelType


# ----------------------- Base Schemas -----------------------

class BaseResponse(BaseModel):
    """Base response model with standard metadata."""
    success: bool = True
    message: Optional[str] = None


# ----------------------- AI Provider Schemas -----------------------

class AIProviderBase(BaseModel):
    """Base schema for AI provider data."""
    name: str
    provider_type: AIProviderType
    is_default: Optional[bool] = False
    is_active: Optional[bool] = True
    base_url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class AIProviderCreate(AIProviderBase):
    """Schema for creating a new AI provider."""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "OpenAI GPT",
                "provider_type": "openai",
                "is_default": True,
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-your-api-key",
                "config": {"organization": "org-id"}
            }
        }


class AIProviderUpdate(BaseModel):
    """Schema for updating an AI provider."""
    name: Optional[str] = None
    provider_type: Optional[AIProviderType] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class AIProviderResponse(AIProviderBase):
    """Schema for AI provider response."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AIProviderListResponse(BaseResponse):
    """Schema for listing AI providers."""
    items: List[AIProviderResponse]
    total: int


# ----------------------- AI Model Schemas -----------------------

class AIModelBase(BaseModel):
    """Base schema for AI model data."""
    provider_id: int
    name: str
    model_type: AIModelType
    model_id: str
    version: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    default_params: Optional[Dict[str, Any]] = None
    max_tokens: Optional[int] = None
    is_active: Optional[bool] = True
    cost_per_1k_tokens: Optional[float] = None


class AIModelCreate(AIModelBase):
    """Schema for creating a new AI model."""
    class Config:
        json_schema_extra = {
            "example": {
                "provider_id": 1,
                "name": "GPT-4",
                "model_type": "text",
                "model_id": "gpt-4",
                "version": "0613",
                "capabilities": {
                    "functions": True,
                    "vision": False
                },
                "default_params": {
                    "temperature": 0.7,
                    "top_p": 1
                },
                "max_tokens": 8192,
                "cost_per_1k_tokens": 0.06
            }
        }


class AIModelUpdate(BaseModel):
    """Schema for updating an AI model."""
    name: Optional[str] = None
    model_type: Optional[AIModelType] = None
    model_id: Optional[str] = None
    version: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    default_params: Optional[Dict[str, Any]] = None
    max_tokens: Optional[int] = None
    is_active: Optional[bool] = None
    cost_per_1k_tokens: Optional[float] = None


class AIModelResponse(AIModelBase):
    """Schema for AI model response."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AIModelListResponse(BaseResponse):
    """Schema for listing AI models."""
    items: List[AIModelResponse]
    total: int


# ----------------------- Text Analysis Schemas -----------------------

class TextAnalysisRequest(BaseModel):
    """Schema for requesting text analysis."""
    text: str = Field(..., min_length=1, max_length=100000)
    model_id: Optional[int] = None
    provider_id: Optional[int] = None
    analysis_types: List[str] = Field(
        default=["language", "sentiment", "entities", "categories"],
        description="Types of analysis to perform"
    )
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "text": "I really enjoyed the product. It's very intuitive and solved my problem quickly!",
                "analysis_types": ["sentiment", "categories"],
                "entity_type": "review",
                "entity_id": 123
            }
        }


class TextAnalysisResponse(BaseResponse):
    """Schema for text analysis response."""
    analysis_id: Optional[int] = None
    language: Optional[str] = None
    sentiment: Optional[Dict[str, Any]] = None
    categories: Optional[List[Dict[str, Any]]] = None
    entities: Optional[List[Dict[str, Any]]] = None
    keywords: Optional[List[Dict[str, Any]]] = None
    summary: Optional[str] = None
    processing_time_ms: Optional[int] = None


# ----------------------- Content Generation Schemas -----------------------

class ContentGenerationRequest(BaseModel):
    """Schema for requesting AI-generated content."""
    prompt: str = Field(..., min_length=1, max_length=10000)
    model_id: Optional[int] = None
    provider_id: Optional[int] = None
    max_tokens: Optional[int] = 1000
    temperature: Optional[float] = 0.7
    params: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Write a product description for a smart home security camera.",
                "max_tokens": 500,
                "temperature": 0.8
            }
        }


class ContentGenerationResponse(BaseResponse):
    """Schema for content generation response."""
    generated_text: str
    model_used: str
    tokens_used: Optional[int] = None
    processing_time_ms: Optional[int] = None


# ----------------------- Recommendation Schemas -----------------------

class RecommendationRequest(BaseModel):
    """Schema for content recommendations."""
    user_id: int
    content_type: str = Field(..., description="Type of content to recommend")
    limit: Optional[int] = 10
    filters: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "content_type": "document",
                "limit": 5,
                "filters": {
                    "categories": ["technical", "business"],
                    "min_score": 0.7
                }
            }
        }


class RecommendationItem(BaseModel):
    """Schema for a single recommendation item."""
    content_id: int
    content_type: str
    score: float
    reason: Optional[str] = None


class RecommendationResponse(BaseResponse):
    """Schema for recommendation response."""
    items: List[RecommendationItem]
    total: int


# ----------------------- AI Usage Schemas -----------------------

class AIUsageRecord(BaseModel):
    """Schema for AI usage record."""
    id: int
    provider_id: int
    provider_name: str
    model_id: int
    model_name: str
    request_type: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AIUsageResponse(BaseResponse):
    """Schema for AI usage response."""
    items: List[AIUsageRecord]
    total: int
    total_cost: float


class AIUsageStatistics(BaseModel):
    """Schema for AI usage statistics."""
    total_requests: int
    total_tokens: int
    total_cost: float
    breakdown_by_model: Dict[str, Any]
    breakdown_by_request_type: Dict[str, Any]
    usage_over_time: List[Dict[str, Any]]
