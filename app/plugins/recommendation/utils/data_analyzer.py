"""
Data Analyzer Utility

This module provides utility functions for analyzing recommendation data patterns
and extracting insights to improve recommendation quality.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import logging
from datetime import datetime, timedelta

from app.core.db import SessionLocal
from ..models.interaction import InteractionDB
from ..models.recommendation import RecommendationDB
from ..models.item import ItemFeatureDB
from ..main import recommendation_plugin

logger = logging.getLogger(__name__)


class RecommendationAnalyzer:
    """Utility class for analyzing recommendation data and extracting insights."""
    
    def __init__(self):
        """Initialize the analyzer with security handler from plugin."""
        self.security = recommendation_plugin.security_handler
    
    def analyze_interaction_patterns(self, user_id: Optional[int] = None,
                                    time_period: int = 30) -> Dict[str, Any]:
        """
        Analyze user interaction patterns to identify trends and preferences.
        
        Args:
            user_id: Optional user ID to analyze (None for all users)
            time_period: Days of history to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        db = SessionLocal()
        try:
            # Define time range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=time_period)
            
            # Build query
            query = db.query(InteractionDB).filter(
                InteractionDB.created_at.between(start_date, end_date)
            )
            
            if user_id is not None:
                query = query.filter(InteractionDB.user_id == user_id)
                
            interactions = query.all()
            
            if not interactions:
                return {"status": "no_data", "message": "No interaction data found for analysis"}
                
            # Convert to DataFrame for analysis
            df = pd.DataFrame([
                {
                    "user_id": i.user_id,
                    "item_id": i.item_id,
                    "interaction_type": i.interaction_type,
                    "value": i.value,
                    "created_at": i.created_at
                }
                for i in interactions
            ])
            
            # Analyze patterns using standardized approach
            results = self._process_interaction_data(df, user_id)
            
            # Log analysis outcome securely using standardized approach
            self.security.secure_log(
                message="Recommendation data analysis completed",
                data={
                    "user_id": user_id,
                    "time_period": time_period,
                    "results_count": len(results) if isinstance(results, dict) else 0
                }
            )
            
            return results
            
        finally:
            db.close()
    
    def _process_interaction_data(self, df: pd.DataFrame, 
                                user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Process interaction data to extract insights.
        
        Args:
            df: DataFrame containing interaction data
            user_id: Optional user ID (None for all users)
            
        Returns:
            Dictionary containing analysis results
        """
        results = {}
        
        # Skip analysis if insufficient data
        if len(df) < 10:
            return {"status": "insufficient_data", "count": len(df)}
        
        # Analyze interaction types distribution
        interaction_distribution = df['interaction_type'].value_counts().to_dict()
        results['interaction_distribution'] = interaction_distribution
        
        # Analyze time patterns
        df['hour'] = df['created_at'].dt.hour
        hourly_pattern = df.groupby('hour').size().to_dict()
        results['hourly_pattern'] = hourly_pattern
        
        # Analyze ratings distribution if present
        if 'rating' in df['interaction_type'].values:
            rating_df = df[df['interaction_type'] == 'rating']
            results['rating_stats'] = {
                'average': rating_df['value'].mean(),
                'median': rating_df['value'].median(),
                'count': len(rating_df)
            }
        
        # Calculate engagement score (custom metric)
        engagement_score = self._calculate_engagement_score(df)
        results['engagement_score'] = engagement_score
        
        # If analyzing a specific user, add user-specific insights
        if user_id is not None:
            results['user_specific'] = self._extract_user_preferences(df)
        
        return results
    
    def _calculate_engagement_score(self, df: pd.DataFrame) -> float:
        """
        Calculate a custom engagement score based on interaction patterns.
        
        Args:
            df: DataFrame containing interaction data
            
        Returns:
            Float representing engagement score (0-100)
        """
        # Define weights for different interaction types
        weights = {
            'purchase': 5.0,
            'rating': 3.0,
            'wishlist': 2.0,
            'view': 1.0,
            'click': 0.5
        }
        
        # Calculate weighted score
        score = 0
        total_possible = 0
        
        for interaction_type, weight in weights.items():
            count = len(df[df['interaction_type'] == interaction_type])
            score += count * weight
            total_possible += len(df) * weight
        
        # Normalize to 0-100 scale
        if total_possible > 0:
            normalized_score = (score / total_possible) * 100
        else:
            normalized_score = 0
            
        return round(normalized_score, 2)
    
    def _extract_user_preferences(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Extract user preferences from interaction data.
        
        Args:
            df: DataFrame containing interaction data
            
        Returns:
            Dictionary containing user preference insights
        """
        # Get most interacted items
        top_items = df['item_id'].value_counts().head(5).to_dict()
        
        # Get preferred interaction times
        hour_preferences = df.groupby('hour').size()
        peak_hours = hour_preferences[hour_preferences > hour_preferences.mean()].index.tolist()
        
        # Get category preferences if available
        # This would require joining with item metadata
        
        return {
            'top_items': top_items,
            'peak_hours': peak_hours
        }
    
    def analyze_recommendation_performance(self, algorithm: Optional[str] = None,
                                         time_period: int = 30) -> Dict[str, Any]:
        """
        Analyze performance of recommendation algorithms.
        
        Args:
            algorithm: Optional algorithm name to analyze (None for all)
            time_period: Days of history to analyze
            
        Returns:
            Dictionary containing performance metrics
        """
        db = SessionLocal()
        try:
            # Define time range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=time_period)
            
            # Build query
            query = db.query(RecommendationDB).filter(
                RecommendationDB.created_at.between(start_date, end_date)
            )
            
            if algorithm:
                query = query.filter(RecommendationDB.algorithm == algorithm)
                
            recommendations = query.all()
            
            if not recommendations:
                return {"status": "no_data", "message": "No recommendation data found for analysis"}
            
            # Process recommendation data to extract performance metrics
            # Implementation follows standardized security approach
            # ...
            
            # Return analysis results
            # This would include metrics like CTR, conversion rate, etc.
            return {
                "status": "success",
                "message": "Analysis completed",
                "metrics": {
                    "count": len(recommendations),
                    # Other metrics would be calculated here
                }
            }
            
        finally:
            db.close()
