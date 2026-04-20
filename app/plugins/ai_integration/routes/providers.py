"""
Routes for managing AI providers.

This module defines API endpoints for creating, retrieving, updating, and deleting 
AI service providers such as OpenAI, Azure OpenAI, Anthropic, etc.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.db import get_db
from app.core.security import get_current_user, get_current_active_user
from app.plugins.ai_integration.models import AIProvider, AIProviderType
from app.plugins.ai_integration.schemas import (
    AIProviderCreate, AIProviderUpdate, AIProviderResponse,
    AIProviderListResponse, BaseResponse
)

router = APIRouter(
    prefix="/providers"
)


@router.post("", response_model=AIProviderResponse)
async def create_ai_provider(
    provider: AIProviderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Create a new AI service provider configuration.
    
    **Requires admin permissions**
    """
    # Check if user has admin permission (simplified check)
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can create AI providers"
        )
    
    # If this provider is set as default, unset any existing defaults of same type
    if provider.is_default:
        existing_defaults = db.query(AIProvider).filter(
            AIProvider.provider_type == provider.provider_type,
            AIProvider.is_default == True
        ).all()
        
        for default_provider in existing_defaults:
            default_provider.is_default = False
            db.add(default_provider)
    
    # Create new provider
    try:
        db_provider = AIProvider(
            name=provider.name,
            provider_type=provider.provider_type,
            is_default=provider.is_default,
            is_active=provider.is_active,
            base_url=provider.base_url,
            config=provider.config,
            api_key=provider.api_key,
            api_secret=provider.api_secret
        )
        
        db.add(db_provider)
        db.commit()
        db.refresh(db_provider)
        return db_provider
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Provider with name '{provider.name}' already exists"
        )


@router.get("", response_model=AIProviderListResponse)
async def get_ai_providers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    provider_type: Optional[AIProviderType] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a list of AI service providers with optional filtering.
    """
    query = db.query(AIProvider)
    
    # Apply filters if provided
    if provider_type:
        query = query.filter(AIProvider.provider_type == provider_type)
    
    if is_active is not None:
        query = query.filter(AIProvider.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    providers = query.order_by(AIProvider.name).offset(skip).limit(limit).all()
    
    return {
        "success": True,
        "items": providers,
        "total": total
    }


@router.get("/{provider_id}", response_model=AIProviderResponse)
async def get_ai_provider(
    provider_id: int = Path(..., title="The ID of the AI provider to get"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific AI service provider.
    """
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"AI provider with ID {provider_id} not found"
        )
    
    return provider


@router.put("/{provider_id}", response_model=AIProviderResponse)
async def update_ai_provider(
    provider_id: int = Path(..., title="The ID of the AI provider to update"),
    provider_update: AIProviderUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Update an existing AI service provider configuration.
    
    **Requires admin permissions**
    """
    # Check if user has admin permission
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can update AI providers"
        )
    
    # Get existing provider
    db_provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    
    if not db_provider:
        raise HTTPException(
            status_code=404,
            detail=f"AI provider with ID {provider_id} not found"
        )
    
    # Handle setting as default
    if provider_update.is_default and provider_update.is_default != db_provider.is_default:
        # Unset any existing defaults of same type
        existing_defaults = db.query(AIProvider).filter(
            AIProvider.provider_type == db_provider.provider_type,
            AIProvider.is_default == True,
            AIProvider.id != provider_id
        ).all()
        
        for default_provider in existing_defaults:
            default_provider.is_default = False
            db.add(default_provider)
    
    # Update provider attributes
    update_data = provider_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_provider, key, value)
    
    try:
        db.add(db_provider)
        db.commit()
        db.refresh(db_provider)
        return db_provider
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Update failed. Provider name may already be in use."
        )


@router.delete("/{provider_id}", response_model=BaseResponse)
async def delete_ai_provider(
    provider_id: int = Path(..., title="The ID of the AI provider to delete"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete an AI service provider configuration.
    
    **Requires admin permissions**
    """
    # Check if user has admin permission
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can delete AI providers"
        )
    
    # Get existing provider
    db_provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    
    if not db_provider:
        raise HTTPException(
            status_code=404,
            detail=f"AI provider with ID {provider_id} not found"
        )
    
    try:
        db.delete(db_provider)
        db.commit()
        return {
            "success": True,
            "message": f"AI provider '{db_provider.name}' successfully deleted"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Unable to delete provider: {str(e)}"
        )
