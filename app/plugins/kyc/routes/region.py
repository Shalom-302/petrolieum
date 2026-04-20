"""
Routes for managing KYC region configurations.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_admin_token, get_current_user_id
from app.plugins.api_gateway.utils import rate_limit

from ..models.region import KycRegionDB, InfrastructureLevel
from ..schemas.region import (
    RegionCreate, RegionUpdate, RegionResponse, 
    RegionList, InfrastructureLevelEnum
)
from ..utils.region_detector import detect_region, get_region_requirements
from ..utils.security import kyc_security

logger = logging.getLogger(__name__)


def get_region_router() -> APIRouter:
    """
    Get the region configuration router.
    
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    @router.post(
        "",
        response_model=RegionResponse,
        status_code=201,
        summary="Create a new KYC region configuration",
        description="Create a new KYC region configuration (admin only)"
    )
    @rate_limit(limit_per_minute=5)
    async def create_region(
        region: RegionCreate,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Create a new KYC region configuration (admin only)."""
        # Verify admin permissions
        try:
            verify_admin_token(current_user_id)
        except:
            # Log unauthorized access attempt
            kyc_security.log_security_event(
                event_type="kyc_region_unauthorized_create",
                user_id=current_user_id,
                action="create_region",
                success=False,
                metadata={}
            )
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Check if region already exists
        existing_region = db.query(KycRegionDB).filter(
            KycRegionDB.country_code == region.country_code
        ).first()
        
        if existing_region:
            raise HTTPException(
                status_code=400, 
                detail=f"Region already exists for country code: {region.country_code}"
            )
        
        # Create new region
        new_region = KycRegionDB(
            name=region.name,
            country_code=region.country_code,
            infrastructure_level=InfrastructureLevel(region.infrastructure_level),
            required_documents=region.required_documents,
            simplified_kyc_enabled=region.simplified_kyc_enabled,
            simplified_requirements=region.simplified_requirements,
            verification_expiry_days=region.verification_expiry_days,
            simplified_kyc_threshold=region.simplified_kyc_threshold,
            trusted_referee_types=region.trusted_referee_types
        )
        
        db.add(new_region)
        db.commit()
        db.refresh(new_region)
        
        # Log successful creation
        kyc_security.log_security_event(
            event_type="kyc_region_created",
            user_id=current_user_id,
            action="create_region",
            success=True,
            metadata={
                "region_id": new_region.id,
                "country_code": new_region.country_code
            }
        )
        
        return new_region
    
    @router.get(
        "/{region_id}",
        response_model=RegionResponse,
        summary="Get region configuration",
        description="Get a KYC region configuration by ID"
    )
    @rate_limit(limit_per_minute=20)
    async def get_region(
        region_id: str = Path(..., description="Region ID"),
        db: Session = Depends(get_db)
    ):
        """Get a KYC region configuration by ID."""
        region = db.query(KycRegionDB).filter(
            KycRegionDB.id == region_id
        ).first()
        
        if not region:
            raise HTTPException(status_code=404, detail="Region not found")
        
        return region
    
    @router.get(
        "/country/{country_code}",
        response_model=RegionResponse,
        summary="Get region by country code",
        description="Get a KYC region configuration by country code"
    )
    @rate_limit(limit_per_minute=20)
    async def get_region_by_country(
        country_code: str = Path(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"),
        db: Session = Depends(get_db)
    ):
        """Get a KYC region configuration by country code."""
        region = detect_region(db, country_code=country_code)
        
        if not region:
            raise HTTPException(
                status_code=404, 
                detail=f"Region not configured for country code: {country_code}"
            )
        
        return region
    
    @router.get(
        "",
        response_model=RegionList,
        summary="List region configurations",
        description="List KYC region configurations with optional filtering"
    )
    @rate_limit(limit_per_minute=10)
    async def list_regions(
        infrastructure_level: Optional[str] = Query(None, description="Filter by infrastructure level"),
        simplified_kyc_enabled: Optional[bool] = Query(None, description="Filter by simplified KYC availability"),
        page: int = Query(1, description="Page number", ge=1),
        size: int = Query(20, description="Page size", ge=1, le=100),
        db: Session = Depends(get_db)
    ):
        """List KYC region configurations with pagination and filtering."""
        # Query regions
        query = db.query(KycRegionDB)
        
        if infrastructure_level:
            try:
                level_enum = InfrastructureLevel(infrastructure_level)
                query = query.filter(KycRegionDB.infrastructure_level == level_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid infrastructure level: {infrastructure_level}")
        
        if simplified_kyc_enabled is not None:
            query = query.filter(KycRegionDB.simplified_kyc_enabled == simplified_kyc_enabled)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        regions = query.order_by(KycRegionDB.name) \
            .offset((page - 1) * size) \
            .limit(size) \
            .all()
        
        return {
            "items": regions,
            "total": total,
            "page": page,
            "size": size
        }
    
    @router.put(
        "/{region_id}",
        response_model=RegionResponse,
        summary="Update region configuration",
        description="Update a KYC region configuration (admin only)"
    )
    @rate_limit(limit_per_minute=5)
    async def update_region(
        region_update: RegionUpdate,
        region_id: str = Path(..., description="Region ID"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Update a KYC region configuration (admin only)."""
        # Verify admin permissions
        try:
            verify_admin_token(current_user_id)
        except:
            # Log unauthorized access attempt
            kyc_security.log_security_event(
                event_type="kyc_region_unauthorized_update",
                user_id=current_user_id,
                action="update_region",
                success=False,
                metadata={"region_id": region_id}
            )
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Get existing region
        region = db.query(KycRegionDB).filter(
            KycRegionDB.id == region_id
        ).first()
        
        if not region:
            raise HTTPException(status_code=404, detail="Region not found")
        
        # Update region
        update_data = region_update.dict(exclude_unset=True)
        
        # Handle special cases for enum types
        if "infrastructure_level" in update_data:
            update_data["infrastructure_level"] = InfrastructureLevel(update_data["infrastructure_level"])
        
        # Update region attributes
        for key, value in update_data.items():
            setattr(region, key, value)
        
        db.commit()
        db.refresh(region)
        
        # Log successful update
        kyc_security.log_security_event(
            event_type="kyc_region_updated",
            user_id=current_user_id,
            action="update_region",
            success=True,
            metadata={
                "region_id": region.id,
                "country_code": region.country_code,
                "updated_fields": list(update_data.keys())
            }
        )
        
        return region
    
    @router.get(
        "/{region_id}/requirements",
        summary="Get region KYC requirements",
        description="Get the KYC requirements for a specific region"
    )
    @rate_limit(limit_per_minute=20)
    async def get_region_requirements_by_id(
        region_id: str = Path(..., description="Region ID"),
        verification_type: str = Query("standard", description="Type of verification"),
        db: Session = Depends(get_db)
    ):
        """Get KYC requirements for a specific region."""
        region = db.query(KycRegionDB).filter(
            KycRegionDB.id == region_id
        ).first()
        
        if not region:
            raise HTTPException(status_code=404, detail="Region not found")
        
        # Get requirements
        requirements = get_region_requirements(region, verification_type)
        
        return {
            "region_id": region.id,
            "region_name": region.name,
            "country_code": region.country_code,
            "verification_type": verification_type,
            "requirements": requirements
        }
    
    return router
