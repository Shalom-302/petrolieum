"""
Analytics Service for Push Notifications

This module provides analytics functions for the push notifications plugin,
implementing the standardized security approach.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, cast, Date
from fastapi import HTTPException

from app.plugins.push_notifications.models.database import Notification, Device, NotificationDevice
from app.plugins.push_notifications.handlers.security_handler import SecurityHandler

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for notification analytics."""
    
    def __init__(self, db: Session, security_handler: SecurityHandler = None, redis_handler=None):
        """
        Initialize analytics service.
        
        Args:
            db: Database session
            security_handler: Security handler for encryption/decryption
            redis_handler: Redis cache handler
        """
        self.db = db
        self.security_handler = security_handler
        self.redis_handler = redis_handler
        logger.info("Analytics service initialized")
        
    def get_delivery_stats(self, start_date: Optional[datetime] = None, 
                         end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get notification delivery statistics.
        
        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            
        Returns:
            Dict with notification statistics
        """
        try:
            # Set default dates if not provided
            if not end_date:
                end_date = datetime.utcnow()
                
            if not start_date:
                start_date = end_date - timedelta(days=30)  # Last 30 days by default
                
            # Query for notification deliveries in the date range
            query = self.db.query(NotificationDevice).filter(
                NotificationDevice.created_at >= start_date,
                NotificationDevice.created_at <= end_date
            )
            
            # Count total notifications
            total_count = query.count()
            
            # Status counts
            delivered_count = query.filter(NotificationDevice.status == "delivered").count()
            failed_count = query.filter(NotificationDevice.status == "failed").count()
            pending_count = query.filter(NotificationDevice.status == "pending").count()
            opened_count = query.filter(NotificationDevice.read_at.isnot(None)).count()
            
            # Calculate success rate
            success_rate = 0
            if total_count > 0:
                success_rate = (delivered_count / total_count) * 100
                
            return {
                "total": total_count,
                "delivered": delivered_count,
                "failed": failed_count,
                "pending": pending_count,
                "opened": opened_count,
                "success_rate": round(success_rate, 2),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting delivery stats: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get delivery stats: {str(e)}")
            
    def get_daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get daily notification statistics.
        
        Args:
            days: Number of days to include
            
        Returns:
            List of daily stats
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Query for daily counts
            daily_counts = self.db.query(
                cast(NotificationDevice.created_at, Date).label('date'),
                func.count().label('total'),
                func.sum(func.case(
                    [(NotificationDevice.status == "delivered", 1)], 
                    else_=0
                )).label('delivered'),
                func.sum(func.case(
                    [(NotificationDevice.status == "failed", 1)], 
                    else_=0
                )).label('failed'),
                func.sum(func.case(
                    [(NotificationDevice.read_at.isnot(None), 1)], 
                    else_=0
                )).label('opened')
            ).filter(
                NotificationDevice.created_at >= start_date,
                NotificationDevice.created_at <= end_date
            ).group_by(
                cast(NotificationDevice.created_at, Date)
            ).order_by(
                cast(NotificationDevice.created_at, Date)
            ).all()
            
            # Format results
            result = []
            for day in daily_counts:
                success_rate = 0
                if day.total > 0:
                    success_rate = (day.delivered / day.total) * 100
                    
                result.append({
                    "date": day.date.isoformat(),
                    "total": day.total,
                    "delivered": day.delivered or 0,
                    "failed": day.failed or 0,
                    "opened": day.opened or 0,
                    "success_rate": round(success_rate, 2)
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Error getting daily stats: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get daily stats: {str(e)}")
    
    def get_device_stats(self) -> Dict[str, Any]:
        """
        Get device statistics.
        
        Returns:
            Dict with device statistics
        """
        try:
            # Total devices
            total_devices = self.db.query(Device).count()
            
            # Active devices (with at least one opened notification)
            active_devices = self.db.query(distinct(NotificationDevice.device_id)).filter(
                NotificationDevice.read_at.isnot(None)
            ).count()
            
            # Calculate engagement rate
            engagement_rate = 0
            if total_devices > 0:
                engagement_rate = (active_devices / total_devices) * 100
                
            return {
                "total_devices": total_devices,
                "active_devices": active_devices,
                "engagement_rate": round(engagement_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting device stats: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get device stats: {str(e)}")
    
    def get_top_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top performing notifications by open rate.
        
        Args:
            limit: Number of notifications to return
            
        Returns:
            List of top notifications with stats
        """
        try:
            # Subquery to get delivery counts
            delivered_counts = self.db.query(
                NotificationDevice.notification_id,
                func.count().label('delivered_count')
            ).filter(
                NotificationDevice.status == "delivered"
            ).group_by(
                NotificationDevice.notification_id
            ).subquery()
            
            # Subquery to get open counts
            opened_counts = self.db.query(
                NotificationDevice.notification_id,
                func.count().label('opened_count')
            ).filter(
                NotificationDevice.read_at.isnot(None)
            ).group_by(
                NotificationDevice.notification_id
            ).subquery()
            
            # Join with notifications
            top_notifications = self.db.query(
                Notification.id,
                Notification.title,
                Notification.created_at,
                delivered_counts.c.delivered_count,
                opened_counts.c.opened_count
            ).join(
                delivered_counts, 
                Notification.id == delivered_counts.c.notification_id
            ).outerjoin(
                opened_counts,
                Notification.id == opened_counts.c.notification_id
            ).order_by(
                (opened_counts.c.opened_count / delivered_counts.c.delivered_count).desc()
            ).limit(limit).all()
            
            # Format results and calculate open rates
            result = []
            for notification in top_notifications:
                delivered = notification.delivered_count or 0
                opened = notification.opened_count or 0
                
                open_rate = 0
                if delivered > 0:
                    open_rate = (opened / delivered) * 100
                    
                result.append({
                    "notification_id": notification.id,
                    "title": notification.title,
                    "created_at": notification.created_at.isoformat(),
                    "delivered_count": delivered,
                    "opened_count": opened,
                    "open_rate": round(open_rate, 2)
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Error getting top notifications: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get top notifications: {str(e)}")
            
    def get_segment_performance(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get notification performance by user segment.
        
        Args:
            days: Number of days to include
            
        Returns:
            List of segment performance metrics
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # This is a complex query that would depend on how segments are implemented
            # For now, return a placeholder with empty results
            logger.info("Segment performance analytics not yet implemented")
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting segment performance: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get segment performance: {str(e)}")
