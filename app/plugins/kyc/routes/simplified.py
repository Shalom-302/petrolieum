"""
Routes for simplified KYC processes in regions with low infrastructure.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.plugins.api_gateway.utils import rate_limit

from ..models.verification import VerificationType
from ..models.region import InfrastructureLevel
from ..schemas.verification import VerificationResponse, ThirdPartyReference
from ..schemas.user_profile import UserProfileCreate, UserProfileResponse, ReferenceCreate
from ..utils.kyc_manager import KycManager
from ..utils.security import kyc_security
from ..utils.validation import validate_simplified_kyc
from ..utils.region_detector import detect_region

logger = logging.getLogger(__name__)


class SimplifiedKycRequest(UserProfileCreate):
    """Schema for simplified KYC request."""
    references: List[ReferenceCreate] = Body(..., min_items=1, description="Trusted references for verification")
    country_code: str = Body(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")
    

def get_simplified_kyc_router() -> APIRouter:
    """
    Get the simplified KYC router.
    
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    @router.post(
        "",
        response_model=VerificationResponse,
        status_code=201,
        summary="Submit simplified KYC verification",
        description="Submit a simplified KYC verification for regions with low infrastructure"
    )
    @rate_limit(limit_per_minute=5)
    async def create_simplified_kyc(
        request: SimplifiedKycRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Submit a simplified KYC verification using trusted references."""
        # Log the simplified KYC request
        kyc_security.log_security_event(
            event_type="simplified_kyc_request",
            user_id=current_user_id,
            action="create_simplified_kyc",
            success=True,
            metadata={
                "country_code": request.country_code,
                "reference_count": len(request.references)
            }
        )
        
        # Detect region based on country code
        region = detect_region(db, country_code=request.country_code)
        if not region:
            raise HTTPException(
                status_code=400, 
                detail=f"Region not configured for country code: {request.country_code}"
            )
        
        # Check if simplified KYC is enabled for this region
        if not region.simplified_kyc_enabled:
            raise HTTPException(
                status_code=400, 
                detail="Simplified KYC is not available in your region"
            )
            
        # Check if the region has low infrastructure
        if region.infrastructure_level not in [InfrastructureLevel.LOW, InfrastructureLevel.VERY_LOW]:
            # Log attempt to use simplified KYC in high-infrastructure region
            kyc_security.log_security_event(
                event_type="simplified_kyc_misuse",
                user_id=current_user_id,
                action="create_simplified_kyc",
                success=False,
                metadata={
                    "country_code": request.country_code,
                    "infrastructure_level": region.infrastructure_level.value
                }
            )
            
            raise HTTPException(
                status_code=400, 
                detail="Simplified KYC is only available in regions with low infrastructure"
            )
        
        # Initialize KYC manager
        kyc_manager = KycManager(db_session=db)
        
        # Convert user profile data
        profile_data = request.dict(exclude={"references", "country_code"})
        profile_data["user_id"] = current_user_id
        
        # Set region ID
        region_id = region.id
        
        # Convert references to the format expected by the verification system
        third_party_references = []
        for ref in request.references:
            third_party_reference = {
                "reference_type": ref.reference_type,
                "reference_name": ref.full_name,
                "reference_id": None,
                "reference_contact": ref.contact_info,
                "relationship": ref.relationship,
                "verification_notes": f"Reference added during simplified KYC for {current_user_id}"
            }
            third_party_references.append(third_party_reference)
        
        # Create verification with simplified KYC type
        created_verification, result = kyc_manager.create_verification(
            user_id=current_user_id,
            verification_type=VerificationType.SIMPLIFIED,
            submitted_data=profile_data,
            third_party_references=third_party_references,
            region_id=region_id
        )
        
        if not created_verification:
            # Log the failure
            kyc_security.log_security_event(
                event_type="simplified_kyc_failed",
                user_id=current_user_id,
                action="create_simplified_kyc",
                success=False,
                metadata={"error": result.get("error")}
            )
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "Failed to create simplified KYC verification")
            )
        
        # Get verification details for response
        verification_details, _ = kyc_manager.get_verification_status(created_verification.id)
        
        # Schedule automatic processing for simplified KYC in background
        # In a real implementation, this would process the verification automatically
        # based on the references and risk assessment
        
        return verification_details
    
    @router.get(
        "/requirements/{country_code}",
        summary="Get simplified KYC requirements",
        description="Get the requirements for simplified KYC in a specific region"
    )
    @rate_limit(limit_per_minute=20)
    async def get_simplified_requirements(
        country_code: str = Path(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"),
        db: Session = Depends(get_db)
    ):
        """Get simplified KYC requirements for a specific country."""
        # Detect region based on country code
        region = detect_region(db, country_code=country_code)
        if not region:
            raise HTTPException(
                status_code=404, 
                detail=f"Region not configured for country code: {country_code}"
            )
        
        # Check if simplified KYC is available
        if not region.simplified_kyc_enabled:
            raise HTTPException(
                status_code=404, 
                detail="Simplified KYC is not available in this region"
            )
        
        # Return the requirements
        return {
            "region_name": region.name,
            "country_code": region.country_code,
            "infrastructure_level": region.infrastructure_level.value,
            "simplified_kyc_enabled": region.simplified_kyc_enabled,
            "requirements": region.simplified_requirements,
            "transaction_threshold": region.simplified_kyc_threshold,
            "accepted_references": region.trusted_referee_types
        }
    
    @router.get(
        "/eligible-regions",
        summary="List regions eligible for simplified KYC",
        description="Get a list of regions where simplified KYC is available"
    )
    @rate_limit(limit_per_minute=10)
    async def list_eligible_regions(
        db: Session = Depends(get_db)
    ):
        """List regions where simplified KYC is available."""
        # Query regions where simplified KYC is enabled
        eligible_regions = db.query(KycRegionDB).filter(
            KycRegionDB.simplified_kyc_enabled == True
        ).all()
        
        # Format response
        regions = []
        for region in eligible_regions:
            regions.append({
                "id": region.id,
                "name": region.name,
                "country_code": region.country_code,
                "infrastructure_level": region.infrastructure_level.value,
                "transaction_threshold": region.simplified_kyc_threshold
            })
        
        return {"regions": regions}
    
    return router
