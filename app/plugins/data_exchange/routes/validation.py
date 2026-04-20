"""
Routes for managing data validation rules.
"""

from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_active_user
from app.plugins.data_exchange.models import ValidationRule
from app.plugins.data_exchange.schemas import (
    ValidationRuleCreate, ValidationRuleUpdate, ValidationRuleResponse, PaginatedResponse
)


router = APIRouter(prefix="/validation")


@router.post("/rules", response_model=ValidationRuleResponse)
async def create_validation_rule(
    rule: ValidationRuleCreate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new validation rule."""
    # Create new rule from request data
    db_rule = ValidationRule(
        name=rule.name,
        description=rule.description,
        rule_type=rule.rule_type,
        configuration=rule.configuration,
        field_name=rule.field_name,
        target_entity=rule.target_entity,
        user_id=current_user.id,
        is_active=True
    )
    
    # Save to database
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    return db_rule


@router.get("/rules", response_model=PaginatedResponse)
async def get_validation_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    target_entity: Optional[str] = Query(None),
    field_name: Optional[str] = Query(None),
    rule_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all validation rules for the current user with pagination and filters."""
    # Base query
    query = db.query(ValidationRule).filter(
        ValidationRule.user_id == current_user.id
    )
    
    # Apply filters
    if target_entity:
        query = query.filter(ValidationRule.target_entity == target_entity)
        
    if field_name:
        query = query.filter(ValidationRule.field_name == field_name)
        
    if rule_type:
        query = query.filter(ValidationRule.rule_type == rule_type)
        
    if is_active is not None:
        query = query.filter(ValidationRule.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    query = query.order_by(ValidationRule.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Get items
    items = query.all()
    
    # Create response
    response = PaginatedResponse(
        items=[ValidationRuleResponse.from_orm(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
    
    return response


@router.get("/rules/{rule_id}", response_model=ValidationRuleResponse)
async def get_validation_rule(
    rule_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific validation rule by ID."""
    rule = db.query(ValidationRule).filter(
        ValidationRule.id == rule_id,
        ValidationRule.user_id == current_user.id
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Validation rule not found")
        
    return rule


@router.put("/rules/{rule_id}", response_model=ValidationRuleResponse)
async def update_validation_rule(
    rule_id: int,
    rule_update: ValidationRuleUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a specific validation rule."""
    # Get the rule
    db_rule = db.query(ValidationRule).filter(
        ValidationRule.id == rule_id,
        ValidationRule.user_id == current_user.id
    ).first()
    
    if not db_rule:
        raise HTTPException(status_code=404, detail="Validation rule not found")
    
    # Update fields if they exist in the request
    update_data = rule_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rule, key, value)
    
    # Save changes
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    return db_rule


@router.delete("/rules/{rule_id}", response_model=Dict[str, Any])
async def delete_validation_rule(
    rule_id: int,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a specific validation rule."""
    # Get the rule
    db_rule = db.query(ValidationRule).filter(
        ValidationRule.id == rule_id,
        ValidationRule.user_id == current_user.id
    ).first()
    
    if not db_rule:
        raise HTTPException(status_code=404, detail="Validation rule not found")
    
    # Delete the rule
    db.delete(db_rule)
    db.commit()
    
    return {"success": True, "message": "Validation rule deleted successfully"}


@router.get("/rule-types", response_model=Dict[str, List[Dict[str, Any]]])
async def get_rule_types():
    """Get available validation rule types and their configurations."""
    rule_types = [
        {
            "type": "required",
            "description": "Field is required",
            "configuration_schema": {}
        },
        {
            "type": "regex",
            "description": "Field matches a regular expression pattern",
            "configuration_schema": {
                "pattern": "string",
                "error_message": "string"
            }
        },
        {
            "type": "range",
            "description": "Numeric value is within a range",
            "configuration_schema": {
                "min": "number",
                "max": "number",
                "error_message": "string"
            }
        },
        {
            "type": "enum",
            "description": "Value must be one of a predefined set",
            "configuration_schema": {
                "values": "array",
                "case_sensitive": "boolean",
                "error_message": "string"
            }
        },
        {
            "type": "date",
            "description": "Value is a valid date within a range",
            "configuration_schema": {
                "min_date": "date",
                "max_date": "date",
                "format": "string",
                "error_message": "string"
            }
        },
        {
            "type": "email",
            "description": "Value is a valid email address",
            "configuration_schema": {
                "error_message": "string"
            }
        },
        {
            "type": "url",
            "description": "Value is a valid URL",
            "configuration_schema": {
                "error_message": "string"
            }
        },
        {
            "type": "length",
            "description": "String length is within a range",
            "configuration_schema": {
                "min": "number",
                "max": "number",
                "error_message": "string"
            }
        },
        {
            "type": "unique",
            "description": "Value must be unique",
            "configuration_schema": {
                "error_message": "string"
            }
        },
        {
            "type": "custom",
            "description": "Custom validation rule with Python code",
            "configuration_schema": {
                "code": "string",
                "error_message": "string"
            }
        }
    ]
    
    return {"rule_types": rule_types}


@router.post("/validate", response_model=Dict[str, Any])
async def validate_data_sample(
    data: Dict[str, Any],
    target_entity: str = Query(...),
    field_name: str = Query(...),
    rule_id: Optional[int] = Query(None),
    rule_config: Optional[Dict[str, Any]] = None,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Validate a sample data value against a validation rule.
    Can either reference an existing rule or provide rule configuration directly.
    """
    # Case 1: Using an existing rule
    if rule_id:
        rule = db.query(ValidationRule).filter(
            ValidationRule.id == rule_id,
            ValidationRule.user_id == current_user.id
        ).first()
        
        if not rule:
            raise HTTPException(status_code=404, detail="Validation rule not found")
        
        # Use the rule to validate the data
        from app.plugins.data_exchange.utils.validators import validate_with_rule
        is_valid, error_message = validate_with_rule(data, rule)
        
    # Case 2: Using provided rule configuration
    elif rule_config:
        from app.plugins.data_exchange.utils.validators import validate_with_config
        is_valid, error_message = validate_with_config(data, rule_config)
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either rule_id or rule_config is required"
        )
    
    return {
        "is_valid": is_valid,
        "error_message": error_message if not is_valid else None
    }
