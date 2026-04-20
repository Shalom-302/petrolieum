"""
Admin Routes

This module defines administrative API endpoints for managing the recommendation system,
including model training, configuration, and performance monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
import logging
from typing import Optional, List, Dict
import time

from app.core.db import get_db
from ..models.recommendation import RecommendationDB
from ..models.similarity import SimilarityMatrixDB

# Initialize router
router = APIRouter()
logger = logging.getLogger(__name__)

# Avoid circular import
def get_recommendation_plugin():
    """Get the recommendation plugin instance using secure approach"""
    # Import here to avoid circular import
    from ..main import recommendation_plugin
    return recommendation_plugin


@router.post("/train")
async def train_models(
    background_tasks: BackgroundTasks,
    algorithm: str = Query(..., regex="^(collaborative|matrix_factorization|content_based|all)$"),
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Trigger training of recommendation models
    """
    try:
        plugin = get_recommendation_plugin()
        # Check if training is already in progress
        if hasattr(plugin, '_training_in_progress') and plugin._training_in_progress:
            raise HTTPException(status_code=409, detail="Training already in progress")
        
        # Start training in background
        from ..tasks.model_refresh import refresh_models
        background_tasks.add_task(refresh_models, algorithm=algorithm, force=force)
        
        # Set training flag
        plugin._training_in_progress = True
        
        return {
            "status": "success", 
            "message": f"Training of {algorithm} models started in background"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting model training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting model training: {str(e)}")


@router.get("/status")
async def get_system_status(
    db: Session = Depends(get_db)
):
    """
    Get status information about the recommendation system
    """
    try:
        plugin = get_recommendation_plugin()
        # Get counts of various entities
        interaction_count = db.query(func.count(InteractionDB.id)).scalar() or 0
        user_count = db.query(func.count(func.distinct(InteractionDB.user_id))).scalar() or 0
        item_count = db.query(func.count(func.distinct(InteractionDB.item_id))).scalar() or 0
        
        # Get latest matrices
        latest_matrices = db.query(SimilarityMatrixDB).order_by(
            SimilarityMatrixDB.created_at.desc()
        ).limit(5).all()
        
        matrices_info = []
        for matrix in latest_matrices:
            matrices_info.append({
                "id": matrix.id,
                "type": matrix.matrix_type,
                "algorithm": matrix.algorithm,
                "dimensions": f"{matrix.rows}x{matrix.columns}",
                "created_at": matrix.created_at.isoformat()
            })
        
        # Get recommendation stats
        recommendations_count = db.query(func.count(RecommendationDB.id)).scalar() or 0
        click_count = db.query(func.count(RecommendationDB.id)).filter(
            RecommendationDB.was_clicked == 1
        ).scalar() or 0
        
        click_through_rate = 0
        if recommendations_count > 0:
            click_through_rate = (click_count / recommendations_count) * 100
        
        # Training status
        training_status = "idle"
        if hasattr(plugin, '_training_in_progress') and plugin._training_in_progress:
            training_status = "in_progress"
        
        return {
            "data_stats": {
                "interactions": interaction_count,
                "users": user_count,
                "items": item_count
            },
            "models": matrices_info,
            "recommendations": {
                "total": recommendations_count,
                "clicks": click_count,
                "click_through_rate": f"{click_through_rate:.2f}%"
            },
            "training_status": training_status,
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting system status: {str(e)}")


@router.delete("/purge_old_data")
async def purge_old_data(
    days: int = Query(30, ge=7, le=365),
    data_type: str = Query(..., regex="^(recommendations|interactions|all)$"),
    db: Session = Depends(get_db)
):
    """
    Remove old data from the system to maintain performance
    """
    try:
        import datetime
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        deleted_count = 0
        
        if data_type in ['recommendations', 'all']:
            # Delete old recommendations
            recommendations_result = db.query(RecommendationDB).filter(
                RecommendationDB.created_at < cutoff_date
            ).delete()
            deleted_count += recommendations_result
        
        if data_type in ['interactions', 'all']:
            # Delete old interactions, but preserve a minimum history per user
            from ..models.interaction import InteractionDB
            from sqlalchemy import func
            
            # Get list of users
            users = db.query(func.distinct(InteractionDB.user_id)).all()
            users = [u[0] for u in users]
            
            total_deleted = 0
            for user_id in users:
                # For each user, keep the most recent interactions
                # and delete older ones beyond the cutoff date
                recent_items = db.query(InteractionDB.item_id).filter(
                    InteractionDB.user_id == user_id
                ).order_by(InteractionDB.created_at.desc()).limit(100).all()
                recent_items = [i[0] for i in recent_items]
                
                # Delete old interactions for this user, but keep interactions with recent items
                result = db.query(InteractionDB).filter(
                    InteractionDB.user_id == user_id,
                    InteractionDB.created_at < cutoff_date,
                    ~InteractionDB.item_id.in_(recent_items)
                ).delete()
                
                total_deleted += result
            
            deleted_count += total_deleted
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Purged {deleted_count} records older than {days} days",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error purging old data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error purging old data: {str(e)}")


@router.post("/reset_recommendations")
async def reset_recommendations(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Reset the recommendation history for testing or after major algorithm changes
    """
    try:
        if user_id:
            # Reset for a specific user
            db.query(RecommendationDB).filter(
                RecommendationDB.user_id == user_id
            ).delete()
        else:
            # Reset for all users
            db.query(RecommendationDB).delete()
        
        db.commit()
        
        target = f"user {user_id}" if user_id else "all users"
        return {
            "status": "success",
            "message": f"Recommendation history reset for {target}"
        }
        
    except Exception as e:
        logger.error(f"Error resetting recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error resetting recommendations: {str(e)}")
