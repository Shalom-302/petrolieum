"""
Routes for managing AI models.

This module defines API endpoints for creating, retrieving, updating, and deleting 
AI models from different providers such as GPT models, BERT models, etc.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_user
from app.plugins.ai_integration.models import AIModel, AIProvider, AIModelType
from app.plugins.ai_integration.schemas import (
    AIModelCreate, AIModelUpdate, AIModelResponse,
    AIModelListResponse, BaseResponse
)

router = APIRouter(
    prefix="/models"
)


@router.post("", response_model=AIModelResponse)
async def create_ai_model(
    model: AIModelCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Create a new AI model configuration.
    
    **Requires admin permissions**
    """
    # Check if user has admin permission (simplified check)
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can create AI models"
        )
    
    # Verify provider exists
    provider = db.query(AIProvider).filter(AIProvider.id == model.provider_id).first()
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider with ID {model.provider_id} not found"
        )
    
    # Create new model
    try:
        db_model = AIModel(
            provider_id=model.provider_id,
            name=model.name,
            model_type=model.model_type,
            model_id=model.model_id,
            version=model.version,
            capabilities=model.capabilities,
            default_params=model.default_params,
            max_tokens=model.max_tokens,
            is_active=model.is_active,
            cost_per_1k_tokens=model.cost_per_1k_tokens
        )
        
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        return db_model
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Model with ID '{model.model_id}' already exists for this provider"
        )


@router.get("", response_model=AIModelListResponse)
async def get_ai_models(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    provider_id: Optional[int] = None,
    model_type: Optional[AIModelType] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a list of AI models with optional filtering.
    """
    query = db.query(AIModel)
    
    # Apply filters if provided
    if provider_id:
        query = query.filter(AIModel.provider_id == provider_id)
    
    if model_type:
        query = query.filter(AIModel.model_type == model_type)
    
    if is_active is not None:
        query = query.filter(AIModel.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    models = query.order_by(AIModel.name).offset(skip).limit(limit).all()
    
    return {
        "success": True,
        "items": models,
        "total": total
    }


@router.get("/{model_id}", response_model=AIModelResponse)
async def get_ai_model(
    model_id: int = Path(..., title="The ID of the AI model to get"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific AI model.
    """
    model = db.query(AIModel).filter(AIModel.id == model_id).first()
    
    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"AI model with ID {model_id} not found"
        )
    
    return model


@router.put("/{model_id}", response_model=AIModelResponse)
async def update_ai_model(
    model_id: int = Path(..., title="The ID of the AI model to update"),
    model_update: AIModelUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Update an existing AI model configuration.
    
    **Requires admin permissions**
    """
    # Check if user has admin permission
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can update AI models"
        )
    
    # Get existing model
    db_model = db.query(AIModel).filter(AIModel.id == model_id).first()
    
    if not db_model:
        raise HTTPException(
            status_code=404,
            detail=f"AI model with ID {model_id} not found"
        )
    
    # Update model attributes
    update_data = model_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_model, key, value)
    
    try:
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        return db_model
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Update failed. Model ID may already be in use for this provider."
        )


@router.delete("/{model_id}", response_model=BaseResponse)
async def delete_ai_model(
    model_id: int = Path(..., title="The ID of the AI model to delete"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete an AI model configuration.
    
    **Requires admin permissions**
    """
    # Check if user has admin permission
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can delete AI models"
        )
    
    # Get existing model
    db_model = db.query(AIModel).filter(AIModel.id == model_id).first()
    
    if not db_model:
        raise HTTPException(
            status_code=404,
            detail=f"AI model with ID {model_id} not found"
        )
    
    try:
        db.delete(db_model)
        db.commit()
        return {
            "success": True,
            "message": f"AI model '{db_model.name}' successfully deleted"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Unable to delete model: {str(e)}"
        )
