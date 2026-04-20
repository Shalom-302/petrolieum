"""
Routes for data export functionality.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, File, Form, Query, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.data_exchange.models import (
    DataFormatType, ImportExportJob, ImportExportTemplate, JobStatusType
)
from app.plugins.data_exchange.schemas import (
    ExportDataRequest, DataExportResponse, JobResponse, PaginatedResponse
)
from app.plugins.data_exchange.utils.exporters import (
    get_exporter, export_data_to_file, get_supported_export_entities
)
from app.plugins.data_exchange.utils.background_tasks import process_export_job


router = APIRouter(prefix="/export")


@router.post("/", response_model=DataExportResponse)
async def export_data(
    background_tasks: BackgroundTasks,
    data: ExportDataRequest,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Export data to a file.
    
    This endpoint supports two methods:
    1. Create a new export job with source entity and format settings
    2. Reference an existing job or template
    """
    # Initialize response
    response = DataExportResponse(success=False)
    
    try:
        # Case 1: Reference existing job
        if data.job_id:
            job = db.query(ImportExportJob).filter(
                ImportExportJob.id == data.job_id,
                ImportExportJob.user_id == current_user.id,
                ImportExportJob.is_import == False
            ).first()
            
            if not job:
                raise HTTPException(status_code=404, detail="Export job not found")
                
            # Update job status
            job.status = JobStatusType.PENDING
            job.started_at = datetime.utcnow()
            job.error_message = None
            job.records_processed = 0
            job.records_succeeded = 0
            job.records_failed = 0
            job.result_log = None
            
            db.add(job)
            db.commit()
            db.refresh(job)
            
        # Case 2: Create job from template
        elif data.template_id:
            template = db.query(ImportExportTemplate).filter(
                ImportExportTemplate.id == data.template_id,
                ImportExportTemplate.user_id == current_user.id,
                ImportExportTemplate.is_import == False
            ).first()
            
            if not template:
                raise HTTPException(status_code=404, detail="Export template not found")
                
            job = ImportExportJob(
                name=f"Export from template {template.name}",
                description=f"Export using template {template.name}",
                is_import=False,
                format_type=template.format_type,
                source_path=template.target_entity,  # For exports, source is the entity name
                target_entity=data.file_path or f"export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{template.format_type}",
                configuration=template.configuration,
                template_id=template.id,
                user_id=current_user.id,
                status=JobStatusType.PENDING,
                started_at=datetime.utcnow()
            )
            
            db.add(job)
            db.commit()
            db.refresh(job)
            
        # Case 3: Create job from direct parameters
        elif data.format_type and data.target_entity:
            # Default file path if not provided
            file_path = data.file_path or f"export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{data.format_type}"
            
            job = ImportExportJob(
                name=f"Export from {data.target_entity}",
                description=f"Export from {data.target_entity} to {file_path}",
                is_import=False,
                format_type=data.format_type,
                source_path=data.target_entity,  # Entity to export from
                target_entity=file_path,  # File to export to
                configuration=data.configuration or {},
                user_id=current_user.id,
                status=JobStatusType.PENDING,
                started_at=datetime.utcnow()
            )
            
            db.add(job)
            db.commit()
            db.refresh(job)
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either job_id, template_id, or format_type and target_entity are required"
            )
        
        # Process the export job in the background
        background_tasks.add_task(
            process_export_job,
            job_id=job.id,
            query_filters=data.query_filters,
            db=db
        )
        
        # Update response
        response.success = True
        response.job_id = job.id
        
        return response
        
    except Exception as e:
        # Log the error and return error response
        print(f"Error in export_data: {str(e)}")
        response.error_message = str(e)
        return response


@router.get("/download/{job_id}")
async def download_export_file(
    job_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Download a completed export file.
    """
    # Get the job
    job = db.query(ImportExportJob).filter(
        ImportExportJob.id == job_id,
        ImportExportJob.user_id == current_user.id,
        ImportExportJob.is_import == False
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
        
    # Check if the job is completed
    if job.status != JobStatusType.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export job is not completed. Current status: {job.status}"
        )
    
    # Return the file
    try:
        filename = job.target_entity.split('/')[-1]
        return FileResponse(
            path=job.target_entity,
            filename=filename,
            media_type=get_media_type(job.format_type)
        )
    except Exception as e:
        print(f"Error in download_export_file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error downloading the export file"
        )


@router.get("/jobs", response_model=PaginatedResponse)
async def get_export_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    source_entity: Optional[str] = Query(None),
    format_type: Optional[str] = Query(None),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all export jobs for the current user."""
    # Base query
    query = db.query(ImportExportJob).filter(
        ImportExportJob.user_id == current_user.id,
        ImportExportJob.is_import == False
    )
    
    # Apply filters
    if status:
        query = query.filter(ImportExportJob.status == status)
    
    if source_entity:
        query = query.filter(ImportExportJob.source_path == source_entity)
        
    if format_type:
        query = query.filter(ImportExportJob.format_type == format_type)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    query = query.order_by(ImportExportJob.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Get items
    items = query.all()
    
    # Create response
    response = PaginatedResponse(
        items=[JobResponse.from_orm(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
    
    return response


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_export_job(
    job_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific export job."""
    job = db.query(ImportExportJob).filter(
        ImportExportJob.id == job_id,
        ImportExportJob.user_id == current_user.id,
        ImportExportJob.is_import == False
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
        
    return job


@router.delete("/jobs/{job_id}", response_model=Dict[str, Any])
async def delete_export_job(
    job_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an export job."""
    job = db.query(ImportExportJob).filter(
        ImportExportJob.id == job_id,
        ImportExportJob.user_id == current_user.id,
        ImportExportJob.is_import == False
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
        
    # Cannot delete running jobs
    if job.status == JobStatusType.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete a running job")
        
    db.delete(job)
    db.commit()
    
    return {"success": True, "message": "Export job deleted successfully"}


@router.get("/entities", response_model=Dict[str, List[str]])
async def get_exportable_entities(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a list of entities that can be exported.
    """
    try:
        entities = get_supported_export_entities()
        return {"entities": entities}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting exportable entities: {str(e)}"
        )


def get_media_type(format_type: str) -> str:
    """Get the media type for a specific format."""
    media_types = {
        "csv": "text/csv",
        "json": "application/json",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xml": "application/xml"
    }
    return media_types.get(format_type.lower(), "application/octet-stream")
