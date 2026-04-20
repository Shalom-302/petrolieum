"""
Routes for tracking and reporting AI usage.

This module defines API endpoints for recording, retrieving, and reporting on
AI service usage across the application.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_user
from app.plugins.ai_integration.models import (
    AIUsageRecord, AIProvider, AIModel
)
from app.plugins.ai_integration.schemas import (
    AIUsageResponse, AIUsageStatistics, BaseResponse
)

router = APIRouter(
    prefix="/usage"
)


@router.get("", response_model=AIUsageResponse)
async def get_usage_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    provider_id: Optional[int] = Query(None, description="Filter by provider ID"),
    model_id: Optional[int] = Query(None, description="Filter by model ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    request_type: Optional[str] = Query(None, description="Filter by request type"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get AI usage records with optional filtering.
    
    **Requires admin permission for viewing all users' data**
    """
    # Check if requesting data for other users
    if user_id is not None and user_id != current_user.get("id") and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can view usage data for other users"
        )
    
    # Restrict non-admin users to their own usage
    if not current_user.get("is_admin", False):
        user_id = current_user.get("id")
    
    # Build query
    query = db.query(AIUsageRecord)
    
    # Apply filters
    if start_date:
        query = query.filter(AIUsageRecord.created_at >= start_date)
    
    if end_date:
        query = query.filter(AIUsageRecord.created_at <= end_date)
    
    if provider_id:
        query = query.filter(AIUsageRecord.provider_id == provider_id)
    
    if model_id:
        query = query.filter(AIUsageRecord.model_id == model_id)
    
    if user_id:
        query = query.filter(AIUsageRecord.user_id == user_id)
    
    if request_type:
        query = query.filter(AIUsageRecord.request_type == request_type)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    usage_records = query.order_by(desc(AIUsageRecord.created_at)).offset(skip).limit(limit).all()
    
    # Calculate total cost
    total_cost = 0.0
    for record in usage_records:
        if record.cost is not None:
            total_cost += record.cost
    
    return {
        "success": True,
        "items": usage_records,
        "total": total,
        "total_cost": total_cost
    }


