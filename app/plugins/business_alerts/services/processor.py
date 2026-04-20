"""
Alert processor service.

This module contains the AlertProcessor service responsible for processing
and analyzing business alerts, including deduplication, aggregation, and
correlation of related alerts.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from app.core.security import create_default_encryption
from app.plugins.business_alerts.models.alert import BusinessAlertDB

logger = logging.getLogger(__name__)


class AlertProcessor:
    """
    Service for processing and analyzing business alerts.
    
    This service provides logic for advanced alert processing, including
    deduplication, correlation of related alerts, and trend analysis.
    It follows the standardized security approach used across the application.
    """
    
    def __init__(self, db: Session, encryption_handler=None):
        """
        Initialize the alert processor service.
        
        Args:
            db: Database session
            encryption_handler: Optional encryption handler for sensitive data
        """
        self.db = db
        self.encryption_handler = encryption_handler or create_default_encryption()
        self.logger = logging.getLogger(__name__)
    
    def deduplicate_alerts(self, entity_type: str, alert_type: str, time_window_minutes: int = 60) -> int:
        """
        Deduplicate alerts of the same type for the same entity.
        
        Args:
            entity_type: Type of entity to deduplicate alerts for
            alert_type: Type of alert to deduplicate
            time_window_minutes: Time window in minutes for deduplication
            
        Returns:
            int: Number of alerts marked as duplicates
        """
        self.logger.info(f"Deduplicating {entity_type}/{alert_type} alerts with {time_window_minutes}m window")
        
        try:
            # Find duplicate alerts within the time window
            window_start = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            
            # Get all entities with multiple active alerts of the same type
            query = """
            WITH alert_groups AS (
                SELECT 
                    entity_id,
                    MIN(created_at) as first_alert_time,
                    COUNT(*) as alert_count
                FROM 
                    business_alerts
                WHERE 
                    entity_type = :entity_type
                    AND alert_type = :alert_type
                    AND status = 'active'
                    AND created_at >= :window_start
                GROUP BY 
                    entity_id
                HAVING 
                    COUNT(*) > 1
            )
            SELECT 
                ba.id,
                ba.entity_id,
                ba.created_at
            FROM 
                business_alerts ba
            JOIN 
                alert_groups ag ON ba.entity_id = ag.entity_id
            WHERE 
                ba.entity_type = :entity_type
                AND ba.alert_type = :alert_type
                AND ba.status = 'active'
                AND ba.created_at >= :window_start
                AND ba.created_at > ag.first_alert_time
            ORDER BY 
                ba.entity_id, ba.created_at
            """
            
            duplicate_alerts = self.db.execute(
                text(query), 
                {
                    "entity_type": entity_type,
                    "alert_type": alert_type,
                    "window_start": window_start
                }
            ).fetchall()
            
            # Mark duplicates with the original alert reference
            duplicate_count = 0
            for alert_id, entity_id, created_at in duplicate_alerts:
                # Find the original alert
                original_alert = self.db.query(BusinessAlertDB).filter(
                    BusinessAlertDB.entity_type == entity_type,
                    BusinessAlertDB.entity_id == entity_id,
                    BusinessAlertDB.alert_type == alert_type,
                    BusinessAlertDB.status == 'active',
                    BusinessAlertDB.created_at < created_at
                ).order_by(BusinessAlertDB.created_at).first()
                
                if original_alert:
                    # Mark this alert as a duplicate
                    duplicate_alert = self.db.query(BusinessAlertDB).filter(
                        BusinessAlertDB.id == alert_id
                    ).first()
                    
                    if duplicate_alert:
                        # Update the alert with secure handling of details
                        current_details = self.encryption_handler.decrypt_data(duplicate_alert.details) if duplicate_alert.details else {}
                        
                        duplicate_alert.status = "resolved"
                        duplicate_alert.resolved_at = datetime.utcnow()
                        duplicate_alert.details = self.encryption_handler.encrypt_data({
                            **(current_details or {}),
                            "resolution_type": "duplicate",
                            "original_alert_id": original_alert.id,
                            "duplicate_detected_at": datetime.utcnow().isoformat()
                        })
                        
                        duplicate_count += 1
            
            # Commit all changes at once
            if duplicate_count > 0:
                self.db.commit()
                
            self.logger.info(f"Deduplicated {duplicate_count} alerts for {entity_type}/{alert_type}")
            return duplicate_count
            
        except Exception as e:
            self.logger.error(f"Error deduplicating alerts: {str(e)}")
            self.db.rollback()
            raise
    
    def correlate_alerts(self, time_window_minutes: int = 120) -> List[Dict[str, Any]]:
        """
        Correlate related alerts to identify patterns or potential incidents.
        
        Args:
            time_window_minutes: Time window in minutes for correlation
            
        Returns:
            List[Dict[str, Any]]: List of correlated alert groups
        """
        self.logger.info(f"Correlating alerts within {time_window_minutes}m window")
        
        try:
            # Define time window for correlation
            window_start = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            
            # Find entities with multiple different alert types
            query = """
            WITH entity_alerts AS (
                SELECT 
                    entity_type,
                    entity_id,
                    COUNT(DISTINCT alert_type) as alert_type_count
                FROM 
                    business_alerts
                WHERE 
                    status IN ('active', 'acknowledged')
                    AND created_at >= :window_start
                GROUP BY 
                    entity_type, entity_id
                HAVING 
                    COUNT(DISTINCT alert_type) > 1
            )
            SELECT 
                ea.entity_type,
                ea.entity_id,
                ea.alert_type_count
            FROM 
                entity_alerts ea
            ORDER BY 
                ea.alert_type_count DESC
            """
            
            correlated_entities = self.db.execute(
                text(query),
                {"window_start": window_start}
            ).fetchall()
            
            # Build correlation results
            correlation_results = []
            for entity_type, entity_id, alert_type_count in correlated_entities:
                # Get all active alerts for this entity
                alerts = self.db.query(BusinessAlertDB).filter(
                    BusinessAlertDB.entity_type == entity_type,
                    BusinessAlertDB.entity_id == entity_id,
                    BusinessAlertDB.status.in_(['active', 'acknowledged']),
                    BusinessAlertDB.created_at >= window_start
                ).all()
                
                if alerts:
                    # Determine highest severity
                    severity_map = {"critical": 3, "warning": 2, "info": 1}
                    highest_severity = max(alerts, key=lambda a: severity_map.get(a.severity, 0)).severity
                    
                    # Build correlation group
                    correlation_results.append({
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "alert_count": len(alerts),
                        "alert_type_count": alert_type_count,
                        "severity": highest_severity,
                        "alert_types": [alert.alert_type for alert in alerts],
                        "alert_ids": [alert.id for alert in alerts],
                        "correlation_time": datetime.utcnow().isoformat()
                    })
            
            self.logger.info(f"Found {len(correlation_results)} correlated alert groups")
            return correlation_results
            
        except Exception as e:
            self.logger.error(f"Error correlating alerts: {str(e)}")
            raise
    
    def analyze_alert_trends(
        self, 
        days: int = 30,
        entity_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze alert trends over time.
        
        Args:
            days: Number of days to analyze
            entity_type: Optional entity type to filter by
            
        Returns:
            Dict[str, Any]: Alert trend analysis
        """
        self.logger.info(f"Analyzing alert trends over {days} days" + 
                       (f" for {entity_type}" if entity_type else ""))
        
        try:
            # Define time window for analysis
            window_start = datetime.utcnow() - timedelta(days=days)
            
            # Base query parameters
            params = {"window_start": window_start}
            type_filter = ""
            
            if entity_type:
                type_filter = "AND entity_type = :entity_type"
                params["entity_type"] = entity_type
            
            # Daily alert counts
            daily_query = f"""
            SELECT 
                DATE_TRUNC('day', created_at) as alert_date,
                alert_type,
                severity,
                COUNT(*) as alert_count
            FROM 
                business_alerts
            WHERE 
                created_at >= :window_start
                {type_filter}
            GROUP BY 
                DATE_TRUNC('day', created_at),
                alert_type,
                severity
            ORDER BY 
                alert_date DESC,
                alert_type,
                severity
            """
            
            daily_results = self.db.execute(
                text(daily_query),
                params
            ).fetchall()
            
            # Format for output
            daily_trends = []
            for result in daily_results:
                daily_trends.append({
                    "date": result.alert_date.strftime("%Y-%m-%d"),
                    "alert_type": result.alert_type,
                    "severity": result.severity,
                    "count": result.alert_count
                })
            
            # Alert type distribution
            type_query = f"""
            SELECT 
                alert_type,
                COUNT(*) as alert_count
            FROM 
                business_alerts
            WHERE 
                created_at >= :window_start
                {type_filter}
            GROUP BY 
                alert_type
            ORDER BY 
                alert_count DESC
            """
            
            type_results = self.db.execute(
                text(type_query),
                params
            ).fetchall()
            
            # Format for output
            type_distribution = []
            for result in type_results:
                type_distribution.append({
                    "alert_type": result.alert_type,
                    "count": result.alert_count,
                    "percentage": 0  # Will calculate after getting total
                })
            
            # Calculate percentages
            if type_distribution:
                total_alerts = sum(item["count"] for item in type_distribution)
                for item in type_distribution:
                    item["percentage"] = round((item["count"] / total_alerts) * 100, 2)
            
            # Build final analysis
            analysis = {
                "time_window": f"{days} days",
                "start_date": window_start.strftime("%Y-%m-%d"),
                "end_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "total_alerts": sum(item["count"] for item in daily_trends),
                "entity_type": entity_type,
                "daily_trends": daily_trends,
                "type_distribution": type_distribution,
                "analysis_time": datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Completed trend analysis for {analysis['total_alerts']} alerts")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing alert trends: {str(e)}")
            raise
            
    def get_entity_risk_assessment(
        self, 
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """
        Generate a risk assessment for a specific entity based on its alerts.
        
        Args:
            entity_type: Type of entity to assess
            entity_id: ID of the entity to assess
            
        Returns:
            Dict[str, Any]: Risk assessment details
        """
        self.logger.info(f"Generating risk assessment for {entity_type}:{entity_id}")
        
        try:
            # Get all alerts for this entity
            alerts = self.db.query(BusinessAlertDB).filter(
                BusinessAlertDB.entity_type == entity_type,
                BusinessAlertDB.entity_id == entity_id
            ).all()
            
            # Calculate risk metrics
            total_alerts = len(alerts)
            active_alerts = sum(1 for a in alerts if a.status == 'active')
            critical_alerts = sum(1 for a in alerts if a.severity == 'critical')
            warning_alerts = sum(1 for a in alerts if a.severity == 'warning')
            
            # Calculate risk score (example algorithm)
            # Higher score = higher risk
            risk_score = min(100, (
                (critical_alerts * 25) +
                (warning_alerts * 10) +
                (active_alerts * 5)
            ))
            
            # Determine risk level
            risk_level = "low"
            if risk_score >= 75:
                risk_level = "high"
            elif risk_score >= 40:
                risk_level = "medium"
                
            # Get most recent alerts
            recent_alerts = sorted(
                [a for a in alerts if a.status == 'active'],
                key=lambda a: a.created_at,
                reverse=True
            )[:5]
            
            # Build risk assessment
            assessment = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "alert_metrics": {
                    "total_alerts": total_alerts,
                    "active_alerts": active_alerts,
                    "critical_alerts": critical_alerts,
                    "warning_alerts": warning_alerts,
                    "info_alerts": total_alerts - critical_alerts - warning_alerts
                },
                "recent_alerts": [{
                    "id": alert.id,
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "created_at": alert.created_at.isoformat()
                } for alert in recent_alerts],
                "assessment_time": datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Completed risk assessment for {entity_type}:{entity_id} - Score: {risk_score}")
            return assessment
            
        except Exception as e:
            self.logger.error(f"Error generating risk assessment: {str(e)}")
            raise
