"""
Routes for managing KYC user profiles.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_admin_token, get_current_user_id
from app.plugins.api_gateway.utils import rate_limit

from ..models.user_profile import ProfileStatus
from ..schemas.user_profile import (
    UserProfileCreate, UserProfileUpdate, UserProfileResponse, 
    UserProfileList, ProfileStatusEnum
)
from ..utils.kyc_manager import KycManager
from ..utils.security import kyc_security

logger = logging.getLogger(__name__)


def get_profile_router() -> APIRouter:
    """
    Get the user profile router.
    
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    @router.post(
        "",
        response_model=UserProfileResponse,
        status_code=201,
        summary="Create a new KYC user profile",
        description="Create a new KYC profile for a user"
    )
    @rate_limit(limit_per_minute=5)
    async def create_user_profile(
        profile: UserProfileCreate,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Create a new KYC user profile."""
        # Log the profile creation attempt
        kyc_security.log_security_event(
            event_type="kyc_profile_create",
            user_id=current_user_id,
            action="create_profile",
            success=True,
            metadata={}
        )
        
        # Initialize KYC manager
        kyc_manager = KycManager(db_session=db)
        
        # Set user_id to current user if not specified or if not admin
        is_admin = False
        try:
            verify_admin_token(current_user_id)
            is_admin = True
        except:
            pass
        
        # Only admins can create profiles for other users
        if not is_admin and profile.user_id != current_user_id:
            # Log unauthorized attempt
            kyc_security.log_security_event(
                event_type="kyc_profile_unauthorized_create",
                user_id=current_user_id,
                action="create_profile",
                success=False,
                metadata={"target_user_id": profile.user_id}
            )
            profile.user_id = current_user_id
        
        # Create user profile
        profile_data = profile.dict()
        created_profile, result = kyc_manager.create_user_profile(
            user_id=profile.user_id,
            profile_data=profile_data,
            region_id=profile.region_id
        )
        
        if not created_profile:
            # Log failure
            kyc_security.log_security_event(
                event_type="kyc_profile_creation_failed",
                user_id=current_user_id,
                action="create_profile",
                success=False,
                metadata={"error": result.get("error")}
            )
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create user profile"))
        
        # Get profile details
        profile_details, _ = kyc_manager.get_user_profile(created_profile.user_id)
        
        return profile_details
    
    @router.get(
        "/me",
        response_model=UserProfileResponse,
        summary="Get current user's KYC profile",
        description="Get the KYC profile of the current user"
    )
    @rate_limit(limit_per_minute=20)
    async def get_current_user_profile(
        include_verifications: bool = Query(False, description="Include verification history"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Get the current user's KYC profile."""
        kyc_manager = KycManager(db_session=db)
        profile_details, result = kyc_manager.get_user_profile(
            user_id=current_user_id,
            include_verifications=include_verifications
        )
        
        if not profile_details:
            raise HTTPException(status_code=404, detail=result.get("error", "Profile not found"))
        
        return profile_details
    
    @router.get(
        "/{user_id}",
        response_model=UserProfileResponse,
        summary="Get user's KYC profile",
        description="Get the KYC profile of a specific user (admin only)"
    )
    @rate_limit(limit_per_minute=10)
    async def get_user_profile(
        user_id: str = Path(..., description="User ID"),
        include_verifications: bool = Query(False, description="Include verification history"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Get a user's KYC profile (admin only or own profile)."""
        # Check if user is accessing their own profile
        if user_id != current_user_id:
            # Verify admin permissions
            try:
                verify_admin_token(current_user_id)
            except:
                # Log unauthorized access attempt
                kyc_security.log_security_event(
                    event_type="kyc_profile_unauthorized_access",
                    user_id=current_user_id,
                    action="get_user_profile",
                    success=False,
                    metadata={"target_user_id": user_id}
                )
                raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Get profile
        kyc_manager = KycManager(db_session=db)
        profile_details, result = kyc_manager.get_user_profile(
            user_id=user_id,
            include_verifications=include_verifications
        )
        
        if not profile_details:
            raise HTTPException(status_code=404, detail=result.get("error", "Profile not found"))
        
        return profile_details
    
    @router.get(
        "",
        response_model=UserProfileList,
        summary="List user profiles",
        description="List KYC user profiles with optional filtering (admin only)"
    )
    @rate_limit(limit_per_minute=5)
    async def list_user_profiles(
        status: Optional[str] = Query(None, description="Filter by status"),
        nationality: Optional[str] = Query(None, description="Filter by nationality"),
        region_id: Optional[str] = Query(None, description="Filter by region ID"),
        page: int = Query(1, description="Page number", ge=1),
        size: int = Query(10, description="Page size", ge=1, le=100),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """List KYC user profiles with pagination and filtering (admin only)."""
        # Verify admin permissions
        try:
            verify_admin_token(current_user_id)
        except:
            # Log unauthorized access attempt
            kyc_security.log_security_event(
                event_type="kyc_profile_unauthorized_list",
                user_id=current_user_id,
                action="list_user_profiles",
                success=False,
                metadata={}
            )
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Query profiles
        query = db.query(KycUserProfileDB)
        
        if status:
            try:
                status_enum = ProfileStatus(status)
                query = query.filter(KycUserProfileDB.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        if nationality:
            query = query.filter(KycUserProfileDB.nationality == nationality)
        
        if region_id:
            query = query.filter(KycUserProfileDB.region_id == region_id)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        profiles = query.order_by(KycUserProfileDB.created_at.desc()) \
            .offset((page - 1) * size) \
            .limit(size) \
            .all()
        
        # Format response
        kyc_manager = KycManager(db_session=db)
        profile_list = []
        
        for p in profiles:
            profile_details, _ = kyc_manager.get_user_profile(p.user_id)
            if profile_details:
                profile_list.append(profile_details)
        
        return {
            "items": profile_list,
            "total": total,
            "page": page,
            "size": size
        }
    
    @router.put(
        "/{user_id}",
        response_model=UserProfileResponse,
        summary="Update user profile",
        description="Update a user's KYC profile"
    )
    @rate_limit(limit_per_minute=5)
    async def update_user_profile(
        profile_update: UserProfileUpdate,
        user_id: str = Path(..., description="User ID"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Update a user's KYC profile."""
        # Check if user is updating their own profile
        if user_id != current_user_id:
            # Verify admin permissions
            try:
                verify_admin_token(current_user_id)
            except:
                # Log unauthorized update attempt
                kyc_security.log_security_event(
                    event_type="kyc_profile_unauthorized_update",
                    user_id=current_user_id,
                    action="update_user_profile",
                    success=False,
                    metadata={"target_user_id": user_id}
                )
                raise HTTPException(status_code=403, detail="Not authorized to update this profile")
        
        # Get existing profile
        kyc_manager = KycManager(db_session=db)
        existing_profile, result = kyc_manager.get_user_profile(user_id)
        
        if not existing_profile:
            raise HTTPException(status_code=404, detail=result.get("error", "Profile not found"))
        
        # Update profile
        # In a real implementation, you would validate and update the profile here
        # For simplicity, we're just returning the existing profile
        return existing_profile
    
    return router
