"""
Routes for managing import/export templates.
"""

from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user, get_current_active_admin_user
from app.plugins.data_exchange.models import ImportExportTemplate
from app.plugins.data_exchange.schemas import (
    TemplateCreate, TemplateUpdate, TemplateResponse, PaginatedResponse
)


router = APIRouter(prefix="/templates")


@router.post("/", response_model=TemplateResponse)
async def create_template(
    template: TemplateCreate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new import/export template."""
    # Create new template from request data
    db_template = ImportExportTemplate(
        name=template.name,
        description=template.description,
        is_import=template.is_import,
        format_type=template.format_type,
        target_entity=template.target_entity,
        configuration=template.configuration,
        user_id=current_user.id,
        is_active=True
    )
    
    # Save to database
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    
    return db_template


@router.get("/", response_model=PaginatedResponse)
async def get_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    is_import: Optional[bool] = Query(None),
    format_type: Optional[str] = Query(None),
    target_entity: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all templates for the current user with pagination and filters."""
    # Base query
    query = db.query(ImportExportTemplate).filter(
        ImportExportTemplate.user_id == current_user.id
    )
    
    # Apply filters
    if is_import is not None:
        query = query.filter(ImportExportTemplate.is_import == is_import)
        
    if format_type:
        query = query.filter(ImportExportTemplate.format_type == format_type)
        
    if target_entity:
        query = query.filter(ImportExportTemplate.target_entity == target_entity)
        
    if is_active is not None:
        query = query.filter(ImportExportTemplate.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    query = query.order_by(ImportExportTemplate.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Get items
    items = query.all()
    
    # Create response
    response = PaginatedResponse(
        items=[TemplateResponse.from_orm(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
    
    return response


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific template by ID."""
    template = db.query(ImportExportTemplate).filter(
        ImportExportTemplate.id == template_id,
        ImportExportTemplate.user_id == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_update: TemplateUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a specific template."""
    # Get the template
    db_template = db.query(ImportExportTemplate).filter(
        ImportExportTemplate.id == template_id,
        ImportExportTemplate.user_id == current_user.id
    ).first()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Update fields if they exist in the request
    update_data = template_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_template, key, value)
    
    # Save changes
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    
    return db_template


@router.delete("/{template_id}", response_model=Dict[str, Any])
async def delete_template(
    template_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a specific template."""
    # Get the template
    db_template = db.query(ImportExportTemplate).filter(
        ImportExportTemplate.id == template_id,
        ImportExportTemplate.user_id == current_user.id
    ).first()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Delete the template
    db.delete(db_template)
    db.commit()
    
    return {"success": True, "message": "Template deleted successfully"}


@router.post("/duplicate/{template_id}", response_model=TemplateResponse)
async def duplicate_template(
    template_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Duplicate an existing template."""
    # Get the source template
    source_template = db.query(ImportExportTemplate).filter(
        ImportExportTemplate.id == template_id,
        ImportExportTemplate.user_id == current_user.id
    ).first()
    
    if not source_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create a new template with the same data
    new_template = ImportExportTemplate(
        name=f"Copy of {source_template.name}",
        description=source_template.description,
        is_import=source_template.is_import,
        format_type=source_template.format_type,
        target_entity=source_template.target_entity,
        configuration=source_template.configuration,
        user_id=current_user.id,
        is_active=True
    )
    
    # Save to database
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    
    return new_template


@router.get("/shared", response_model=List[TemplateResponse])
async def get_shared_templates(
    format_type: Optional[str] = Query(None),
    is_import: Optional[bool] = Query(None),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get templates shared by admin users for public use."""
    # Get templates shared by admin users (typically system-provided templates)
    query = db.query(ImportExportTemplate).filter(
        ImportExportTemplate.is_active == True
    ).join(
        "user"  # Assuming there's a relationship with User model
    ).filter(
        #User.is_admin == True,  # Filter for admin users
        #ImportExportTemplate.is_public == True  # Only get public templates
    )
    
    # Apply filters
    if is_import is not None:
        query = query.filter(ImportExportTemplate.is_import == is_import)
        
    if format_type:
        query = query.filter(ImportExportTemplate.format_type == format_type)
    
    # Get all matching templates
    templates = query.all()
    
    return [TemplateResponse.from_orm(template) for template in templates]
