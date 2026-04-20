"""
Routes for managing scheduled imports and exports.
"""

from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.data_exchange.models import ImportExportSchedule, ImportExportJob
from app.plugins.data_exchange.schemas import (
    ScheduleCreate, ScheduleUpdate, ScheduleResponse, PaginatedResponse
)
from app.plugins.data_exchange.utils.scheduler import (
    register_schedule, update_schedule, remove_schedule
)


router = APIRouter(prefix="/schedules")


@router.post("/", response_model=ScheduleResponse)
async def create_schedule(
    background_tasks: BackgroundTasks,
    schedule: ScheduleCreate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new import/export schedule."""
    # Create new schedule from request data
    db_schedule = ImportExportSchedule(
        name=schedule.name,
        description=schedule.description,
        frequency=schedule.frequency,
        start_date=schedule.start_date,
        end_date=schedule.end_date,
        cron_expression=schedule.cron_expression,
        parameters=schedule.parameters.dict() if schedule.parameters else {},
        user_id=current_user.id,
        is_active=True
    )
    
    # Save to database
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    
    # Register the schedule in the scheduler
    background_tasks.add_task(
        register_schedule,
        schedule_id=db_schedule.id,
        db=db
    )
    
    return db_schedule


@router.get("/", response_model=PaginatedResponse)
async def get_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    frequency: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all schedules for the current user with pagination and filters."""
    # Base query
    query = db.query(ImportExportSchedule).filter(
        ImportExportSchedule.user_id == current_user.id
    )
    
    # Apply filters
    if frequency:
        query = query.filter(ImportExportSchedule.frequency == frequency)
        
    if is_active is not None:
        query = query.filter(ImportExportSchedule.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    query = query.order_by(ImportExportSchedule.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Get items
    items = query.all()
    
    # Create response
    response = PaginatedResponse(
        items=[ScheduleResponse.from_orm(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
    
    return response


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific schedule by ID."""
    schedule = db.query(ImportExportSchedule).filter(
        ImportExportSchedule.id == schedule_id,
        ImportExportSchedule.user_id == current_user.id
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule_route(
    background_tasks: BackgroundTasks,
    schedule_id: int,
    schedule_update: ScheduleUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a specific schedule."""
    # Get the schedule
    db_schedule = db.query(ImportExportSchedule).filter(
        ImportExportSchedule.id == schedule_id,
        ImportExportSchedule.user_id == current_user.id
    ).first()
    
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Update fields if they exist in the request
    update_data = schedule_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_schedule, key, value)
    
    # Save changes
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    
    # Update the schedule in the scheduler
    background_tasks.add_task(
        update_schedule,
        schedule_id=db_schedule.id,
        db=db
    )
    
    return db_schedule


@router.delete("/{schedule_id}", response_model=Dict[str, Any])
async def delete_schedule(
    background_tasks: BackgroundTasks,
    schedule_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a specific schedule."""
    # Get the schedule
    db_schedule = db.query(ImportExportSchedule).filter(
        ImportExportSchedule.id == schedule_id,
        ImportExportSchedule.user_id == current_user.id
    ).first()
    
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Remove from scheduler
    background_tasks.add_task(
        remove_schedule,
        schedule_id=db_schedule.id,
        db=db
    )
    
    # Delete the schedule
    db.delete(db_schedule)
    db.commit()
    
    return {"success": True, "message": "Schedule deleted successfully"}


@router.post("/{schedule_id}/activate", response_model=ScheduleResponse)
async def activate_schedule(
    background_tasks: BackgroundTasks,
    schedule_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Activate a specific schedule."""
    # Get the schedule
    db_schedule = db.query(ImportExportSchedule).filter(
        ImportExportSchedule.id == schedule_id,
        ImportExportSchedule.user_id == current_user.id
    ).first()
    
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Activate the schedule
    db_schedule.is_active = True
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    
    # Register the schedule in the scheduler
    background_tasks.add_task(
        register_schedule,
        schedule_id=db_schedule.id,
        db=db
    )
    
    return db_schedule


@router.post("/{schedule_id}/deactivate", response_model=ScheduleResponse)
async def deactivate_schedule(
    background_tasks: BackgroundTasks,
    schedule_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deactivate a specific schedule."""
    # Get the schedule
    db_schedule = db.query(ImportExportSchedule).filter(
        ImportExportSchedule.id == schedule_id,
        ImportExportSchedule.user_id == current_user.id
    ).first()
    
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Deactivate the schedule
    db_schedule.is_active = False
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    
    # Remove from scheduler
    background_tasks.add_task(
        remove_schedule,
        schedule_id=db_schedule.id,
        db=db
    )
    
    return db_schedule


@router.get("/{schedule_id}/jobs", response_model=PaginatedResponse)
async def get_schedule_jobs(
    schedule_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all jobs associated with a specific schedule."""
    # Verify schedule exists and belongs to the user
    schedule = db.query(ImportExportSchedule).filter(
        ImportExportSchedule.id == schedule_id,
        ImportExportSchedule.user_id == current_user.id
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Get jobs associated with this schedule
    query = db.query(ImportExportJob).filter(
        ImportExportJob.schedule_id == schedule_id
    )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    query = query.order_by(ImportExportJob.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Get items
    items = query.all()
    
    # Create response
    from app.plugins.data_exchange.schemas import JobResponse
    response = PaginatedResponse(
        items=[JobResponse.from_orm(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
    
    return response
