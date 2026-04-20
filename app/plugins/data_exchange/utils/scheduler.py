"""
Utility functions for scheduling import and export jobs.
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from sqlalchemy.orm import Session

from app.plugins.data_exchange.models import ImportExportSchedule, ImportExportJob, JobStatusType
from app.plugins.data_exchange.utils.background_tasks import process_import_job, process_export_job


# Set up logging
logger = logging.getLogger(__name__)

# Initialize the scheduler
scheduler = AsyncIOScheduler(
    jobstores={'default': MemoryJobStore()},
    job_defaults={'misfire_grace_time': 15*60}  # 15 minutes grace time
)


def start_scheduler():
    """Start the scheduler if it's not already running."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Data exchange scheduler started")


def shutdown_scheduler():
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Data exchange scheduler stopped")


def register_schedule(schedule_id: int, db: Session) -> bool:
    """
    Register a schedule in the scheduler.
    
    Args:
        schedule_id: ID of the schedule to register
        db: Database session
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get the schedule
        schedule = db.query(ImportExportSchedule).filter(
            ImportExportSchedule.id == schedule_id,
            ImportExportSchedule.is_active == True
        ).first()
        
        if not schedule:
            logger.error(f"Schedule {schedule_id} not found or not active")
            return False
        
        # Remove existing job if it exists
        job_id = f"data_exchange_schedule_{schedule_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # Set up the trigger based on the frequency
        trigger = get_trigger_for_schedule(schedule)
        
        if not trigger:
            logger.error(f"Invalid schedule configuration for schedule {schedule_id}")
            return False
        
        # Add the job to the scheduler
        scheduler.add_job(
            schedule_job_execution,
            trigger=trigger,
            id=job_id,
            name=f"Schedule {schedule.name}",
            args=[schedule_id, db],
            replace_existing=True
        )
        
        logger.info(f"Registered schedule {schedule_id}: {schedule.name}")
        
        # Make sure the scheduler is running
        start_scheduler()
        
        return True
    
    except Exception as e:
        logger.exception(f"Error registering schedule {schedule_id}: {str(e)}")
        return False


def update_schedule(schedule_id: int, db: Session) -> bool:
    """
    Update an existing schedule in the scheduler.
    
    Args:
        schedule_id: ID of the schedule to update
        db: Database session
        
    Returns:
        True if successful, False otherwise
    """
    # This is essentially the same as registering it
    return register_schedule(schedule_id, db)


def remove_schedule(schedule_id: int, db: Session) -> bool:
    """
    Remove a schedule from the scheduler.
    
    Args:
        schedule_id: ID of the schedule to remove
        db: Database session
        
    Returns:
        True if successful, False otherwise
    """
    try:
        job_id = f"data_exchange_schedule_{schedule_id}"
        
        # Remove the job if it exists
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"Removed schedule {schedule_id}")
            return True
        
        # Job doesn't exist
        logger.warning(f"Schedule {schedule_id} not found in scheduler")
        return False
    
    except Exception as e:
        logger.exception(f"Error removing schedule {schedule_id}: {str(e)}")
        return False


def get_trigger_for_schedule(schedule: ImportExportSchedule):
    """
    Create a trigger for a schedule based on its frequency.
    
    Args:
        schedule: The schedule to create a trigger for
        
    Returns:
        An APScheduler trigger
    """
    if schedule.frequency == "once":
        # One-time execution
        start_date = schedule.start_date or datetime.utcnow()
        return DateTrigger(run_date=start_date)
    
    elif schedule.frequency == "hourly":
        # Hourly execution
        interval = schedule.parameters.get("interval", 1)
        return IntervalTrigger(hours=interval)
    
    elif schedule.frequency == "daily":
        # Daily execution
        interval = schedule.parameters.get("interval", 1)
        hour = schedule.parameters.get("hour", 0)
        minute = schedule.parameters.get("minute", 0)
        return CronTrigger(
            day_of_week="*",
            hour=hour,
            minute=minute,
            start_date=schedule.start_date,
            end_date=schedule.end_date
        )
    
    elif schedule.frequency == "weekly":
        # Weekly execution
        day_of_week = schedule.parameters.get("day_of_week", 0)
        hour = schedule.parameters.get("hour", 0)
        minute = schedule.parameters.get("minute", 0)
        return CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            start_date=schedule.start_date,
            end_date=schedule.end_date
        )
    
    elif schedule.frequency == "monthly":
        # Monthly execution
        day = schedule.parameters.get("day", 1)
        hour = schedule.parameters.get("hour", 0)
        minute = schedule.parameters.get("minute", 0)
        return CronTrigger(
            day=day,
            hour=hour,
            minute=minute,
            start_date=schedule.start_date,
            end_date=schedule.end_date
        )
    
    elif schedule.frequency == "cron":
        # Custom cron expression
        if not schedule.cron_expression:
            logger.error(f"No cron expression provided for cron schedule {schedule.id}")
            return None
        
        try:
            return CronTrigger.from_crontab(
                schedule.cron_expression,
                start_date=schedule.start_date,
                end_date=schedule.end_date
            )
        except Exception as e:
            logger.error(f"Invalid cron expression '{schedule.cron_expression}': {str(e)}")
            return None
    
    else:
        logger.error(f"Unknown frequency '{schedule.frequency}' for schedule {schedule.id}")
        return None


async def schedule_job_execution(schedule_id: int, db: Session):
    """
    Execute a scheduled job.
    
    Args:
        schedule_id: ID of the schedule
        db: Database session
    """
    logger.info(f"Executing scheduled job for schedule {schedule_id}")
    
    try:
        # Get the schedule
        schedule = db.query(ImportExportSchedule).filter(
            ImportExportSchedule.id == schedule_id
        ).first()
        
        if not schedule:
            logger.error(f"Schedule {schedule_id} not found")
            return
        
        # Check if the schedule is still active
        if not schedule.is_active:
            logger.info(f"Schedule {schedule_id} is no longer active, removing job")
            remove_schedule(schedule_id, db)
            return
        
        # Create a new job record for this execution
        job = ImportExportJob(
            name=f"Scheduled: {schedule.name}",
            description=f"Job created by schedule {schedule.name} (ID: {schedule.id})",
            is_import=schedule.parameters.get("is_import", True),
            format_type=schedule.parameters.get("format_type"),
            source_path=schedule.parameters.get("source_path"),
            target_entity=schedule.parameters.get("target_entity"),
            configuration=schedule.parameters.get("configuration", {}),
            schedule_id=schedule.id,
            user_id=schedule.user_id,
            status=JobStatusType.PENDING,
            started_at=datetime.utcnow()
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Process the job based on its type
        if job.is_import:
            await process_import_job(job.id, db)
        else:
            await process_export_job(job.id, schedule.parameters.get("query_filters"), db)
        
        logger.info(f"Completed scheduled execution for schedule {schedule_id}, job {job.id}")
    
    except Exception as e:
        logger.exception(f"Error executing scheduled job for schedule {schedule_id}: {str(e)}")


def load_all_schedules(db: Session):
    """
    Load all active schedules from the database into the scheduler.
    
    Args:
        db: Database session
    """
    # Get all active schedules
    schedules = db.query(ImportExportSchedule).filter(
        ImportExportSchedule.is_active == True
    ).all()
    
    logger.info(f"Loading {len(schedules)} active schedules")
    
    # Register each schedule
    for schedule in schedules:
        register_schedule(schedule.id, db)
    
    # Start the scheduler if there are any schedules
    if schedules:
        start_scheduler()


def get_next_run_times(schedule_id: int, limit: int = 5) -> list:
    """
    Get the next scheduled run times for a job.
    
    Args:
        schedule_id: ID of the schedule
        limit: Maximum number of run times to return
        
    Returns:
        List of next run times as strings
    """
    job_id = f"data_exchange_schedule_{schedule_id}"
    job = scheduler.get_job(job_id)
    
    if not job:
        return []
    
    # Get the next run time
    next_run = job.next_run_time
    if not next_run:
        return []
    
    # For some triggers, we can calculate future run times
    run_times = [next_run]
    
    if isinstance(job.trigger, (CronTrigger, IntervalTrigger)):
        # Calculate additional run times for interval and cron triggers
        for _ in range(1, limit):
            try:
                # Get the next run time after the previous one
                next_time = job.trigger.get_next_fire_time(
                    run_times[-1], run_times[-1]
                )
                if next_time:
                    run_times.append(next_time)
                else:
                    break
            except Exception:
                break
    
    # Format the times as strings
    return [run_time.strftime("%Y-%m-%d %H:%M:%S") for run_time in run_times]
