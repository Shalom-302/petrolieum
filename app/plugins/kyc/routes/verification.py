"""
Routes for managing KYC verifications.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_admin_token, get_current_user_id
from app.plugins.api_gateway.utils import rate_limit

from ..models.verification import VerificationStatus, VerificationType
from ..schemas.verification import (
    VerificationCreate, VerificationUpdate, VerificationResponse, VerificationList,
    VerificationTypeEnum, VerificationStatusEnum
)
from ..utils.kyc_manager import KycManager
from ..utils.security import kyc_security

logger = logging.getLogger(__name__)


def get_verification_router() -> APIRouter:
    """
    Get the verification router.
    
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    @router.post(
        "",
        response_model=VerificationResponse,
        status_code=201,
        summary="Create a new KYC verification",
        description="Create a new KYC verification for a user"
    )
    @rate_limit(limit_per_minute=10)
    async def create_verification(
        verification: VerificationCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Create a new KYC verification."""
        # Log the request
        kyc_security.log_security_event(
            event_type="kyc_verification_request",
            user_id=current_user_id,
            action="create_verification",
            success=True,
            metadata={
                "verification_type": verification.verification_type,
                "documents_count": len(verification.documents_provided) if verification.documents_provided else 0
            }
        )
        
        # Initialize KYC manager
        kyc_manager = KycManager(db_session=db)
        
        # Create verification
        created_verification, result = kyc_manager.create_verification(
            user_id=verification.user_id,
            verification_type=verification.verification_type,
            submitted_data=verification.submitted_data,
            documents_provided=[doc.dict() for doc in verification.documents_provided] if verification.documents_provided else None,
            third_party_references=[ref.dict() for ref in verification.third_party_references] if verification.third_party_references else None,
            region_id=verification.region_id
        )
        
        if not created_verification:
            # Log the failure
            kyc_security.log_security_event(
                event_type="kyc_verification_failed",
                user_id=current_user_id,
                action="create_verification",
                success=False,
                metadata={"error": result.get("error")}
            )
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create verification"))
        
        # Get verification details for response
        verification_details, _ = kyc_manager.get_verification_status(created_verification.id)
        
        # Schedule background processing if needed
        if created_verification.verification_type == VerificationType.SIMPLIFIED:
            # For simplified KYC, we might want to process it automatically in the background
            # This is just a placeholder - in a real implementation, you'd have a background task
            # to automatically process simplified KYC verifications
            pass
        
        return verification_details
    
    @router.get(
        "/{verification_id}",
        response_model=VerificationResponse,
        summary="Get verification details",
        description="Get details of a specific KYC verification"
    )
    @rate_limit(limit_per_minute=20)
    async def get_verification(
        verification_id: str = Path(..., description="Verification ID"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Get a KYC verification by ID."""
        kyc_manager = KycManager(db_session=db)
        verification_details, result = kyc_manager.get_verification_status(verification_id)
        
        if not verification_details:
            raise HTTPException(status_code=404, detail=result.get("error", "Verification not found"))
        
        # Check if the user is authorized to view this verification
        if verification_details["user_id"] != current_user_id:
            # Check if the user is an admin
            try:
                verify_admin_token(current_user_id)
            except:
                # Log unauthorized access attempt
                kyc_security.log_security_event(
                    event_type="kyc_verification_unauthorized_access",
                    user_id=current_user_id,
                    action="get_verification",
                    success=False,
                    metadata={"verification_id": verification_id}
                )
                raise HTTPException(status_code=403, detail="Not authorized to view this verification")
        
        return verification_details
    
    @router.get(
        "",
        response_model=VerificationList,
        summary="List verifications",
        description="List KYC verifications with optional filtering"
    )
    @rate_limit(limit_per_minute=10)
    async def list_verifications(
        user_id: Optional[str] = Query(None, description="Filter by user ID"),
        status: Optional[str] = Query(None, description="Filter by status"),
        verification_type: Optional[str] = Query(None, description="Filter by verification type"),
        page: int = Query(1, description="Page number", ge=1),
        size: int = Query(10, description="Page size", ge=1, le=100),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """List KYC verifications with pagination and filtering."""
        # Check if the user is an admin for listing all verifications
        is_admin = False
        try:
            verify_admin_token(current_user_id)
            is_admin = True
        except:
            # Non-admin users can only view their own verifications
            if not user_id or user_id != current_user_id:
                user_id = current_user_id
        
        # Query verifications
        query = db.query(VerificationStatus)
        
        if user_id:
            query = query.filter(VerificationStatus.user_id == user_id)
        
        if status:
            try:
                status_enum = VerificationStatus(status)
                query = query.filter(VerificationStatus.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        if verification_type:
            try:
                type_enum = VerificationType(verification_type)
                query = query.filter(VerificationStatus.verification_type == type_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid verification type: {verification_type}")
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        verifications = query.order_by(VerificationStatus.created_at.desc()) \
            .offset((page - 1) * size) \
            .limit(size) \
            .all()
        
        # Format response
        kyc_manager = KycManager(db_session=db)
        verification_list = []
        
        for v in verifications:
            details, _ = kyc_manager.get_verification_status(v.id)
            if details:
                verification_list.append(details)
        
        return {
            "items": verification_list,
            "total": total,
            "page": page,
            "size": size
        }
    
    @router.put(
        "/{verification_id}",
        response_model=VerificationResponse,
        summary="Update verification status",
        description="Update the status of a KYC verification (admin only)"
    )
    @rate_limit(limit_per_minute=10)
    async def update_verification(
        verification_update: VerificationUpdate,
        verification_id: str = Path(..., description="Verification ID"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Update a KYC verification status (admin only)."""
        # Verify admin permissions
        try:
            verify_admin_token(current_user_id)
        except:
            # Log unauthorized access attempt
            kyc_security.log_security_event(
                event_type="kyc_verification_unauthorized_update",
                user_id=current_user_id,
                action="update_verification",
                success=False,
                metadata={"verification_id": verification_id}
            )
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Initialize KYC manager
        kyc_manager = KycManager(db_session=db)
        
        # Process verification
        updated_verification, result = kyc_manager.process_verification(
            verification_id=verification_id,
            admin_id=current_user_id,
            new_status=verification_update.status,
            review_notes=verification_update.review_notes,
            rejection_reason=verification_update.rejection_reason
        )
        
        if not updated_verification:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to update verification"))
        
        # Get updated verification details
        verification_details, _ = kyc_manager.get_verification_status(verification_id)
        
        return verification_details
    
    return router
