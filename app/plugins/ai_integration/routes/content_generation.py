"""
Routes for AI content generation.

This module defines API endpoints for generating content using AI models,
including text generation, completions, and creative content.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
import time

from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_user
from app.plugins.ai_integration.models import (
    AIProvider, AIModel, AIModelType, AIUsageRecord
)
from app.plugins.ai_integration.schemas import (
    ContentGenerationRequest, ContentGenerationResponse, BaseResponse
)
from app.plugins.ai_integration.utils.ai_client import get_ai_client

router = APIRouter(
    prefix="/content"
)


@router.post("", response_model=ContentGenerationResponse)
async def generate_content(
    content_request: ContentGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Generate content using AI models.
    
    This endpoint can be used for various text generation tasks:
    - Creating product descriptions
    - Writing email responses
    - Generating creative content
    - Completing text based on a prompt
    """
    # Start timing
    start_time = time.time()
    
    # Determine which model to use
    model = None
    if content_request.model_id:
        model = db.query(AIModel).filter(
            AIModel.id == content_request.model_id,
            AIModel.model_type.in_([AIModelType.TEXT, AIModelType.MULTIMODAL]),
            AIModel.is_active == True
        ).first()
        
        if not model:
            raise HTTPException(
                status_code=404,
                detail=f"Active AI model with ID {content_request.model_id} not found"
            )
    elif content_request.provider_id:
        # Find a suitable model from the specified provider
        model = db.query(AIModel).filter(
            AIModel.provider_id == content_request.provider_id,
            AIModel.model_type.in_([AIModelType.TEXT, AIModelType.MULTIMODAL]),
            AIModel.is_active == True
        ).first()
        
        if not model:
            raise HTTPException(
                status_code=404,
                detail=f"No active text models found for provider ID {content_request.provider_id}"
            )
    else:
        # Find a default model for content generation
        provider = db.query(AIProvider).filter(
            AIProvider.is_default == True,
            AIProvider.is_active == True
        ).first()
        
        if not provider:
            raise HTTPException(
                status_code=404,
                detail="No default AI provider configured"
            )
        
        model = db.query(AIModel).filter(
            AIModel.provider_id == provider.id,
            AIModel.model_type.in_([AIModelType.TEXT, AIModelType.MULTIMODAL]),
            AIModel.is_active == True
        ).first()
        
        if not model:
            raise HTTPException(
                status_code=404,
                detail="No active text models found for default provider"
            )
    
    # Get AI client for the model's provider
    provider = db.query(AIProvider).filter(AIProvider.id == model.provider_id).first()
    ai_client = get_ai_client(provider)
    
    # Prepare parameters
    params = content_request.params or {}
    params.update({
        "max_tokens": content_request.max_tokens or model.max_tokens or 1000,
        "temperature": content_request.temperature or 0.7,
    })
    
    # Generate content
    try:
        result = ai_client.generate_text(content_request.prompt, model, params)
        
        # Record usage
        usage_record = AIUsageRecord(
            provider_id=provider.id,
            model_id=model.id,
            user_id=current_user.get("id"),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
            request_type="content_generation",
            prompt_summary=content_request.prompt[:100] + "..." if len(content_request.prompt) > 100 else content_request.prompt,
            cost=calculate_cost(model, result.get("total_tokens", 0))
        )
        
        db.add(usage_record)
        db.commit()
        
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "success": True,
            "generated_text": result.get("text", ""),
            "model_used": model.name,
            "tokens_used": result.get("total_tokens"),
            "processing_time_ms": processing_time_ms
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating content: {str(e)}"
        )


def calculate_cost(model: AIModel, tokens: int) -> Optional[float]:
    """Calculate the cost of a request based on token usage."""
    if model.cost_per_1k_tokens is None or tokens == 0:
        return None
    
    return (tokens / 1000) * model.cost_per_1k_tokens


@router.post("/completion", response_model=ContentGenerationResponse)
async def complete_text(
    completion_request: ContentGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Complete text based on a prompt.
    
    This is a specialized endpoint for text completion (auto-complete),
    which may use different models or parameters than general content generation.
    """
    # Use the general content generation function but potentially with different defaults
    return await generate_content(completion_request, db, current_user)


@router.post("/chat", response_model=ContentGenerationResponse)
async def chat_response(
    chat_request: ContentGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Generate a conversational response.
    
    This endpoint is specifically for chat-based interactions,
    where the prompt should be formatted as a conversation history.
    """
    # Use the general content generation function but potentially with different defaults
    # In a real implementation, you might format the prompt differently or use a chat-specific model
    return await generate_content(chat_request, db, current_user)
