"""
Algorithm Service

This module implements the core recommendation algorithms including
collaborative filtering, matrix factorization, and content-based filtering.
"""
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from scipy.sparse.linalg import svds
from sklearn.metrics.pairwise import cosine_similarity
import logging
from datetime import datetime, timedelta
import json
import pickle
import time

from app.core.db import SessionLocal
from ..models.interaction import InteractionDB
from ..models.item import ItemFeatureDB
from ..models.similarity import SimilarityMatrixDB, ItemSimilarityDB
from ..models.recommendation import RecommendationDB, UserPreferenceDB

logger = logging.getLogger(__name__)

class AlgorithmService:
    """
    Service implementing recommendation algorithms and prediction generation
    """
    def __init__(self, encryption_handler=None):
        """
        Initialize the algorithm service with optional encryption handler
        
        Args:
            encryption_handler: Handler for encrypting/decrypting sensitive data
        """
        self.encryption_handler = encryption_handler
        
    async def recommend_collaborative_filtering(
        self, 
        user_id: int, 
        n_recommendations: int = 10,
        algorithm: str = "item_based",
        exclude_items: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations using collaborative filtering.
        
        Args:
            user_id: ID of the user
            n_recommendations: Number of recommendations to generate
            algorithm: 'item_based' or 'user_based'
            exclude_items: List of item IDs to exclude from recommendations
            
        Returns:
            List of recommended items with scores
        """
        db = SessionLocal()
        start_time = time.time()
        
        try:
            # Secure logging to protect user identity
            logger.info(
                f"Generating {algorithm} recommendations for user",
                extra={"user_id_hash": self.encryption_handler.hash_sensitive_data(str(user_id))}
            )
            
            # Get all user-item interactions
            interactions = db.query(InteractionDB).filter(
                InteractionDB.interaction_type.in_(['rating', 'view', 'purchase'])
            ).all()
            
            # Convert to DataFrame for matrix operations
            df = pd.DataFrame([
                (i.user_id, i.item_id, i.value) 
                for i in interactions
            ], columns=['user_id', 'item_id', 'value'])
            
            # Create utility matrix (users x items)
            utility_matrix = df.pivot(
                index='user_id', 
                columns='item_id', 
                values='value'
            ).fillna(0)
            
            # Handle new users not in the matrix
            if user_id not in utility_matrix.index:
                logger.info(f"New user {user_id}, returning popular items")
                return await self.recommend_popular_items(
                    n_recommendations=n_recommendations,
                    exclude_items=exclude_items
                )
            
            recommendations = []
            
            if algorithm == "item_based":
                # Check if we have a precomputed similarity matrix
                similarity_matrix = db.query(SimilarityMatrixDB).filter(
                    SimilarityMatrixDB.matrix_type == 'item-item',
                    SimilarityMatrixDB.algorithm == 'cosine'
                ).order_by(SimilarityMatrixDB.updated_at.desc()).first()
                
                if similarity_matrix:
                    # Use precomputed similarity matrix if available
                    matrix_data = pickle.loads(similarity_matrix.matrix_data)
                    item_similarity = matrix_data.get('matrix')
                    item_ids = matrix_data.get('item_ids')
                    
                    # Get items the user has interacted with
                    user_items = utility_matrix.loc[user_id].values
                    
                    # Generate scores using the similarity matrix
                    weighted_scores = np.zeros(len(item_ids))
                    for idx, item_id in enumerate(item_ids):
                        item_col = utility_matrix.columns.get_loc(item_id)
                        if user_items[item_col] > 0:
                            for other_idx, other_id in enumerate(item_ids):
                                weighted_scores[other_idx] += user_items[item_col] * item_similarity[item_col, other_idx]
                else:
                    # Compute item similarity on-the-fly
                    item_similarity = cosine_similarity(utility_matrix.T)
                    
                    # Get user ratings and compute weighted scores
                    user_ratings = utility_matrix.loc[user_id].values.reshape(1, -1)
                    weighted_scores = user_ratings.dot(item_similarity)[0]
                
                # Exclude items the user has already interacted with
                user_items = utility_matrix.loc[user_id]
                already_interacted = user_items[user_items > 0].index
                
                # Create exclude set
                exclude_set = set(already_interacted)
                if exclude_items:
                    exclude_set.update(exclude_items)
                
                # Generate recommendations
                for idx, item_id in enumerate(utility_matrix.columns):
                    if item_id not in exclude_set and weighted_scores[idx] > 0:
                        recommendations.append({
                            "item_id": int(item_id),
                            "score": float(weighted_scores[idx]),
                            "algorithm": "collaborative_item_based"
                        })
            
            elif algorithm == "user_based":
                # Compute user similarity
                user_similarity = cosine_similarity(utility_matrix)
                
                # Find similar users
                user_idx = utility_matrix.index.get_loc(user_id)
                similar_users_indices = user_similarity[user_idx].argsort()[-10:][::-1]
                similar_users = [
                    utility_matrix.index[idx] 
                    for idx in similar_users_indices 
                    if utility_matrix.index[idx] != user_id
                ]
                
                # Calculate predicted ratings
                predicted_ratings = np.zeros(len(utility_matrix.columns))
                similarity_sum = np.zeros(len(utility_matrix.columns))
                
                for similar_user in similar_users:
                    sim_score = user_similarity[user_idx, utility_matrix.index.get_loc(similar_user)]
                    
                    # Skip users with low similarity
                    if sim_score < 0.1:
                        continue
                        
                    similar_user_ratings = utility_matrix.loc[similar_user].values
                    
                    # For each item, add weighted rating from similar user
                    for idx, rating in enumerate(similar_user_ratings):
                        if rating > 0:
                            predicted_ratings[idx] += rating * sim_score
                            similarity_sum[idx] += sim_score
                
                # Normalize by similarity sum to get weighted average
                for idx in range(len(predicted_ratings)):
                    if similarity_sum[idx] > 0:
                        predicted_ratings[idx] /= similarity_sum[idx]
                
                # Exclude items the user has already interacted with
                user_items = utility_matrix.loc[user_id]
                already_interacted = user_items[user_items > 0].index
                
                # Create exclude set
                exclude_set = set(already_interacted)
                if exclude_items:
                    exclude_set.update(exclude_items)
                
                # Generate recommendations
                for idx, item_id in enumerate(utility_matrix.columns):
                    if item_id not in exclude_set and predicted_ratings[idx] > 0:
                        recommendations.append({
                            "item_id": int(item_id),
                            "score": float(predicted_ratings[idx]),
                            "algorithm": "collaborative_user_based"
                        })
            
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            # Sort by score and take top N
            recommendations.sort(key=lambda x: x["score"], reverse=True)
            recommendations = recommendations[:n_recommendations]
            
            # Add ranks
            for i, rec in enumerate(recommendations):
                rec["rank"] = i + 1
                
            # Log performance
            elapsed_time = time.time() - start_time
            logger.info(
                f"Generated {len(recommendations)} recommendations in {elapsed_time:.2f}s",
                extra={"algorithm": algorithm}
            )
            
            return recommendations
            
        except Exception as e:
            # Secure error logging
            logger.error(
                f"Error generating recommendations: {str(e)}",
                extra={"error_code": "RECOMMENDATION_ALGORITHM_ERROR"}
            )
            return []
        finally:
            db.close()
    
    async def recommend_matrix_factorization(
        self, 
        user_id: int, 
        n_recommendations: int = 10,
        n_factors: int = 50,
        exclude_items: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations using matrix factorization (SVD).
        
        Args:
            user_id: ID of the user
            n_recommendations: Number of recommendations to generate
            n_factors: Number of latent factors to use
            exclude_items: List of item IDs to exclude
            
        Returns:
            List of recommended items with scores
        """
        db = SessionLocal()
        start_time = time.time()
        
        try:
            # Secure logging to protect user identity
            logger.info(
                f"Generating matrix factorization recommendations for user",
                extra={"user_id_hash": self.encryption_handler.hash_sensitive_data(str(user_id))}
            )
            
            # Get interactions for matrix factorization
            interactions = db.query(InteractionDB).filter(
                InteractionDB.interaction_type == 'rating'
            ).all()
            
            # Convert to DataFrame
            df = pd.DataFrame([
                (i.user_id, i.item_id, i.value) 
                for i in interactions
            ], columns=['user_id', 'item_id', 'value'])
            
            # Create utility matrix (users x items)
            utility_matrix = df.pivot(
                index='user_id', 
                columns='item_id', 
                values='value'
            ).fillna(0)
            
            # Handle new users
            if user_id not in utility_matrix.index:
                return await self.recommend_popular_items(
                    n_recommendations=n_recommendations,
                    exclude_items=exclude_items
                )
            
            # Normalize the data (center around mean)
            utility_matrix_mean = utility_matrix.mean(axis=1)
            utility_matrix_demeaned = utility_matrix.sub(utility_matrix_mean, axis=0)
            
            # Fill NaN with zeros after demeaning
            utility_matrix_demeaned = utility_matrix_demeaned.fillna(0)
            
            # Convert to numpy array for SVD
            utility_np = utility_matrix_demeaned.values
            
            # Compute SVD
            U, sigma, Vt = svds(utility_np, k=min(n_factors, min(utility_np.shape)-1))
            
            # Convert sigma to diagonal matrix
            sigma_diag = np.diag(sigma)
            
            # Reconstruct the prediction matrix
            predicted_ratings = np.dot(np.dot(U, sigma_diag), Vt) + utility_matrix_mean.values.reshape(-1, 1)
            
            # Convert back to DataFrame
            predictions_df = pd.DataFrame(
                predicted_ratings,
                index=utility_matrix.index,
                columns=utility_matrix.columns
            )
            
            # Get user's predicted ratings
            user_predictions = predictions_df.loc[user_id]
            
            # Exclude items the user has already interacted with
            already_interacted = utility_matrix.loc[user_id]
            already_interacted = already_interacted[already_interacted > 0].index
            
            # Create exclude set
            exclude_set = set(already_interacted)
            if exclude_items:
                exclude_set.update(exclude_items)
            
            # Generate recommendations
            recommendations = []
            for item_id, score in user_predictions.items():
                if item_id not in exclude_set:
                    recommendations.append({
                        "item_id": int(item_id),
                        "score": float(score),
                        "algorithm": "matrix_factorization"
                    })
            
            # Sort by score and take top N
            recommendations.sort(key=lambda x: x["score"], reverse=True)
            recommendations = recommendations[:n_recommendations]
            
            # Add ranks
            for i, rec in enumerate(recommendations):
                rec["rank"] = i + 1
                
            # Log performance
            elapsed_time = time.time() - start_time
            logger.info(
                f"Generated {len(recommendations)} matrix factorization recommendations in {elapsed_time:.2f}s",
                extra={"n_factors": n_factors}
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(
                f"Error generating matrix factorization recommendations: {str(e)}",
                extra={"error_code": "MATRIX_FACTORIZATION_ERROR"}
            )
            return []
        finally:
            db.close()
    
    async def recommend_content_based(
        self, 
        user_id: int, 
        n_recommendations: int = 10,
        exclude_items: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate content-based recommendations based on item features.
        
        Args:
            user_id: ID of the user
            n_recommendations: Number of recommendations to generate
            exclude_items: List of item IDs to exclude
            
        Returns:
            List of recommended items with scores
        """
        # Implementation details omitted for brevity
        # Would analyze item features and user preferences to recommend similar items
        return []
    
    async def recommend_popular_items(
        self,
        n_recommendations: int = 10,
        timeframe: str = "month",
        exclude_items: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Recommend the most popular items based on interaction counts.
        
        Args:
            n_recommendations: Number of recommendations to generate
            timeframe: Timeframe for popularity calculation ('day', 'week', 'month', 'all')
            exclude_items: List of item IDs to exclude
            
        Returns:
            List of recommended items with scores
        """
        db = SessionLocal()
        
        try:
            # Calculate start date based on timeframe
            now = datetime.now()
            if timeframe == 'day':
                start_date = now - timedelta(days=1)
            elif timeframe == 'week':
                start_date = now - timedelta(weeks=1)
            elif timeframe == 'month':
                start_date = now - timedelta(days=30)
            else:  # 'all'
                start_date = datetime.min
            
            # Query for popular items
            query = db.query(
                InteractionDB.item_id,
                func.count(InteractionDB.id).label('count')
            ).filter(
                InteractionDB.created_at >= start_date
            ).group_by(
                InteractionDB.item_id
            ).order_by(
                func.count(InteractionDB.id).desc()
            )
            
            # Apply exclude filter if provided
            if exclude_items:
                query = query.filter(InteractionDB.item_id.notin_(exclude_items))
            
            # Get top N items
            popular_items = query.limit(n_recommendations).all()
            
            # Format recommendations
            recommendations = []
            for i, (item_id, count) in enumerate(popular_items):
                recommendations.append({
                    "item_id": item_id,
                    "score": float(count),
                    "rank": i + 1,
                    "algorithm": "popularity"
                })
                
            return recommendations
            
        except Exception as e:
            logger.error(
                f"Error generating popular item recommendations: {str(e)}",
                extra={"error_code": "POPULAR_ITEMS_ERROR"}
            )
            return []
        finally:
            db.close()
    
    async def recommend_hybrid(
        self, 
        user_id: int, 
        n_recommendations: int = 10,
        weights: Dict[str, float] = None,
        exclude_items: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate hybrid recommendations combining multiple algorithms.
        
        Args:
            user_id: ID of the user
            n_recommendations: Number of recommendations to generate
            weights: Dictionary of algorithm weights (defaults to equal weighting)
            exclude_items: List of item IDs to exclude
            
        Returns:
            List of recommended items with scores
        """
        # Default weights if not provided
        if weights is None:
            weights = {
                "collaborative_item_based": 0.4,
                "matrix_factorization": 0.3,
                "content_based": 0.2,
                "popularity": 0.1
            }
            
        # Get recommendations from each algorithm with more items than required
        # to ensure we have enough unique items after combining
        expanded_n = int(n_recommendations * 2.5)
        
        # Collect recommendations from each algorithm
        cf_items = await self.recommend_collaborative_filtering(
            user_id=user_id,
            n_recommendations=expanded_n,
            algorithm="item_based",
            exclude_items=exclude_items
        )
        
        mf_items = await self.recommend_matrix_factorization(
            user_id=user_id, 
            n_recommendations=expanded_n,
            exclude_items=exclude_items
        )
        
        content_items = await self.recommend_content_based(
            user_id=user_id,
            n_recommendations=expanded_n,
            exclude_items=exclude_items
        )
        
        popular_items = await self.recommend_popular_items(
            n_recommendations=expanded_n,
            exclude_items=exclude_items
        )
        
        # Collect all items and normalize scores within each algorithm
        all_items = {}
        
        # Helper function to normalize scores
        def normalize_scores(items):
            if not items:
                return []
                
            max_score = max(item["score"] for item in items) if items else 1.0
            min_score = min(item["score"] for item in items) if items else 0.0
            score_range = max_score - min_score
            
            if score_range == 0:
                score_range = 1.0
                
            for item in items:
                item["normalized_score"] = (item["score"] - min_score) / score_range
                
            return items
        
        # Normalize scores for each algorithm
        cf_items = normalize_scores(cf_items)
        mf_items = normalize_scores(mf_items)
        content_items = normalize_scores(content_items)
        popular_items = normalize_scores(popular_items)
        
        # Combine recommendations
        for item in cf_items:
            item_id = item["item_id"]
            if item_id not in all_items:
                all_items[item_id] = {
                    "item_id": item_id,
                    "algorithms": {},
                    "weighted_score": 0.0
                }
            all_items[item_id]["algorithms"]["collaborative_item_based"] = item["normalized_score"]
            all_items[item_id]["weighted_score"] += item["normalized_score"] * weights.get("collaborative_item_based", 0.0)
            
        for item in mf_items:
            item_id = item["item_id"]
            if item_id not in all_items:
                all_items[item_id] = {
                    "item_id": item_id,
                    "algorithms": {},
                    "weighted_score": 0.0
                }
            all_items[item_id]["algorithms"]["matrix_factorization"] = item["normalized_score"]
            all_items[item_id]["weighted_score"] += item["normalized_score"] * weights.get("matrix_factorization", 0.0)
        
        for item in content_items:
            item_id = item["item_id"]
            if item_id not in all_items:
                all_items[item_id] = {
                    "item_id": item_id,
                    "algorithms": {},
                    "weighted_score": 0.0
                }
            all_items[item_id]["algorithms"]["content_based"] = item["normalized_score"]
            all_items[item_id]["weighted_score"] += item["normalized_score"] * weights.get("content_based", 0.0)
            
        for item in popular_items:
            item_id = item["item_id"]
            if item_id not in all_items:
                all_items[item_id] = {
                    "item_id": item_id,
                    "algorithms": {},
                    "weighted_score": 0.0
                }
            all_items[item_id]["algorithms"]["popularity"] = item["normalized_score"]
            all_items[item_id]["weighted_score"] += item["normalized_score"] * weights.get("popularity", 0.0)
        
        # Sort by weighted score and take top N
        recommendations = list(all_items.values())
        recommendations.sort(key=lambda x: x["weighted_score"], reverse=True)
        recommendations = recommendations[:n_recommendations]
        
        # Format final recommendations
        final_recommendations = []
        for i, rec in enumerate(recommendations):
            final_recommendations.append({
                "item_id": rec["item_id"],
                "score": rec["weighted_score"],
                "rank": i + 1,
                "algorithm": "hybrid",
                "algorithm_scores": rec["algorithms"]
            })
            
        return final_recommendations
