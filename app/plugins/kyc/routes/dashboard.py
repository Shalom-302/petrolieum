"""
Routes for the KYC administrative dashboard.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from app.core.db import get_db
from app.core.security import verify_admin_token, get_current_user_id
from app.plugins.api_gateway.utils import rate_limit

from ..models.verification import KycVerificationDB, VerificationStatus, VerificationType, RiskLevel
from ..models.user_profile import KycUserProfileDB, ProfileStatus
from ..models.region import KycRegionDB, InfrastructureLevel
from ..utils.security import kyc_security

logger = logging.getLogger(__name__)


def get_dashboard_router() -> APIRouter:
    """
    Get the KYC dashboard router.
    
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    @router.get(
        "/statistics/overview",
        summary="KYC statistics overview",
        description="Get overview statistics for the KYC system (admin only)"
    )
    @rate_limit(limit_per_minute=10)
    async def get_statistics_overview(
        time_range: str = Query("30d", description="Time range for statistics (7d, 30d, 90d, all)"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Get overview statistics for the KYC system."""
        # Verify admin permissions
        try:
            verify_admin_token(current_user_id)
        except:
            # Log unauthorized access attempt
            kyc_security.log_security_event(
                event_type="kyc_dashboard_unauthorized_access",
                user_id=current_user_id,
                action="get_statistics_overview",
                success=False,
                metadata={}
            )
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Determine date filter based on time_range
        date_filter = None
        if time_range != "all":
            days = 30  # Default to 30 days
            if time_range == "7d":
                days = 7
            elif time_range == "90d":
                days = 90
                
            start_date = datetime.utcnow() - timedelta(days=days)
            date_filter = KycVerificationDB.created_at >= start_date
        
        # Query verification statistics
        verification_query = db.query(
            KycVerificationDB.status,
            func.count(KycVerificationDB.id).label("count")
        )
        
        if date_filter:
            verification_query = verification_query.filter(date_filter)
            
        verification_stats = verification_query.group_by(
            KycVerificationDB.status
        ).all()
        
        # Format verification statistics
        verification_counts = {
            "total": 0,
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "expired": 0
        }
        
        for status, count in verification_stats:
            verification_counts["total"] += count
            status_name = status.value.lower()
            if status_name in verification_counts:
                verification_counts[status_name] = count
        
        # Query profile statistics
        profile_query = db.query(
            KycUserProfileDB.status,
            func.count(KycUserProfileDB.id).label("count")
        )
        
        if date_filter:
            profile_query = profile_query.filter(KycUserProfileDB.created_at >= start_date)
            
        profile_stats = profile_query.group_by(
            KycUserProfileDB.status
        ).all()
        
        # Format profile statistics
        profile_counts = {
            "total": 0,
            "incomplete": 0,
            "pending": 0,
            "verified": 0,
            "rejected": 0
        }
        
        for status, count in profile_stats:
            profile_counts["total"] += count
            status_name = status.value.lower()
            if status_name in profile_counts:
                profile_counts[status_name] = count
        
        # Query verification types
        verification_type_query = db.query(
            KycVerificationDB.verification_type,
            func.count(KycVerificationDB.id).label("count")
        )
        
        if date_filter:
            verification_type_query = verification_type_query.filter(date_filter)
            
        verification_type_stats = verification_type_query.group_by(
            KycVerificationDB.verification_type
        ).all()
        
        # Format verification type statistics
        verification_type_counts = {
            "standard": 0,
            "simplified": 0,
            "enhanced": 0
        }
        
        for v_type, count in verification_type_stats:
            type_name = v_type.value.lower()
            if type_name in verification_type_counts:
                verification_type_counts[type_name] = count
        
        # Get simplified KYC ratio
        simplified_count = verification_type_counts.get("simplified", 0)
        total_count = verification_counts.get("total", 0)
        simplified_ratio = 0
        if total_count > 0:
            simplified_ratio = simplified_count / total_count
        
        # Format response
        response = {
            "time_range": time_range,
            "verification_counts": verification_counts,
            "profile_counts": profile_counts,
            "verification_types": verification_type_counts,
            "simplified_kyc_ratio": simplified_ratio,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return response
    
    @router.get(
        "/statistics/by-region",
        summary="KYC statistics by region",
        description="Get KYC statistics broken down by region (admin only)"
    )
    @rate_limit(limit_per_minute=10)
    async def get_statistics_by_region(
        time_range: str = Query("30d", description="Time range for statistics (7d, 30d, 90d, all)"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Get KYC statistics broken down by region."""
        # Verify admin permissions
        try:
            verify_admin_token(current_user_id)
        except:
            # Log unauthorized access attempt
            kyc_security.log_security_event(
                event_type="kyc_dashboard_unauthorized_access",
                user_id=current_user_id,
                action="get_statistics_by_region",
                success=False,
                metadata={}
            )
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Determine date filter based on time_range
        date_filter = None
        if time_range != "all":
            days = 30  # Default to 30 days
            if time_range == "7d":
                days = 7
            elif time_range == "90d":
                days = 90
                
            start_date = datetime.utcnow() - timedelta(days=days)
            date_filter = KycVerificationDB.created_at >= start_date
        
        # Get all regions
        regions = db.query(KycRegionDB).all()
        region_map = {r.id: r for r in regions}
        
        # Query verification statistics by region
        region_query = db.query(
            KycVerificationDB.region_id,
            KycVerificationDB.status,
            func.count(KycVerificationDB.id).label("count")
        )
        
        if date_filter:
            region_query = region_query.filter(date_filter)
            
        region_stats = region_query.group_by(
            KycVerificationDB.region_id,
            KycVerificationDB.status
        ).all()
        
        # Format region statistics
        region_data = {}
        
        for region_id, status, count in region_stats:
            if not region_id:
                region_name = "Unknown"
                country_code = "XX"
            else:
                region = region_map.get(region_id)
                region_name = region.name if region else "Unknown"
                country_code = region.country_code if region else "XX"
            
            if region_name not in region_data:
                region_data[region_name] = {
                    "country_code": country_code,
                    "region_id": region_id,
                    "total": 0,
                    "pending": 0,
                    "approved": 0,
                    "rejected": 0,
                    "simplified_count": 0
                }
            
            region_data[region_name]["total"] += count
            status_name = status.value.lower()
            if status_name in ["pending", "approved", "rejected"]:
                region_data[region_name][status_name] = count
        
        # Query simplified KYC by region
        simplified_query = db.query(
            KycVerificationDB.region_id,
            func.count(KycVerificationDB.id).label("count")
        ).filter(KycVerificationDB.verification_type == VerificationType.SIMPLIFIED)
        
        if date_filter:
            simplified_query = simplified_query.filter(date_filter)
            
        simplified_stats = simplified_query.group_by(
            KycVerificationDB.region_id
        ).all()
        
        # Add simplified KYC counts
        for region_id, count in simplified_stats:
            if not region_id:
                region_name = "Unknown"
            else:
                region = region_map.get(region_id)
                region_name = region.name if region else "Unknown"
            
            if region_name in region_data:
                region_data[region_name]["simplified_count"] = count
        
        # Format response
        response = {
            "time_range": time_range,
            "regions": list(region_data.values()),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return response
    
    @router.get(
        "/pending-verifications",
        summary="Pending KYC verifications",
        description="Get a list of pending KYC verifications for review (admin only)"
    )
    @rate_limit(limit_per_minute=10)
    async def get_pending_verifications(
        risk_level: Optional[str] = Query(None, description="Filter by risk level"),
        verification_type: Optional[str] = Query(None, description="Filter by verification type"),
        page: int = Query(1, description="Page number", ge=1),
        size: int = Query(20, description="Page size", ge=1, le=100),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Get a list of pending KYC verifications for review."""
        # Verify admin permissions
        try:
            verify_admin_token(current_user_id)
        except:
            # Log unauthorized access attempt
            kyc_security.log_security_event(
                event_type="kyc_dashboard_unauthorized_access",
                user_id=current_user_id,
                action="get_pending_verifications",
                success=False,
                metadata={}
            )
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Query pending verifications
        query = db.query(KycVerificationDB).filter(
            KycVerificationDB.status == VerificationStatus.PENDING
        )
        
        if risk_level:
            try:
                risk_enum = RiskLevel(risk_level)
                query = query.filter(KycVerificationDB.risk_level == risk_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid risk level: {risk_level}")
        
        if verification_type:
            try:
                type_enum = VerificationType(verification_type)
                query = query.filter(KycVerificationDB.verification_type == type_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid verification type: {verification_type}")
        
        # Order by risk level (high risk first)
        query = query.order_by(
            desc(KycVerificationDB.risk_level),
            KycVerificationDB.created_at
        )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        verifications = query.offset((page - 1) * size).limit(size).all()
        
        # Format response
        verification_list = []
        for v in verifications:
            # Get user profile name
            profile_name = None
            if v.profile_id:
                profile = db.query(KycUserProfileDB).filter(
                    KycUserProfileDB.id == v.profile_id
                ).first()
                
                if profile:
                    profile_name = profile.full_name
                    
            # Get region name
            region_name = None
            if v.region_id:
                region = db.query(KycRegionDB).filter(
                    KycRegionDB.id == v.region_id
                ).first()
                
                if region:
                    region_name = region.name
            
            verification_list.append({
                "id": v.id,
                "user_id": v.user_id,
                "verification_type": v.verification_type.value,
                "risk_level": v.risk_level.value,
                "created_at": v.created_at.isoformat(),
                "profile_name": profile_name,
                "region_name": region_name,
                "document_count": len(v.documents_provided) if v.documents_provided else 0,
                "is_simplified": v.verification_type == VerificationType.SIMPLIFIED
            })
        
        return {
            "items": verification_list,
            "total": total,
            "page": page,
            "size": size
        }
    
    @router.get(
        "/risk-assessment",
        summary="Risk assessment overview",
        description="Get an overview of risk assessment results (admin only)"
    )
    @rate_limit(limit_per_minute=10)
    async def get_risk_assessment(
        time_range: str = Query("30d", description="Time range for statistics (7d, 30d, 90d, all)"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """Get an overview of risk assessment results."""
        # Verify admin permissions
        try:
            verify_admin_token(current_user_id)
        except:
            # Log unauthorized access attempt
            kyc_security.log_security_event(
                event_type="kyc_dashboard_unauthorized_access",
                user_id=current_user_id,
                action="get_risk_assessment",
                success=False,
                metadata={}
            )
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        # Determine date filter based on time_range
        date_filter = None
        if time_range != "all":
            days = 30  # Default to 30 days
            if time_range == "7d":
                days = 7
            elif time_range == "90d":
                days = 90
                
            start_date = datetime.utcnow() - timedelta(days=days)
            date_filter = KycVerificationDB.created_at >= start_date
        
        # Query risk level distribution
        risk_query = db.query(
            KycVerificationDB.risk_level,
            func.count(KycVerificationDB.id).label("count")
        )
        
        if date_filter:
            risk_query = risk_query.filter(date_filter)
            
        risk_stats = risk_query.group_by(
            KycVerificationDB.risk_level
        ).all()
        
        # Format risk level statistics
        risk_counts = {
            "low": 0,
            "medium": 0,
            "high": 0
        }
        
        total_count = 0
        for risk_level, count in risk_stats:
            risk_name = risk_level.value.lower()
            if risk_name in risk_counts:
                risk_counts[risk_name] = count
                total_count += count
        
        # Calculate percentages
        risk_percentages = {
            "low": 0,
            "medium": 0,
            "high": 0
        }
        
        if total_count > 0:
            for key in risk_counts:
                risk_percentages[key] = risk_counts[key] / total_count
        
        # Query risk level by verification type
        risk_by_type_query = db.query(
            KycVerificationDB.verification_type,
            KycVerificationDB.risk_level,
            func.count(KycVerificationDB.id).label("count")
        )
        
        if date_filter:
            risk_by_type_query = risk_by_type_query.filter(date_filter)
            
        risk_by_type_stats = risk_by_type_query.group_by(
            KycVerificationDB.verification_type,
            KycVerificationDB.risk_level
        ).all()
        
        # Format risk by verification type
        risk_by_type = {
            "standard": {
                "low": 0,
                "medium": 0,
                "high": 0
            },
            "simplified": {
                "low": 0,
                "medium": 0,
                "high": 0
            },
            "enhanced": {
                "low": 0,
                "medium": 0,
                "high": 0
            }
        }
        
        for v_type, risk_level, count in risk_by_type_stats:
            type_name = v_type.value.lower()
            risk_name = risk_level.value.lower()
            
            if type_name in risk_by_type and risk_name in risk_by_type[type_name]:
                risk_by_type[type_name][risk_name] = count
        
        # Format response
        response = {
            "time_range": time_range,
            "risk_counts": risk_counts,
            "risk_percentages": risk_percentages,
            "risk_by_verification_type": risk_by_type,
            "total_assessments": total_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return response
    
    return router
