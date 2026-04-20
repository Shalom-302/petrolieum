"""
Alert notifier service.

This module contains the AlertNotifier service responsible for sending
notifications about business alerts to various destinations such as
web interfaces, email, or mobile devices.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.plugins.business_alerts.models.alert import BusinessAlertDB

logger = logging.getLogger(__name__)


class AlertNotifier:
    """
    Service for sending notifications about business alerts.
    
    This service handles the delivery of alert notifications to various
    destinations including web interfaces, email, and potentially other
    channels like mobile push notifications.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the alert notifier service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def send_web_notifications(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Send notifications to web interface.
        
        This method retrieves active alerts and formats them for delivery
        to the web interface, typically via WebSockets.
        
        Args:
            user_id: Optional user ID to filter alerts by relevant user
            
        Returns:
            List[Dict[str, Any]]: List of formatted web notifications
        """
        # Build query to get active alerts
        query = self.db.query(BusinessAlertDB).filter(
            BusinessAlertDB.status == "active"
        )
        
        if user_id:
            # Filter alerts relevant to this user
            # This would typically join with a user-entity relationship table
            # to find entities the user has access to
            # For simplicity, this example doesn't implement full filtering
            pass
        
        # Execute the query
        alerts = query.all()
        
        # Format alerts for web interface
        # Ensure sensitive data is properly filtered out
        web_alerts = [{
            "id": alert.id,
            "message": alert.message,
            "severity": alert.severity,
            "entity_type": alert.entity_type,
            "entity_id": alert.entity_id,
            "alert_type": alert.alert_type,
            "created_at": alert.created_at.isoformat(),
        } for alert in alerts]
        
        # Log the notification action
        self.logger.info(f"Prepared {len(web_alerts)} web notifications" + 
                        (f" for user {user_id}" if user_id else ""))
        
        return web_alerts
        
    async def get_user_notifications(
        self, 
        user_id: str, 
        include_acknowledged: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get notifications for a specific user.
        
        Args:
            user_id: User ID to get notifications for
            include_acknowledged: Whether to include acknowledged alerts
            
        Returns:
            List[Dict[str, Any]]: List of notifications
        """
        # Build the query
        statuses = ["active"]
        if include_acknowledged:
            statuses.append("acknowledged")
            
        # In a real implementation, this would join with user permissions
        # to only show alerts for entities the user has access to
        # This is a simplified implementation
        query = self.db.query(BusinessAlertDB).filter(
            BusinessAlertDB.status.in_(statuses)
        )
        
        # Execute the query
        alerts = query.order_by(BusinessAlertDB.created_at.desc()).all()
        
        # Format the notifications
        notifications = [{
            "id": alert.id,
            "message": alert.message,
            "severity": alert.severity,
            "entity_type": alert.entity_type,
            "entity_id": alert.entity_id,
            "alert_type": alert.alert_type,
            "status": alert.status,
            "created_at": alert.created_at.isoformat(),
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None
        } for alert in alerts]
        
        self.logger.info(f"Retrieved {len(notifications)} notifications for user {user_id}")
        return notifications
    
    async def send_email_notifications(
        self, 
        recipient_email: str, 
        alerts: List[BusinessAlertDB]
    ) -> bool:
        """
        Send email notifications for alerts.
        
        Args:
            recipient_email: Email address to send notifications to
            alerts: List of alerts to include in the email
            
        Returns:
            bool: Success status
            
        Note:
            This is a placeholder implementation. In a real system, this would
            connect to an email service or message queue.
        """
        if not alerts:
            self.logger.info(f"No alerts to send to {recipient_email}")
            return True
            
        # Log the email notification attempt
        self.logger.info(f"Would send email with {len(alerts)} alerts to {recipient_email}")
        
        # In a real implementation, this would:
        # 1. Format the alerts into an email template
        # 2. Connect to an email service or message queue
        # 3. Send the email and handle errors
        
        return True
    
    async def send_push_notifications(
        self, 
        user_id: str, 
        alerts: List[BusinessAlertDB]
    ) -> Dict[str, Any]:
        """
        Send push notifications for alerts.
        
        Args:
            user_id: User ID to send notifications to
            alerts: List of alerts to send as push notifications
            
        Returns:
            Dict[str, Any]: Result of the push notification attempt
            
        Note:
            This is a placeholder implementation. In a real system, this would
            connect to a push notification service.
        """
        if not alerts:
            self.logger.info(f"No alerts to push to user {user_id}")
            return {"success": True, "sent": 0}
            
        # Log the push notification attempt
        self.logger.info(f"Would send {len(alerts)} push notifications to user {user_id}")
        
        # In a real implementation, this would:
        # 1. Format the alerts for the push notification service
        # 2. Connect to the push notification service
        # 3. Send the notifications and handle errors
        
        return {
            "success": True,
            "sent": len(alerts),
            "failed": 0
        }
    
    async def send_digest(
        self, 
        user_id: str, 
        time_period: str = "daily"
    ) -> Dict[str, Any]:
        """
        Send a digest of alerts for a specific time period.
        
        Args:
            user_id: User ID to send digest to
            time_period: Time period for the digest ("daily", "weekly")
            
        Returns:
            Dict[str, Any]: Result of the digest sending attempt
        """
        # Determine time window based on period
        if time_period == "daily":
            time_window = "24 hours"
            query_filter = "created_at >= NOW() - INTERVAL '1 day'"
        elif time_period == "weekly":
            time_window = "7 days"
            query_filter = "created_at >= NOW() - INTERVAL '7 day'"
        else:
            self.logger.warning(f"Invalid time period: {time_period}")
            return {"success": False, "error": "Invalid time period"}
            
        # Get alerts for the time period
        query = f"""
        SELECT 
            alert_type, 
            severity, 
            COUNT(*) as count
        FROM 
            business_alerts
        WHERE 
            {query_filter}
        GROUP BY 
            alert_type, severity
        ORDER BY 
            severity DESC, count DESC
        """
        
        try:
            results = self.db.execute(text(query)).fetchall()
            
            # Format the digest content
            digest_items = [{
                "alert_type": row.alert_type,
                "severity": row.severity,
                "count": row.count
            } for row in results]
            
            # Log the digest sending attempt
            self.logger.info(f"Would send {time_period} digest with {len(digest_items)} alert types to user {user_id}")
            
            # In a real implementation, this would:
            # 1. Format the digest into an email template
            # 2. Connect to an email service
            # 3. Send the email and handle errors
            
            return {
                "success": True,
                "time_period": time_period,
                "time_window": time_window,
                "alert_types": len(digest_items),
                "total_alerts": sum(item["count"] for item in digest_items)
            }
            
        except Exception as e:
            self.logger.error(f"Error preparing {time_period} digest: {str(e)}")
            return {"success": False, "error": str(e)}
