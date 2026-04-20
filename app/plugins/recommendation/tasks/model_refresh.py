"""
Model Refresh Tasks

This module implements background tasks for refreshing recommendation models,
including training and evaluation of collaborative filtering, matrix factorization,
and content-based recommendation algorithms.
"""
import numpy as np
import pandas as pd
from scipy.sparse.linalg import svds
from sklearn.metrics.pairwise import cosine_similarity
import logging
import time
import pickle
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.core.db import SessionLocal
from ..models.interaction import InteractionDB
from ..models.similarity import SimilarityMatrixDB
from ..models.recommendation import UserPreferenceDB

logger = logging.getLogger(__name__)

# Get plugin instance to access encryption handler
from ..main import recommendation_plugin


async def refresh_models(algorithm: str = "all", force: bool = False):
    """
    Refresh recommendation models by training them on the latest data.
    
    Args:
        algorithm: Which algorithm to train ('collaborative', 'matrix_factorization', 'content_based', 'all')
        force: Whether to force retraining even if recent models exist
    """
    try:
        logger.info(f"Starting model refresh for {algorithm}")
        
        db = SessionLocal()
        
        try:
            # Check if we should refresh each type of model
            if algorithm in ["collaborative", "all"]:
                await _refresh_collaborative_models(db, force)
                
            if algorithm in ["matrix_factorization", "all"]:
                await _refresh_matrix_factorization_models(db, force)
                
            if algorithm in ["content_based", "all"]:
                await _refresh_content_based_models(db, force)
                
            logger.info(f"Model refresh completed for {algorithm}")
        finally:
            db.close()
            
        # Reset training flag
        recommendation_plugin._training_in_progress = False
        
    except Exception as e:
        logger.error(f"Error during model refresh: {str(e)}")
        # Reset training flag even on error
        recommendation_plugin._training_in_progress = False


async def _refresh_collaborative_models(db, force: bool = False):
    """
    Refresh collaborative filtering models.
    
    Args:
        db: Database session
        force: Whether to force retraining
    """
    start_time = time.time()
    
    # Skip if recent model exists and force is False
    if not force:
        recent_model = db.query(SimilarityMatrixDB).filter(
            SimilarityMatrixDB.matrix_type == "item-item",
            SimilarityMatrixDB.algorithm == "cosine"
        ).order_by(SimilarityMatrixDB.created_at.desc()).first()
        
        if recent_model and (datetime.now() - recent_model.created_at).days < 1:
            logger.info("Recent collaborative model exists, skipping refresh")
            return
    
    # Get all relevant interactions for collaborative filtering
    interactions = db.query(InteractionDB).filter(
        InteractionDB.interaction_type.in_(['rating', 'view', 'purchase'])
    ).all()
    
    if len(interactions) < 100:
        logger.warning("Not enough interactions for collaborative filtering, skipping")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame([
        (i.user_id, i.item_id, i.value) 
        for i in interactions
    ], columns=['user_id', 'item_id', 'value'])
    
    # Create utility matrix
    utility_matrix = df.pivot(
        index='user_id', 
        columns='item_id', 
        values='value'
    ).fillna(0)
    
    # Compute item-item similarity
    item_similarity = cosine_similarity(utility_matrix.T)
    
    # Serialize matrix data
    matrix_data = {
        'matrix': item_similarity,
        'item_ids': utility_matrix.columns.tolist(),
        'user_ids': utility_matrix.index.tolist()
    }
    
    serialized_matrix = pickle.dumps(matrix_data)
    
    # Store the new similarity matrix
    new_matrix = SimilarityMatrixDB(
        matrix_type="item-item",
        algorithm="cosine",
        matrix_data=serialized_matrix,
        rows=item_similarity.shape[0],
        columns=item_similarity.shape[1],
        metadata=f"{{\"items\": {len(utility_matrix.columns)}, \"users\": {len(utility_matrix.index)}}}",
        training_duration=(time.time() - start_time)
    )
    
    db.add(new_matrix)
    
    # Also compute user-user similarity
    user_similarity = cosine_similarity(utility_matrix)
    
    # Serialize user similarity matrix
    user_matrix_data = {
        'matrix': user_similarity,
        'user_ids': utility_matrix.index.tolist()
    }
    
    serialized_user_matrix = pickle.dumps(user_matrix_data)
    
    # Store the user similarity matrix
    new_user_matrix = SimilarityMatrixDB(
        matrix_type="user-user",
        algorithm="cosine",
        matrix_data=serialized_user_matrix,
        rows=user_similarity.shape[0],
        columns=user_similarity.shape[1],
        metadata=f"{{\"users\": {len(utility_matrix.index)}}}",
        training_duration=(time.time() - start_time)
    )
    
    db.add(new_user_matrix)
    db.commit()
    
    logger.info(
        f"Collaborative models refreshed in {time.time() - start_time:.2f}s",
        extra={
            "items": len(utility_matrix.columns),
            "users": len(utility_matrix.index)
        }
    )


