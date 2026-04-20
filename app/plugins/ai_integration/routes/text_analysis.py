"""
Routes for text analysis capabilities.

This module defines API endpoints for analyzing text using AI models,
including sentiment analysis, entity recognition, and categorization.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
import time

from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_user
from app.plugins.ai_integration.models import (
    AIProvider, AIModel, TextAnalysisResult, AIModelType
)
from app.plugins.ai_integration.schemas import (
    TextAnalysisRequest, TextAnalysisResponse, BaseResponse
)
from app.plugins.ai_integration.utils.ai_client import get_ai_client

router = APIRouter(
    prefix="/text-analysis"
)


@router.post("", response_model=TextAnalysisResponse)
async def analyze_text(
    analysis_request: TextAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Analyze text using AI models for sentiment, entities, and categories.
    
    The analysis can include various types:
    - language: Detect the language of the text
    - sentiment: Determine the sentiment (positive, negative, neutral)
    - entities: Extract named entities (people, organizations, etc.)
    - categories: Classify the text into categories
    - keywords: Extract key phrases or terms
    - summary: Generate a concise summary of the text
    """
    # Start timing
    start_time = time.time()
    
    # Determine which model to use
    model = None
    if analysis_request.model_id:
        model = db.query(AIModel).filter(
            AIModel.id == analysis_request.model_id,
            AIModel.model_type.in_([AIModelType.TEXT, AIModelType.MULTIMODAL]),
            AIModel.is_active == True
        ).first()
        
        if not model:
            raise HTTPException(
                status_code=404,
                detail=f"Active AI model with ID {analysis_request.model_id} not found"
            )
    elif analysis_request.provider_id:
        # Find a suitable model from the specified provider
        model = db.query(AIModel).filter(
            AIModel.provider_id == analysis_request.provider_id,
            AIModel.model_type.in_([AIModelType.TEXT, AIModelType.MULTIMODAL]),
            AIModel.is_active == True
        ).first()
        
        if not model:
            raise HTTPException(
                status_code=404,
                detail=f"No active text models found for provider ID {analysis_request.provider_id}"
            )
    else:
        # Find a default model for text analysis
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
    
    # Initialize response object
    response = {
        "success": True,
        "analysis_id": None
    }
    
    # Process each requested analysis type
    try:
        # Language detection
        if "language" in analysis_request.analysis_types:
            language = ai_client.detect_language(analysis_request.text, model)
            response["language"] = language
        
        # Sentiment analysis
        if "sentiment" in analysis_request.analysis_types:
            sentiment = ai_client.analyze_sentiment(analysis_request.text, model)
            response["sentiment"] = sentiment
        
        # Entity recognition
        if "entities" in analysis_request.analysis_types:
            entities = ai_client.extract_entities(analysis_request.text, model)
            response["entities"] = entities
        
        # Categories classification
        if "categories" in analysis_request.analysis_types:
            categories = ai_client.classify_text(analysis_request.text, model)
            response["categories"] = categories
        
        # Keyword extraction
        if "keywords" in analysis_request.analysis_types:
            keywords = ai_client.extract_keywords(analysis_request.text, model)
            response["keywords"] = keywords
        
        # Text summarization
        if "summary" in analysis_request.analysis_types:
            summary = ai_client.summarize_text(analysis_request.text, model)
            response["summary"] = summary
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing text: {str(e)}"
        )
    
    # Record processing time
    processing_time_ms = int((time.time() - start_time) * 1000)
    response["processing_time_ms"] = processing_time_ms
    
    # Store results if entity reference is provided
    if analysis_request.entity_type and analysis_request.entity_id:
        try:
            # Check if analysis already exists for this entity
            existing_analysis = db.query(TextAnalysisResult).filter(
                TextAnalysisResult.entity_type == analysis_request.entity_type,
                TextAnalysisResult.entity_id == analysis_request.entity_id
            ).first()
            
            # Update or create analysis record
            if existing_analysis:
                # Update existing record
                existing_analysis.language = response.get("language")
                existing_analysis.sentiment_score = response.get("sentiment", {}).get("score")
                existing_analysis.sentiment_magnitude = response.get("sentiment", {}).get("magnitude")
                existing_analysis.sentiment_label = response.get("sentiment", {}).get("label")
                existing_analysis.categories = response.get("categories")
                existing_analysis.entities = response.get("entities")
                existing_analysis.keywords = response.get("keywords")
                existing_analysis.summary = response.get("summary")
                existing_analysis.model_id = model.id
                existing_analysis.processing_time_ms = processing_time_ms
                
                db.add(existing_analysis)
                db.commit()
                
                response["analysis_id"] = existing_analysis.id
            else:
                # Create new record
                new_analysis = TextAnalysisResult(
                    entity_type=analysis_request.entity_type,
                    entity_id=analysis_request.entity_id,
                    language=response.get("language"),
                    sentiment_score=response.get("sentiment", {}).get("score"),
                    sentiment_magnitude=response.get("sentiment", {}).get("magnitude"),
                    sentiment_label=response.get("sentiment", {}).get("label"),
                    categories=response.get("categories"),
                    entities=response.get("entities"),
                    keywords=response.get("keywords"),
                    summary=response.get("summary"),
                    model_id=model.id,
                    processing_time_ms=processing_time_ms
                )
                
                db.add(new_analysis)
                db.commit()
                db.refresh(new_analysis)
                
                response["analysis_id"] = new_analysis.id
        
        except Exception as e:
            # Log error but don't fail the request
            print(f"Error storing analysis results: {str(e)}")
    
    return response


@router.get("/{entity_type}/{entity_id}", response_model=TextAnalysisResponse)
async def get_entity_analysis(
    entity_type: str = Path(..., description="Type of entity (e.g., document, comment)"),
    entity_id: int = Path(..., description="ID of the entity"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get previously stored analysis results for a specific entity.
    """
    analysis = db.query(TextAnalysisResult).filter(
        TextAnalysisResult.entity_type == entity_type,
        TextAnalysisResult.entity_id == entity_id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for {entity_type} with ID {entity_id}"
        )
    
    return {
        "success": True,
        "analysis_id": analysis.id,
        "language": analysis.language,
        "sentiment": {
            "score": analysis.sentiment_score,
            "magnitude": analysis.sentiment_magnitude,
            "label": analysis.sentiment_label
        } if analysis.sentiment_score is not None else None,
        "categories": analysis.categories,
        "entities": analysis.entities,
        "keywords": analysis.keywords,
        "summary": analysis.summary,
        "processing_time_ms": analysis.processing_time_ms
    }


@router.delete("/{entity_type}/{entity_id}", response_model=BaseResponse)
async def delete_entity_analysis(
    entity_type: str = Path(..., description="Type of entity (e.g., document, comment)"),
    entity_id: int = Path(..., description="ID of the entity"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete analysis results for a specific entity.
    """
    analysis = db.query(TextAnalysisResult).filter(
        TextAnalysisResult.entity_type == entity_type,
        TextAnalysisResult.entity_id == entity_id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for {entity_type} with ID {entity_id}"
        )
    
    db.delete(analysis)
    db.commit()
    
    return {
        "success": True,
        "message": f"Analysis for {entity_type} ID {entity_id} deleted successfully"
    }
