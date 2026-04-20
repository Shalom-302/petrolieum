"""
Recommendation Routes

This module defines API endpoints for generating recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.orm import Session
import uuid
import time
import logging

from app.core.db import get_db
from ..services.algorithm_service import AlgorithmService
from ..schemas.recommendation import (
    RecommendationRequest, 
    SimilarItemsRequest,
    RecommendationResponse,
    RecommendedItem,
    AlgorithmType
)
from ..models.item import ItemFeatureDB
from ..models.recommendation import RecommendationDB

# Initialize router
router = APIRouter()
logger = logging.getLogger(__name__)

# Avoid circular import
def get_algorithm_service():
    """Get the algorithm service instance with secure configuration"""
    # Import here to avoid circular import
    from ..main import recommendation_plugin
    return recommendation_plugin.algorithm_service

@router.post("/items", response_model=RecommendationResponse)
async def recommend_items(
    request: RecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Generate personalized item recommendations for a user
    """
    start_time = time.time()
    
    try:
        algorithm_service = get_algorithm_service()
        
        # Generate recommendations based on requested algorithm
        if request.algorithm == AlgorithmType.COLLABORATIVE_USER_BASED:
            items = await algorithm_service.recommend_collaborative_filtering(
                user_id=request.user_id,
                n_recommendations=request.count,
                algorithm="user_based",
                exclude_items=request.exclude_items
            )
        elif request.algorithm == AlgorithmType.COLLABORATIVE_ITEM_BASED:
            items = await algorithm_service.recommend_collaborative_filtering(
                user_id=request.user_id,
                n_recommendations=request.count,
                algorithm="item_based",
                exclude_items=request.exclude_items
            )
        elif request.algorithm == AlgorithmType.MATRIX_FACTORIZATION:
            items = await algorithm_service.recommend_matrix_factorization(
                user_id=request.user_id,
                n_recommendations=request.count,
                exclude_items=request.exclude_items
            )
        elif request.algorithm == AlgorithmType.CONTENT_BASED:
            items = await algorithm_service.recommend_content_based(
                user_id=request.user_id,
                n_recommendations=request.count,
                exclude_items=request.exclude_items
            )
        elif request.algorithm == AlgorithmType.POPULARITY:
            items = await algorithm_service.recommend_popular_items(
                n_recommendations=request.count,
                exclude_items=request.exclude_items
            )
        elif request.algorithm == AlgorithmType.HYBRID:
            items = await algorithm_service.recommend_hybrid(
                user_id=request.user_id,
                n_recommendations=request.count,
                exclude_items=request.exclude_items
            )
        else:
            raise HTTPException(status_code=400, detail=f"Algorithm {request.algorithm} not supported")
        
        # If no recommendations found, return empty list
        if not items:
            return RecommendationResponse(
                user_id=request.user_id,
                items=[],
                context=request.context,
                total_items=0,
                algorithm=request.algorithm.value,
                generation_time=(time.time() - start_time) * 1000,
                recommendation_id=str(uuid.uuid4())
            )
        
        # Enrich recommendations with item details
        recommended_items = []
        item_ids = [item["item_id"] for item in items]
        item_features = db.query(ItemFeatureDB).filter(ItemFeatureDB.item_id.in_(item_ids)).all()
        
        # Create a lookup dict for item features
        item_features_dict = {feature.item_id: feature for feature in item_features}
        
        for item in items:
            item_id = item["item_id"]
            feature = item_features_dict.get(item_id)
            
            recommended_item = RecommendedItem(
                item_id=item_id,
                score=item["score"],
                rank=item.get("rank", 0),
                algorithm=item.get("algorithm", request.algorithm.value)
            )
            
            # Add item metadata if available
            if feature:
                recommended_item.title = feature.title
                recommended_item.description = feature.description
                
                # Parse categories if available
                if feature.categories:
                    recommended_item.categories = feature.categories.split(",")
                
                # Generate explanation based on algorithm
                if item.get("algorithm") == "collaborative_item_based":
                    recommended_item.reason = "Users who interacted with similar items also liked this"
                elif item.get("algorithm") == "collaborative_user_based":
                    recommended_item.reason = "Users with similar tastes enjoyed this"
                elif item.get("algorithm") == "content_based":
                    recommended_item.reason = "Based on your content preferences"
                elif item.get("algorithm") == "popularity":
                    recommended_item.reason = "Popular among other users"
                elif item.get("algorithm") == "hybrid":
                    recommended_item.reason = "Recommended based on multiple factors"
            
            recommended_items.append(recommended_item)
        
        # Create a unique recommendation ID
        recommendation_id = str(uuid.uuid4())
        
        # Store recommendations for tracking and evaluation
        for recommended_item in recommended_items:
            db_recommendation = RecommendationDB(
                user_id=request.user_id,
                item_id=recommended_item.item_id,
                algorithm=recommended_item.algorithm,
                score=recommended_item.score,
                rank=recommended_item.rank,
                context=request.context,
                expires_at=time.time() + (24 * 60 * 60)  # 24 hours expiry
            )
            db.add(db_recommendation)
        
        db.commit()
        
        # Prepare and return response
        return RecommendationResponse(
            user_id=request.user_id,
            items=recommended_items,
            context=request.context,
            total_items=len(recommended_items),
            algorithm=request.algorithm.value,
            generation_time=(time.time() - start_time) * 1000,
            recommendation_id=recommendation_id
        )
    
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")


@router.post("/similar", response_model=RecommendationResponse)
async def similar_items(
    request: SimilarItemsRequest,
    db: Session = Depends(get_db)
):
    """
    Find items similar to a given item
    """
    try:
        # Check if item exists
        item = db.query(ItemFeatureDB).filter(ItemFeatureDB.item_id == request.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item with ID {request.item_id} not found")
        
        # Implement logic to find similar items
        # For demonstration, this could use pre-computed similarities or
        # calculate similarities on the fly based on item features
        
        # Placeholder for similar items logic
        # In a real implementation, this would use the SimilarityService
        similar_items = []
        
        return RecommendationResponse(
            user_id=0,  # Not user-specific
            items=similar_items,
            context="similar_items",
            total_items=len(similar_items),
            algorithm=request.algorithm,
            generation_time=0,
            recommendation_id=str(uuid.uuid4())
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar items: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error finding similar items: {str(e)}")


@router.get("/trending", response_model=RecommendationResponse)
async def trending_items(
    count: int = Query(10, ge=1, le=100),
    time_period: str = Query("day", regex="^(day|week|month)$"),
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get trending items based on recent interactions
    """
    try:
        algorithm_service = get_algorithm_service()
        
        # Get popular items with time period filter
        items = await algorithm_service.recommend_popular_items(
            n_recommendations=count,
            timeframe=time_period
        )
        
        # Enrich with item details
        # Similar to the recommend_items endpoint implementation
        
        return RecommendationResponse(
            user_id=0,  # Not user-specific
            items=items,
            context="trending",
            total_items=len(items),
            algorithm="trending",
            generation_time=0,
            recommendation_id=str(uuid.uuid4())
        )
    
    except Exception as e:
        logger.error(f"Error getting trending items: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting trending items: {str(e)}")
