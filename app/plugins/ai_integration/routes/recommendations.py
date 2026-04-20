"""
Routes for content recommendations.

This module defines API endpoints for retrieving and managing AI-generated 
content recommendations for users.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import time

from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_user
from app.plugins.ai_integration.models import (
    ContentRecommendation, AIProvider, AIModel, AIModelType
)
from app.plugins.ai_integration.schemas import (
    RecommendationRequest, RecommendationResponse, RecommendationItem, BaseResponse
)
from app.plugins.ai_integration.utils.ai_client import get_ai_client

router = APIRouter(
    prefix="/recommendations"
)


@router.post("", response_model=RecommendationResponse)
async def get_recommendations(
    recommendation_request: RecommendationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get content recommendations for a user.
    
    This endpoint uses AI models to generate personalized content recommendations
    based on user history, preferences, and behavior.
    """
    # Check if user_id matches current_user or if admin
    if recommendation_request.user_id != current_user.get("id") and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="You can only request recommendations for yourself"
        )
    
    # Check for existing recommendations that are still valid
    existing_recommendations = db.query(ContentRecommendation).filter(
        ContentRecommendation.user_id == recommendation_request.user_id,
        ContentRecommendation.content_type == recommendation_request.content_type,
        ContentRecommendation.is_active == True
    ).all()
    
    # If we have existing recommendations, return them
    if existing_recommendations:
        items = []
        for rec in existing_recommendations[:recommendation_request.limit]:
            items.append({
                "content_id": rec.content_id,
                "content_type": rec.content_type,
                "score": rec.score,
                "reason": rec.reason
            })
        
        return {
            "success": True,
            "items": items,
            "total": len(items)
        }
    
    # Otherwise, generate new recommendations
    # Find a default model for recommendations
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
            detail="No active models found for generating recommendations"
        )
    
    # Get AI client
    ai_client = get_ai_client(provider)
    
    # Generate recommendations
    # In a real implementation, this would use the user's history, behavior, etc.
    # For now, we'll just generate some sample recommendations
    try:
        # Call AI service to get recommendations
        # This is a placeholder - real implementation would use the AI client
        recommendations = generate_sample_recommendations(
            recommendation_request.user_id, 
            recommendation_request.content_type, 
            recommendation_request.limit,
            recommendation_request.filters
        )
        
        # Store recommendations in database
        for rec in recommendations:
            db_rec = ContentRecommendation(
                user_id=recommendation_request.user_id,
                content_type=recommendation_request.content_type,
                content_id=rec["content_id"],
                score=rec["score"],
                reason=rec["reason"],
                is_active=True
            )
            db.add(db_rec)
        
        db.commit()
        
        return {
            "success": True,
            "items": recommendations,
            "total": len(recommendations)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating recommendations: {str(e)}"
        )


@router.post("/{content_id}/feedback", response_model=BaseResponse)
async def provide_recommendation_feedback(
    content_id: int = Path(..., description="ID of the recommended content"),
    content_type: str = Query(..., description="Type of content"),
    liked: bool = Query(..., description="Whether the user liked the recommendation"),
    feedback: Optional[str] = Query(None, description="Optional feedback text"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Provide feedback on a recommendation.
    
    This feedback can be used to improve future recommendations.
    """
    # Find the recommendation
    recommendation = db.query(ContentRecommendation).filter(
        ContentRecommendation.content_id == content_id,
        ContentRecommendation.content_type == content_type,
        ContentRecommendation.user_id == current_user.get("id"),
        ContentRecommendation.is_active == True
    ).first()
    
    if not recommendation:
        raise HTTPException(
            status_code=404,
            detail=f"No active recommendation found for {content_type} ID {content_id}"
        )
    
    # Update recommendation with feedback
    recommendation.user_feedback = liked
    recommendation.feedback_text = feedback
    
    db.add(recommendation)
    db.commit()
    
    return {
        "success": True,
        "message": "Feedback recorded successfully"
    }


@router.delete("", response_model=BaseResponse)
async def clear_recommendations(
    content_type: Optional[str] = Query(None, description="Type of content to clear recommendations for"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Clear active recommendations for the current user.
    
    If content_type is specified, only recommendations for that type are cleared.
    Otherwise, all recommendations for the user are cleared.
    """
    query = db.query(ContentRecommendation).filter(
        ContentRecommendation.user_id == current_user.get("id"),
        ContentRecommendation.is_active == True
    )
    
    if content_type:
        query = query.filter(ContentRecommendation.content_type == content_type)
    
    # Mark recommendations as inactive rather than deleting them
    recommendations = query.all()
    for rec in recommendations:
        rec.is_active = False
        db.add(rec)
    
    db.commit()
    
    message = "All recommendations cleared" if not content_type else f"Recommendations for {content_type} cleared"
    
    return {
        "success": True,
        "message": message
    }


# Helper function for generating sample recommendations
# In a real implementation, this would be replaced with actual AI-generated recommendations
def generate_sample_recommendations(user_id: int, content_type: str, limit: int, filters: Optional[Dict[str, Any]]) -> List[RecommendationItem]:
    """Generate sample recommendations for testing."""
    recommendations = []
    
    # Generate some sample recommendations
    for i in range(1, limit + 1):
        score = 1.0 - (i * 0.05)  # Decreasing scores
        recommendation = {
            "content_id": 100 + i,
            "content_type": content_type,
            "score": score,
            "reason": f"Based on your recent activity and preferences"
        }
        recommendations.append(recommendation)
    
    return recommendations
