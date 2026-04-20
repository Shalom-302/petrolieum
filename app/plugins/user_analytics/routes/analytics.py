"""
API routes for analytics and visualization features.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_admin_user
from ..schemas import HeatmapFilter, UserJourneyFilter
from ..services.event_service import EventService
from ..services.heatmap_service import HeatmapService
from ..models import AnalyticsUserSession, AnalyticsUserEvent
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/heatmap", response_model=Dict[str, Any])
async def generate_heatmap(
    filter_params: HeatmapFilter,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)  # Restricted to admins
):
    """
    Generates a heatmap visualization based on user interactions.
    
    This endpoint creates a visual representation of where users interact
    most frequently with the application interface.
    """
    event_service = EventService(db)
    heatmap_service = HeatmapService()
    
    # Get filtered data
    events = event_service.get_heatmap_data(filter_params)
    
    if not events:
        # Return empty data instead of 404 error
        return {"points": [], "message": "No events found matching the filter criteria"}
    
    # Generate the heatmap
    heatmap_data = heatmap_service.generate_heatmap(events)
    
    if not heatmap_data:
        raise HTTPException(status_code=500, detail="Error generating heatmap")
    
    return heatmap_data

@router.post("/component-heatmap/{component_name}")
async def generate_component_heatmap(
    component_name: str = Path(..., description="Name of the UI component to analyze"),
    filter_params: HeatmapFilter = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Generates a heatmap for a specific UI component.
    
    This endpoint provides a more focused view of how users interact
    with a particular component in the interface.
    """
    event_service = EventService(db)
    heatmap_service = HeatmapService()
    
    # Use empty filter if none provided
    if not filter_params:
        filter_params = HeatmapFilter()
    
    # Force the filter to the specified component
    filter_params.component_name = component_name
    
    # Get filtered data
    events = event_service.get_heatmap_data(filter_params)
    
    if not events:
        # Return empty data instead of 404 error
        return {"points": [], "message": "No events found for this component"}
    
    # Generate the component-specific heatmap
    heatmap_data = heatmap_service.generate_component_heatmap(events, component_name)
    
    if not heatmap_data:
        raise HTTPException(status_code=500, detail="Error generating component heatmap")
    
    return heatmap_data

@router.post("/user-journey")
async def get_user_journey(
    filter_params: UserJourneyFilter,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Retrieves a user's journey through the application.
    
    This endpoint provides a chronological sequence of user interactions
    to understand their navigation patterns and behavior.
    """
    event_service = EventService(db)
    
    # Get user journey data
    journey_data = event_service.get_user_journey(filter_params)
    
    if not journey_data:
        # Return empty data instead of 404 error
        return {
            "user_id": filter_params.user_id,
            "session_id": filter_params.session_id,
            "journey": [],
            "message": "No journey events found matching the criteria"
        }
    
    return {
        "user_id": filter_params.user_id,
        "session_id": filter_params.session_id,
        "journey": journey_data
    }

@router.get("/dashboard/overview")
async def get_analytics_overview(
    days: int = Query(7, description="Number of days to include in the overview"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Provides an overview of key analytics metrics.
    
    This endpoint returns summarized statistics like active users,
    popular pages, and interaction rates for a dashboard view.
    """
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get session counts
    total_sessions = db.query(AnalyticsUserSession).filter(
        AnalyticsUserSession.session_start >= start_date,
        AnalyticsUserSession.session_start <= end_date
    ).count()
    
    # Get event counts
    total_events = db.query(AnalyticsUserEvent).filter(
        AnalyticsUserEvent.timestamp >= start_date,
        AnalyticsUserEvent.timestamp <= end_date
    ).count()
    
    # Get unique user count
    unique_users = db.query(AnalyticsUserSession.user_id).filter(
        AnalyticsUserSession.session_start >= start_date,
        AnalyticsUserSession.session_start <= end_date,
        AnalyticsUserSession.user_id.isnot(None)
    ).distinct().count()
    
    # Get most common event types
    event_types = db.query(
        AnalyticsUserEvent.event_type,
        func.count(AnalyticsUserEvent.id).label("count")
    ).filter(
        AnalyticsUserEvent.timestamp >= start_date,
        AnalyticsUserEvent.timestamp <= end_date
    ).group_by(AnalyticsUserEvent.event_type).order_by(desc("count")).limit(5).all()
    
    # Get most visited pages
    top_pages = db.query(
        AnalyticsUserEvent.target_path,
        func.count(AnalyticsUserEvent.id).label("count")
    ).filter(
        AnalyticsUserEvent.timestamp >= start_date,
        AnalyticsUserEvent.timestamp <= end_date,
        AnalyticsUserEvent.target_path.isnot(None)
    ).group_by(AnalyticsUserEvent.target_path).order_by(desc("count")).limit(10).all()
    
    return {
        "time_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days
        },
        "metrics": {
            "total_sessions": total_sessions,
            "total_events": total_events,
            "unique_users": unique_users,
            "events_per_session": round(total_events / total_sessions, 2) if total_sessions > 0 else 0
        },
        "top_event_types": [{"type": t[0], "count": t[1]} for t in event_types],
        "top_pages": [{"path": p[0], "visits": p[1]} for p in top_pages]
    }
