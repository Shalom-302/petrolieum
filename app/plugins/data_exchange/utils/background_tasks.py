"""
Background tasks for processing import and export jobs.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.plugins.data_exchange.models import ImportExportJob, JobStatusType
from app.plugins.data_exchange.utils.importers import import_data_to_db, validate_import_data
from app.plugins.data_exchange.utils.exporters import export_data_to_file, get_entity_data


logger = logging.getLogger(__name__)


async def process_import_job(job_id: int, db: Session) -> None:
    """
    Process an import job asynchronously.
    
    Args:
        job_id: ID of the import job to process
        db: Database session
    """
    # Get the job
    job = db.query(ImportExportJob).filter(
        ImportExportJob.id == job_id,
        ImportExportJob.is_import == True
    ).first()
    
    if not job:
        logger.error(f"Import job {job_id} not found")
        return
    
    try:
        # Update job status
        job.status = JobStatusType.RUNNING
        job.started_at = datetime.utcnow()
        db.add(job)
        db.commit()
        
        # Validate the data first
        validation_errors = validate_import_data(
            job.source_path,
            job.format_type,
            job.target_entity,
            job.configuration
        )
        
        # If there are validation errors, fail the job
        if validation_errors:
            error_summary = "\n".join([
                f"Row {error.row_index}, Field '{error.field_name}': {error.error_message}"
                for error in validation_errors[:10]  # Limit to first 10 errors
            ])
            
            # If there are more errors, add a note
            if len(validation_errors) > 10:
                error_summary += f"\n...and {len(validation_errors) - 10} more errors"
            
            job.status = JobStatusType.FAILED
            job.error_message = f"Validation failed with {len(validation_errors)} errors: \n{error_summary}"
            job.completed_at = datetime.utcnow()
            db.add(job)
            db.commit()
            return
        
        # Import the data
        import_stats = import_data_to_db(
            job.source_path,
            job.format_type,
            job.target_entity,
            job.configuration,
            db
        )
        
        # Update job with results
        job.records_processed = import_stats["total"]
        job.records_succeeded = import_stats["success"]
        job.records_failed = import_stats["error"]
        
        # Process completed successfully
        if import_stats["error"] == 0:
            job.status = JobStatusType.COMPLETED
            job.result_log = f"Successfully imported {import_stats['success']} records."
        else:
            # Some records failed
            job.status = JobStatusType.COMPLETED_WITH_ERRORS
            
            # Store the first few errors in the result log
            error_log = []
            for i, error in enumerate(import_stats["errors"][:5]):
                error_log.append(f"Row {error['row_index']}: {error['error']}")
            
            if len(import_stats["errors"]) > 5:
                error_log.append(f"...and {len(import_stats['errors']) - 5} more errors")
            
            job.result_log = "\n".join([
                f"Imported {import_stats['success']} records successfully.",
                f"Failed to import {import_stats['error']} records.",
                "Sample errors:",
                *error_log
            ])
        
        job.completed_at = datetime.utcnow()
        db.add(job)
        db.commit()
        
    except Exception as e:
        logger.exception(f"Error processing import job {job_id}: {str(e)}")
        
        # Update job status to failed
        job.status = JobStatusType.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        db.add(job)
        db.commit()


async def process_export_job(
    job_id: int, 
    query_filters: Optional[Dict[str, Any]] = None,
    db: Session = None
) -> None:
    """
    Process an export job asynchronously.
    
    Args:
        job_id: ID of the export job to process
        query_filters: Optional filters to apply to the data query
        db: Database session
    """
    # Get the job
    job = db.query(ImportExportJob).filter(
        ImportExportJob.id == job_id,
        ImportExportJob.is_import == False
    ).first()
    
    if not job:
        logger.error(f"Export job {job_id} not found")
        return
    
    try:
        # Update job status
        job.status = JobStatusType.RUNNING
        job.started_at = datetime.utcnow()
        db.add(job)
        db.commit()
        
        # Get the data from the source entity
        data = get_entity_data(
            job.source_path,
            query_filters,
            db
        )
        
        # Update records processed count
        job.records_processed = len(data)
        
        # Export the data to a file
        export_file_path = export_data_to_file(
            data,
            job.format_type,
            job.target_entity,
            job.configuration
        )
        
        # Update job with results
        job.records_succeeded = len(data)
        job.records_failed = 0
        job.status = JobStatusType.COMPLETED
        job.result_log = f"Successfully exported {len(data)} records to {export_file_path}."
        job.completed_at = datetime.utcnow()
        
        db.add(job)
        db.commit()
        
    except Exception as e:
        logger.exception(f"Error processing export job {job_id}: {str(e)}")
        
        # Update job status to failed
        job.status = JobStatusType.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        db.add(job)
        db.commit()


async def retry_job(job_id: int, db: Session) -> None:
    """
    Retry a failed import or export job.
    
    Args:
        job_id: ID of the job to retry
        db: Database session
    """
    # Get the job
    job = db.query(ImportExportJob).get(job_id)
    
    if not job:
        logger.error(f"Job {job_id} not found")
        return
    
    # Can only retry failed jobs
    if job.status not in [JobStatusType.FAILED, JobStatusType.COMPLETED_WITH_ERRORS]:
        logger.error(f"Cannot retry job {job_id} with status {job.status}")
        return
    
    # Reset job stats
    job.status = JobStatusType.PENDING
    job.started_at = datetime.utcnow()
    job.completed_at = None
    job.error_message = None
    job.records_processed = 0
    job.records_succeeded = 0
    job.records_failed = 0
    job.result_log = None
    
    db.add(job)
    db.commit()
    
    # Process the job
    if job.is_import:
        await process_import_job(job_id, db)
    else:
        await process_export_job(job_id, {}, db)
