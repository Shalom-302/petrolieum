"""
Routes for data import functionality.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, BackgroundTasks, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.data_exchange.models import (
    DataFormatType, ImportExportJob, ImportExportTemplate, JobStatusType
)
from app.plugins.data_exchange.schemas import (
    ImportDataRequest, DataImportResponse, DataImportPreviewResponse, 
    JobResponse, PaginatedResponse, DataValidationError
)
from app.plugins.data_exchange.utils.importers import (
    get_importer, detect_file_format, preview_import_data, validate_import_data
)
from app.plugins.data_exchange.utils.file_handlers import save_uploaded_file
from app.plugins.data_exchange.utils.background_tasks import process_import_job


router = APIRouter(prefix="/import")


@router.post("/", response_model=DataImportResponse)
async def import_data(
    background_tasks: BackgroundTasks,
    data: ImportDataRequest = None,
    file: UploadFile = File(None),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Import data from a file.
    
    This endpoint supports two methods:
    1. Upload a file directly
    2. Reference an existing job or template with a file path
    """
    # Initialize response
    response = DataImportResponse(success=False)
    
    try:
        # Case 1: File upload
        if file:
            # Save the uploaded file
            file_path = await save_uploaded_file(file, current_user.id)
            
            # Detect format if not provided
            format_type = data.format_type if data and data.format_type else detect_file_format(file_path)
            
            # Create a new job
            job = ImportExportJob(
                name=f"Import {file.filename}",
                description=f"Import from uploaded file {file.filename}",
                is_import=True,
                format_type=format_type,
                source_path=file_path,
                target_entity=data.target_entity if data and data.target_entity else "",
                configuration=data.configuration if data else {},
                template_id=data.template_id if data else None,
                user_id=current_user.id,
                status=JobStatusType.PENDING
            )
            
            db.add(job)
            db.commit()
            db.refresh(job)
            
        # Case 2: Reference existing job
        elif data and data.job_id:
            job = db.query(ImportExportJob).filter(
                ImportExportJob.id == data.job_id,
                ImportExportJob.user_id == current_user.id
            ).first()
            
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
                
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
            
        # Case 3: Create job from template
        elif data and data.template_id:
            template = db.query(ImportExportTemplate).filter(
                ImportExportTemplate.id == data.template_id,
                ImportExportTemplate.user_id == current_user.id
            ).first()
            
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
                
            job = ImportExportJob(
                name=f"Import from template {template.name}",
                description=f"Import using template {template.name}",
                is_import=True,
                format_type=template.format_type,
                source_path=data.file_path,
                target_entity=template.target_entity,
                configuration=template.configuration,
                template_id=template.id,
                user_id=current_user.id,
                status=JobStatusType.PENDING,
                started_at=datetime.utcnow()
            )
            
            db.add(job)
            db.commit()
            db.refresh(job)
            
        # Case 4: Create job from direct parameters
        elif data and data.file_path and data.format_type and data.target_entity:
            job = ImportExportJob(
                name=f"Import to {data.target_entity}",
                description=f"Import from {data.file_path} to {data.target_entity}",
                is_import=True,
                format_type=data.format_type,
                source_path=data.file_path,
                target_entity=data.target_entity,
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
                detail="Either file upload or job parameters are required"
            )
            
        # Check if validation only
        if data and data.validate_only:
            # Validate the data without importing
            validation_errors = validate_import_data(job.source_path, job.format_type, job.target_entity, job.configuration)
            
            # Update response with validation results
            response.success = len(validation_errors) == 0
            response.job_id = job.id
            response.validation_errors = validation_errors
            
        else:
            # Process the import job in the background
            background_tasks.add_task(
                process_import_job,
                job_id=job.id,
                db=db
            )
            
            # Update response
            response.success = True
            response.job_id = job.id
            
        return response
        
    except Exception as e:
        # Log the error and return error response
        print(f"Error in import_data: {str(e)}")
        response.error_message = str(e)
        return response


@router.post("/preview", response_model=DataImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    format_type: Optional[str] = Form(None),
    target_entity: str = Form(...),
    mapping_config: Optional[str] = Form(None),
    sample_size: int = Query(5, ge=1, le=20),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Preview data import by uploading a file and getting sample data with field mappings.
    Returns headers, sample data, detected types, and suggested mappings.
    """
    try:
        # Save the uploaded file temporarily
        file_path = await save_uploaded_file(file, current_user.id, is_temp=True)
        
        # Detect format if not provided
        if not format_type:
            format_type = detect_file_format(file_path)
            
        # Parse mapping configuration if provided
        config = {}
        if mapping_config:
            import json
            config = json.loads(mapping_config)
            
        # Preview the import data
        preview_result = preview_import_data(
            file_path=file_path,
            format_type=format_type,
            target_entity=target_entity,
            config=config,
            sample_size=sample_size
        )
        
        return preview_result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs", response_model=PaginatedResponse)
async def get_import_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    target_entity: Optional[str] = Query(None),
    format_type: Optional[str] = Query(None),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all import jobs for the current user."""
    # Base query
    query = db.query(ImportExportJob).filter(
        ImportExportJob.user_id == current_user.id,
        ImportExportJob.is_import == True
    )
    
    # Apply filters
    if status:
        query = query.filter(ImportExportJob.status == status)
    
    if target_entity:
        query = query.filter(ImportExportJob.target_entity == target_entity)
        
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
async def get_import_job(
    job_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific import job."""
    job = db.query(ImportExportJob).filter(
        ImportExportJob.id == job_id,
        ImportExportJob.user_id == current_user.id,
        ImportExportJob.is_import == True
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
        
    return job


@router.delete("/jobs/{job_id}", response_model=Dict[str, Any])
async def delete_import_job(
    job_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an import job."""
    job = db.query(ImportExportJob).filter(
        ImportExportJob.id == job_id,
        ImportExportJob.user_id == current_user.id,
        ImportExportJob.is_import == True
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
        
    # Cannot delete running jobs
    if job.status == JobStatusType.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete a running job")
        
    db.delete(job)
    db.commit()
    
    return {"success": True, "message": "Import job deleted successfully"}
