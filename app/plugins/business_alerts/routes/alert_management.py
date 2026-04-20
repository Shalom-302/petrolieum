"""
Alert management routes.

This module provides API endpoints for managing business alerts,
including listing, creating, updating, and acknowledging alerts.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.core.rate_limit import rate_limit
from app.plugins.business_alerts.models.alert import BusinessAlertDB
from app.plugins.business_alerts.schemas.alert import (
    AlertResponse,
    AlertCreate,
    AlertUpdate,
    PaginatedAlertResponse
)
from app.plugins.business_alerts.services.detector import AlertDetector

logger = logging.getLogger(__name__)


def get_alert_management_router():
    """
    Create and return a router for alert management endpoints.
    
    This function initializes an APIRouter with various endpoints for
    managing business alerts, including CRUD operations and alert
    acknowledgment functionality.
    
    Returns:
        APIRouter: FastAPI router with alert management endpoints
    """
    router = APIRouter()
    
    @router.get(
        "",
        response_model=PaginatedAlertResponse,
        summary="List business alerts",
        description="List business alerts with optional filtering"
    )
    @rate_limit(limit_per_minute=20)
    async def list_alerts(
        status: Optional[str] = Query(None, description="Filter by status"),
        severity: Optional[str] = Query(None, description="Filter by severity"),
        entity_type: Optional[str] = Query(None, description="Filter by entity type"),
        alert_type: Optional[str] = Query(None, description="Filter by alert type"),
        entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Page size"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        List business alerts with optional filtering.
        
        Args:
            status: Filter by alert status (active, acknowledged, resolved)
            severity: Filter by alert severity (critical, warning, info)
            entity_type: Filter by entity type (company, user, etc.)
            alert_type: Filter by alert type (missing_financial_data, etc.)
            entity_id: Filter by specific entity ID
            page: Page number for pagination
            page_size: Number of items per page
            db: Database session
            current_user_id: ID of the current authenticated user
            
        Returns:
            PaginatedAlertResponse: Paginated list of alerts
        """
        # Build query with filters
        query = db.query(BusinessAlertDB)
        
        if status:
            query = query.filter(BusinessAlertDB.status == status)
        if severity:
            query = query.filter(BusinessAlertDB.severity == severity)
        if entity_type:
            query = query.filter(BusinessAlertDB.entity_type == entity_type)
        if alert_type:
            query = query.filter(BusinessAlertDB.alert_type == alert_type)
        if entity_id:
            query = query.filter(BusinessAlertDB.entity_id == entity_id)
            
        # Apply pagination
        total = query.count()
        alerts = query.order_by(BusinessAlertDB.created_at.desc()) \
                     .offset((page-1) * page_size) \
                     .limit(page_size) \
                     .all()
        
        # Log the action
        logger.info(f"User {current_user_id} retrieved {len(alerts)} alerts (filtered by: status={status}, severity={severity})")
        
        return {
            "items": alerts,
            "total": total,
            "page": page,
            "size": page_size
        }
    
    @router.get(
        "/{alert_id}",
        response_model=AlertResponse,
        summary="Get alert details",
        description="Get details of a specific business alert"
    )
    @rate_limit(limit_per_minute=30)
    async def get_alert(
        alert_id: str = Path(..., description="Alert ID"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Get details of a specific business alert.
        
        Args:
            alert_id: ID of the alert to retrieve
            db: Database session
            current_user_id: ID of the current authenticated user
            
        Returns:
            AlertResponse: Alert details
            
        Raises:
            HTTPException: If alert not found
        """
        alert = db.query(BusinessAlertDB).filter(BusinessAlertDB.id == alert_id).first()
        if not alert:
            logger.warning(f"User {current_user_id} attempted to access non-existent alert {alert_id}")
            raise HTTPException(status_code=404, detail="Alert not found")
        
        logger.info(f"User {current_user_id} accessed alert {alert_id}")
        return alert
    
    @router.post(
        "",
        response_model=AlertResponse,
        summary="Create alert",
        description="Create a new business alert"
    )
    @rate_limit(limit_per_minute=10)
    async def create_alert(
        alert: AlertCreate,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Create a new business alert.
        
        Args:
            alert: Alert data
            db: Database session
            current_user_id: ID of the current authenticated user
            
        Returns:
            AlertResponse: Created alert
        """
        # Create new alert
        db_alert = BusinessAlertDB(
            entity_type=alert.entity_type,
            entity_id=alert.entity_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            message=alert.message,
            details=alert.details,
            status=alert.status
        )
        
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)
        
        logger.info(f"User {current_user_id} created alert {db_alert.id} for {alert.entity_type}:{alert.entity_id}")
        return db_alert
    
    @router.patch(
        "/{alert_id}/acknowledge",
        response_model=AlertResponse,
        summary="Acknowledge alert",
        description="Mark an alert as acknowledged"
    )
    @rate_limit(limit_per_minute=10)
    async def acknowledge_alert(
        alert_id: str = Path(..., description="Alert ID"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Mark an alert as acknowledged.
        
        Args:
            alert_id: ID of the alert to acknowledge
            db: Database session
            current_user_id: ID of the current authenticated user
            
        Returns:
            AlertResponse: Updated alert
            
        Raises:
            HTTPException: If alert not found or already acknowledged
        """
        alert = db.query(BusinessAlertDB).filter(BusinessAlertDB.id == alert_id).first()
        if not alert:
            logger.warning(f"User {current_user_id} attempted to acknowledge non-existent alert {alert_id}")
            raise HTTPException(status_code=404, detail="Alert not found")
            
        if alert.status == "acknowledged":
            logger.info(f"User {current_user_id} attempted to acknowledge already acknowledged alert {alert_id}")
            raise HTTPException(status_code=400, detail="Alert already acknowledged")
            
        if alert.status == "resolved":
            logger.info(f"User {current_user_id} attempted to acknowledge resolved alert {alert_id}")
            raise HTTPException(status_code=400, detail="Cannot acknowledge resolved alert")
            
        # Update alert status
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = current_user_id
        
        db.commit()
        db.refresh(alert)
        
        logger.info(f"Alert {alert_id} acknowledged by user {current_user_id}")
        return alert
    
    @router.patch(
        "/{alert_id}/resolve",
        response_model=AlertResponse,
        summary="Resolve alert",
        description="Mark an alert as resolved"
    )
    @rate_limit(limit_per_minute=10)
    async def resolve_alert(
        alert_id: str = Path(..., description="Alert ID"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Mark an alert as resolved.
        
        Args:
            alert_id: ID of the alert to resolve
            db: Database session
            current_user_id: ID of the current authenticated user
            
        Returns:
            AlertResponse: Updated alert
            
        Raises:
            HTTPException: If alert not found or already resolved
        """
        alert = db.query(BusinessAlertDB).filter(BusinessAlertDB.id == alert_id).first()
        if not alert:
            logger.warning(f"User {current_user_id} attempted to resolve non-existent alert {alert_id}")
            raise HTTPException(status_code=404, detail="Alert not found")
            
        if alert.status == "resolved":
            logger.info(f"User {current_user_id} attempted to resolve already resolved alert {alert_id}")
            raise HTTPException(status_code=400, detail="Alert already resolved")
            
        # Update alert status
        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()
        
        db.commit()
        db.refresh(alert)
        
        logger.info(f"Alert {alert_id} resolved by user {current_user_id}")
        return alert
    
    @router.delete(
        "/{alert_id}",
        response_model=dict,
        summary="Delete alert",
        description="Delete a business alert"
    )
    @rate_limit(limit_per_minute=5)
    async def delete_alert(
        alert_id: str = Path(..., description="Alert ID"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Delete a business alert.
        
        Args:
            alert_id: ID of the alert to delete
            db: Database session
            current_user_id: ID of the current authenticated user
            
        Returns:
            dict: Operation result
            
        Raises:
            HTTPException: If alert not found
        """
        alert = db.query(BusinessAlertDB).filter(BusinessAlertDB.id == alert_id).first()
        if not alert:
            logger.warning(f"User {current_user_id} attempted to delete non-existent alert {alert_id}")
            raise HTTPException(status_code=404, detail="Alert not found")
            
        db.delete(alert)
        db.commit()
        
        logger.info(f"Alert {alert_id} deleted by user {current_user_id}")
        return {"status": "success", "message": "Alert deleted successfully"}
    
    return router
