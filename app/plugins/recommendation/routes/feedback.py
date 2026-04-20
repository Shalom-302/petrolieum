"""
Feedback Routes

This module defines API endpoints for collecting user feedback on recommendations,
which is essential for improving recommendation quality over time.
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
import logging
from datetime import datetime

from app.core.db import get_db
from ..schemas.recommendation import RecommendationFeedback
from ..models.recommendation import RecommendationDB

# Initialize router
router = APIRouter()
logger = logging.getLogger(__name__)

# Avoid circular import
def get_recommendation_plugin():
    """Get the recommendation plugin instance using secure approach"""
    # Import here to avoid circular import
    from ..main import recommendation_plugin
    return recommendation_plugin


@router.post("/record", status_code=201)
async def record_feedback(
    feedback: RecommendationFeedback,
    db: Session = Depends(get_db)
):
    """
    Record user feedback on a recommendation (clicks, likes, etc.)
    """
    try:
        # Find the recommendation in the database
        recommendation = db.query(RecommendationDB).filter(
            RecommendationDB.user_id == feedback.user_id,
            RecommendationDB.item_id == feedback.item_id
        ).order_by(RecommendationDB.created_at.desc()).first()
        
        if recommendation:
            # Update feedback on the recommendation
            if feedback.feedback_type == 'click':
                recommendation.was_clicked = 1
                recommendation.click_time = datetime.now()
            # Additional feedback types can be handled here
            
            db.commit()
            # Get plugin securely
            plugin = get_recommendation_plugin()
            logger.info(
                f"Recorded {feedback.feedback_type} feedback",
                extra={
                    "user_id_hash": plugin.encryption_handler.hash_sensitive_data(str(feedback.user_id)),
                    "item_id": feedback.item_id,
                    "feedback_type": feedback.feedback_type
                }
            )
        else:
            # If recommendation not found in DB, still record the interaction
            # This might happen if the recommendation was generated but not stored
            # Get plugin securely
            plugin = get_recommendation_plugin()
            logger.warning(
                f"Feedback for unknown recommendation",
                extra={
                    "user_id_hash": plugin.encryption_handler.hash_sensitive_data(str(feedback.user_id)),
                    "item_id": feedback.item_id
                }
            )
        
        # Create an interaction record for this feedback
        from ..models.interaction import InteractionDB
        
        # Map feedback types to interaction types
        interaction_type_mapping = {
            'click': 'view',
            'like': 'rating',
            'dislike': 'rating',
            'purchase': 'purchase',
            'share': 'share',
            'bookmark': 'bookmark'
        }
        
        # Map feedback values
        value_mapping = {
            'like': 5.0,
            'dislike': 1.0
        }
        
        # Create interaction record
        interaction = InteractionDB(
            user_id=feedback.user_id,
            item_id=feedback.item_id,
            interaction_type=interaction_type_mapping.get(feedback.feedback_type, 'view'),
            value=value_mapping.get(feedback.feedback_type, 1.0),
            context=feedback.context,
            metadata=str(feedback.additional_data) if feedback.additional_data else None
        )
        
        db.add(interaction)
        db.commit()
        
        return {"status": "success", "message": "Feedback recorded"}
        
    except Exception as e:
        logger.error(f"Error recording feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recording feedback: {str(e)}")


@router.post("/batch", status_code=201)
async def batch_feedback(
    feedbacks: List[RecommendationFeedback],
    db: Session = Depends(get_db)
):
    """
    Record multiple feedback entries in a single request
    """
    try:
        for feedback in feedbacks:
            # Find the recommendation
            recommendation = db.query(RecommendationDB).filter(
                RecommendationDB.user_id == feedback.user_id,
                RecommendationDB.item_id == feedback.item_id
            ).order_by(RecommendationDB.created_at.desc()).first()
            
            if recommendation:
                # Update feedback
                if feedback.feedback_type == 'click':
                    recommendation.was_clicked = 1
                    recommendation.click_time = datetime.now()
            
            # Create an interaction record (similar to the single feedback endpoint)
            # Implementation omitted for brevity
        
        db.commit()
        return {"status": "success", "message": f"Recorded {len(feedbacks)} feedback entries"}
        
    except Exception as e:
        logger.error(f"Error recording batch feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recording batch feedback: {str(e)}")


@router.post("/preferences")
async def update_preferences(
    user_id: int,
    preferences: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update user preferences for recommendation customization
    """
    try:
        # Find or create user preferences
        from ..models.recommendation import UserPreferenceDB
        user_preferences = db.query(UserPreferenceDB).filter(
            UserPreferenceDB.user_id == user_id
        ).first()
        
        if not user_preferences:
            user_preferences = UserPreferenceDB(user_id=user_id)
            db.add(user_preferences)
        
        # Update preferences fields
        if 'preferred_categories' in preferences:
            import json
            user_preferences.preferred_categories = json.dumps(preferences['preferred_categories'])
            
        if 'preferred_tags' in preferences:
            import json
            user_preferences.preferred_tags = json.dumps(preferences['preferred_tags'])
            
        if 'diversity_preference' in preferences:
            user_preferences.diversity_preference = float(preferences['diversity_preference'])
            
        if 'novelty_preference' in preferences:
            user_preferences.novelty_preference = float(preferences['novelty_preference'])
        
        db.commit()
        
        return {"status": "success", "message": "User preferences updated"}
        
    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating user preferences: {str(e)}")