@router.get("/statistics", response_model=AIUsageStatistics)
async def get_usage_statistics(
    period: str = Query("month", description="Statistics period: 'day', 'week', 'month', or 'year'"),
    start_date: Optional[datetime] = Query(None, description="Custom start date for statistics"),
    end_date: Optional[datetime] = Query(None, description="Custom end date for statistics"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get aggregated statistics on AI usage.
    
    **Requires admin permission for viewing all users' data**
    """
    # Check if requesting data for other users
    if user_id is not None and user_id != current_user.get("id") and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can view usage statistics for other users"
        )
    
    # Restrict non-admin users to their own usage
    if not current_user.get("is_admin", False):
        user_id = current_user.get("id")
    
    # Determine date range
    if start_date is None:
        today = datetime.now()
        if period == "day":
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "year":
            start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # Default to month
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    end_date = end_date or datetime.now()
    
    # Build base query
    query = db.query(AIUsageRecord).filter(
        AIUsageRecord.created_at >= start_date,
        AIUsageRecord.created_at <= end_date
    )
    
    if user_id:
        query = query.filter(AIUsageRecord.user_id == user_id)
    
    # Get total counts
    total_requests = query.count()
    total_tokens_result = db.query(func.sum(AIUsageRecord.total_tokens)).filter(
        AIUsageRecord.created_at >= start_date,
        AIUsageRecord.created_at <= end_date
    )
    
    if user_id:
        total_tokens_result = total_tokens_result.filter(AIUsageRecord.user_id == user_id)
    
    total_tokens = total_tokens_result.scalar() or 0
    
    # Calculate total cost
    total_cost_result = db.query(func.sum(AIUsageRecord.cost)).filter(
        AIUsageRecord.created_at >= start_date,
        AIUsageRecord.created_at <= end_date,
        AIUsageRecord.cost != None
    )
    
    if user_id:
        total_cost_result = total_cost_result.filter(AIUsageRecord.user_id == user_id)
    
    total_cost = total_cost_result.scalar() or 0.0
    
    # Get breakdown by model
    model_breakdown = {}
    model_stats = db.query(
        AIUsageRecord.model_id,
        func.count(AIUsageRecord.id).label("request_count"),
        func.sum(AIUsageRecord.total_tokens).label("token_count"),
        func.sum(AIUsageRecord.cost).label("total_cost")
    ).filter(
        AIUsageRecord.created_at >= start_date,
        AIUsageRecord.created_at <= end_date
    )
    
    if user_id:
        model_stats = model_stats.filter(AIUsageRecord.user_id == user_id)
    
    model_stats = model_stats.group_by(AIUsageRecord.model_id).all()
    
    for stat in model_stats:
        model = db.query(AIModel).filter(AIModel.id == stat.model_id).first()
        model_name = model.name if model else f"Unknown Model ({stat.model_id})"
        
        model_breakdown[model_name] = {
            "requests": stat.request_count,
            "tokens": stat.token_count or 0,
            "cost": stat.total_cost or 0.0
        }
    
    # Get breakdown by request type
    request_type_breakdown = {}
    request_type_stats = db.query(
        AIUsageRecord.request_type,
        func.count(AIUsageRecord.id).label("request_count"),
        func.sum(AIUsageRecord.total_tokens).label("token_count"),
        func.sum(AIUsageRecord.cost).label("total_cost")
    ).filter(
        AIUsageRecord.created_at >= start_date,
        AIUsageRecord.created_at <= end_date
    )
    
    if user_id:
        request_type_stats = request_type_stats.filter(AIUsageRecord.user_id == user_id)
    
    request_type_stats = request_type_stats.group_by(AIUsageRecord.request_type).all()
    
    for stat in request_type_stats:
        request_type = stat.request_type or "Unknown"
        
        request_type_breakdown[request_type] = {
            "requests": stat.request_count,
            "tokens": stat.token_count or 0,
            "cost": stat.total_cost or 0.0
        }
    
    # Get usage over time
    # For simplicity, group by day
    time_stats = db.query(
        func.date(AIUsageRecord.created_at).label("date"),
        func.count(AIUsageRecord.id).label("request_count"),
        func.sum(AIUsageRecord.total_tokens).label("token_count"),
        func.sum(AIUsageRecord.cost).label("total_cost")
    ).filter(
        AIUsageRecord.created_at >= start_date,
        AIUsageRecord.created_at <= end_date
    )
    
    if user_id:
        time_stats = time_stats.filter(AIUsageRecord.user_id == user_id)
    
    time_stats = time_stats.group_by(func.date(AIUsageRecord.created_at)).order_by("date").all()
    
    usage_over_time = []
    for stat in time_stats:
        usage_over_time.append({
            "date": stat.date.isoformat() if stat.date else None,
            "requests": stat.request_count,
            "tokens": stat.token_count or 0,
            "cost": stat.total_cost or 0.0
        })
    
    return {
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "breakdown_by_model": model_breakdown,
        "breakdown_by_request_type": request_type_breakdown,
        "usage_over_time": usage_over_time
    }


@router.delete("", response_model=BaseResponse)
async def clear_usage_records(
    start_date: Optional[datetime] = Query(None, description="Delete records from this date"),
    end_date: Optional[datetime] = Query(None, description="Delete records until this date"),
    provider_id: Optional[int] = Query(None, description="Delete records for this provider"),
    model_id: Optional[int] = Query(None, description="Delete records for this model"),
    user_id: Optional[int] = Query(None, description="Delete records for this user"),
    request_type: Optional[str] = Query(None, description="Delete records of this type"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete AI usage records with optional filtering.
    
    **Requires admin permission**
    """
    # Check admin permissions
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can delete usage records"
        )
    
    # Build query
    query = db.query(AIUsageRecord)
    
    # Apply filters
    if start_date:
        query = query.filter(AIUsageRecord.created_at >= start_date)
    
    if end_date:
        query = query.filter(AIUsageRecord.created_at <= end_date)
    
    if provider_id:
        query = query.filter(AIUsageRecord.provider_id == provider_id)
    
    if model_id:
        query = query.filter(AIUsageRecord.model_id == model_id)
    
    if user_id:
        query = query.filter(AIUsageRecord.user_id == user_id)
    
    if request_type:
        query = query.filter(AIUsageRecord.request_type == request_type)
    
    # Get count of records to delete
    count = query.count()
    
    if count == 0:
        return {
            "success": True,
            "message": "No matching records found to delete"
        }
    
    # Delete records
    query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "success": True,
        "message": f"Successfully deleted {count} usage records"
    }