async def _refresh_matrix_factorization_models(db, force: bool = False):
    """
    Refresh matrix factorization models.
    
    Args:
        db: Database session
        force: Whether to force retraining
    """
    start_time = time.time()
    
    # Skip if recent model exists and force is False
    if not force:
        recent_model = db.query(SimilarityMatrixDB).filter(
            SimilarityMatrixDB.matrix_type == "latent-factors",
            SimilarityMatrixDB.algorithm == "svd"
        ).order_by(SimilarityMatrixDB.created_at.desc()).first()
        
        if recent_model and (datetime.now() - recent_model.created_at).days < 1:
            logger.info("Recent matrix factorization model exists, skipping refresh")
            return
    
    # Get all ratings for matrix factorization
    interactions = db.query(InteractionDB).filter(
        InteractionDB.interaction_type == 'rating'
    ).all()
    
    if len(interactions) < 100:
        logger.warning("Not enough ratings for matrix factorization, skipping")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame([
        (i.user_id, i.item_id, i.value) 
        for i in interactions
    ], columns=['user_id', 'item_id', 'value'])
    
    # Create utility matrix
    utility_matrix = df.pivot(
        index='user_id', 
        columns='item_id', 
        values='value'
    ).fillna(0)
    
    # Normalize the data
    utility_matrix_mean = utility_matrix.mean(axis=1)
    utility_matrix_demeaned = utility_matrix.sub(utility_matrix_mean, axis=0)
    utility_matrix_demeaned = utility_matrix_demeaned.fillna(0)
    
    # Convert to numpy array
    utility_np = utility_matrix_demeaned.values
    
    # Number of factors
    n_factors = min(50, min(utility_np.shape) - 1)
    
    # Compute SVD
    U, sigma, Vt = svds(utility_np, k=n_factors)
    
    # Store user factors (U * sigma) for each user
    for i, user_id in enumerate(utility_matrix.index):
        user_preference = db.query(UserPreferenceDB).filter(
            UserPreferenceDB.user_id == user_id
        ).first()
        
        if not user_preference:
            user_preference = UserPreferenceDB(user_id=user_id)
            db.add(user_preference)
        
        # Store the latent factors for the user
        user_factors = U[i, :] * sigma
        user_preference.latent_factors = ",".join(map(str, user_factors))
    
    # Store the item factors (Vt.T) in a matrix
    item_factors = Vt.T
    
    # Serialize matrix data
    matrix_data = {
        'item_factors': item_factors,
        'item_ids': utility_matrix.columns.tolist(),
        'n_factors': n_factors
    }
    
    serialized_matrix = pickle.dumps(matrix_data)
    
    # Store the new similarity matrix
    new_matrix = SimilarityMatrixDB(
        matrix_type="latent-factors",
        algorithm="svd",
        matrix_data=serialized_matrix,
        rows=item_factors.shape[0],
        columns=item_factors.shape[1],
        metadata=f"{{\"items\": {len(utility_matrix.columns)}, \"users\": {len(utility_matrix.index)}, \"factors\": {n_factors}}}",
        training_duration=(time.time() - start_time)
    )
    
    db.add(new_matrix)
    db.commit()
    
    logger.info(
        f"Matrix factorization model refreshed in {time.time() - start_time:.2f}s",
        extra={
            "items": len(utility_matrix.columns),
            "users": len(utility_matrix.index),
            "factors": n_factors
        }
    )


async def _refresh_content_based_models(db, force: bool = False):
    """
    Refresh content-based recommendation models.
    
    Args:
        db: Database session
        force: Whether to force retraining
    """
    # Implementation for content-based models
    # This could include TF-IDF, Word2Vec, or other NLP techniques
    # to extract features from item text content
    
    # For brevity, we're not implementing the full content-based algorithm here
    logger.info("Content-based model refresh completed (placeholder)")
    pass
