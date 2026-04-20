"""
KYC management utilities.

Provides centralized management of KYC processes and operations.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Union
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db

from ..models.verification import KycVerificationDB, VerificationStatus, VerificationType, RiskLevel
from ..models.user_profile import KycUserProfileDB, ProfileStatus
from ..models.region import KycRegionDB, InfrastructureLevel

from .security import kyc_security, encrypt_personal_data, validate_document_data
from .validation import KycValidator, validate_simplified_kyc
from .region_detector import detect_region, get_region_requirements

logger = logging.getLogger(__name__)


class KycManager:
    """Manager for KYC operations."""
    
    def __init__(self, db_session: Session):
        """
        Initialize the KYC manager.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self.security = kyc_security
        logger.info("KYC Manager initialized")
    
    def create_user_profile(
        self, 
        user_id: str,
        profile_data: Dict[str, Any],
        region_id: Optional[str] = None
    ) -> Tuple[KycUserProfileDB, Dict[str, Any]]:
        """
        Create a new KYC user profile.
        
        Args:
            user_id: User ID
            profile_data: Profile data
            region_id: Optional region ID
            
        Returns:
            Tuple of (created profile, operation result)
        """
        # Log the operation
        self.security.log_security_event(
            event_type="kyc_profile_create",
            user_id=user_id,
            action="create_profile",
            success=True,
            metadata={"region_id": region_id}
        )
        
        # Validate the profile data
        valid, error_msg = KycValidator.validate_personal_info(profile_data)
        if not valid:
            logger.warning(f"Invalid profile data for user {user_id}: {error_msg}")
            return None, {"success": False, "error": error_msg}
        
        # Check if profile already exists
        existing_profile = self.db.query(KycUserProfileDB).filter(
            KycUserProfileDB.user_id == user_id
        ).first()
        
        if existing_profile:
            logger.warning(f"Profile already exists for user {user_id}")
            return None, {"success": False, "error": "Profile already exists for this user"}
        
        # Determine region if not provided
        region = None
        if region_id:
            region = self.db.query(KycRegionDB).filter(
                KycRegionDB.id == region_id
            ).first()
        else:
            # Try to detect region from profile data
            country_code = profile_data.get("nationality")
            address = profile_data.get("address", {})
            if address and "country" in address:
                country_code = address["country"]
            
            if country_code:
                region = detect_region(self.db, country_code=country_code)
        
        # Encrypt sensitive data
        is_encrypted = True
        encryption_metadata = None
        
        encrypted_data = {}
        fields_to_encrypt = [
            "full_name", "date_of_birth", "phone_number", "email",
            "tax_id", "address", "occupation", "employer", "source_of_funds"
        ]
        
        for field in fields_to_encrypt:
            if field in profile_data:
                encrypted_data[field] = profile_data[field]
        
        if encrypted_data:
            encryption_result = encrypt_personal_data(encrypted_data)
            encryption_metadata = encryption_result.get("metadata")
        
        # Create new profile
        new_profile = KycUserProfileDB(
            user_id=user_id,
            full_name=profile_data.get("full_name"),
            date_of_birth=profile_data.get("date_of_birth"),
            nationality=profile_data.get("nationality"),
            address=profile_data.get("address"),
            phone_number=profile_data.get("phone_number"),
            email=profile_data.get("email"),
            tax_id=profile_data.get("tax_id"),
            occupation=profile_data.get("occupation"),
            employer=profile_data.get("employer"),
            source_of_funds=profile_data.get("source_of_funds"),
            politically_exposed=profile_data.get("politically_exposed", False),
            is_encrypted=is_encrypted,
            encryption_metadata=encryption_metadata,
            status=ProfileStatus.INCOMPLETE,
            region_id=region.id if region else None,
            references=profile_data.get("references"),
        )
        
        self.db.add(new_profile)
        self.db.commit()
        self.db.refresh(new_profile)
        
        logger.info(f"Created KYC profile for user {user_id}")
        
        return new_profile, {"success": True}
    
    def create_verification(
        self,
        user_id: str,
        verification_type: str,
        submitted_data: Dict[str, Any],
        documents_provided: Optional[List[Dict[str, Any]]] = None,
        third_party_references: Optional[List[Dict[str, Any]]] = None,
        region_id: Optional[str] = None
    ) -> Tuple[Optional[KycVerificationDB], Dict[str, Any]]:
        """
        Create a new KYC verification.
        
        Args:
            user_id: User ID
            verification_type: Type of verification
            submitted_data: Submitted data for verification
            documents_provided: Optional list of documents
            third_party_references: Optional list of references for simplified KYC
            region_id: Optional region ID
            
        Returns:
            Tuple of (created verification, operation result)
        """
        # Log the verification attempt
        self.security.log_security_event(
            event_type="kyc_verification_create",
            user_id=user_id,
            action=f"create_{verification_type}_verification",
            success=True,
            metadata={
                "verification_type": verification_type,
                "document_count": len(documents_provided) if documents_provided else 0,
                "reference_count": len(third_party_references) if third_party_references else 0
            }
        )
        
        # Get or create user profile
        profile = self.db.query(KycUserProfileDB).filter(
            KycUserProfileDB.user_id == user_id
        ).first()
        
        if not profile and submitted_data:
            # Create a profile from the submitted data
            profile, result = self.create_user_profile(
                user_id=user_id,
                profile_data=submitted_data,
                region_id=region_id
            )
            
            if not profile:
                return None, result
        
        # Determine region
        region = None
        if region_id:
            region = self.db.query(KycRegionDB).filter(
                KycRegionDB.id == region_id
            ).first()
        elif profile and profile.region_id:
            region = self.db.query(KycRegionDB).filter(
                KycRegionDB.id == profile.region_id
            ).first()
        else:
            # Try to detect region
            country_code = None
            if submitted_data and "nationality" in submitted_data:
                country_code = submitted_data["nationality"]
            elif submitted_data and "address" in submitted_data and "country" in submitted_data["address"]:
                country_code = submitted_data["address"]["country"]
                
            if country_code:
                region = detect_region(self.db, country_code=country_code)
        
        # Process verification based on type
        if verification_type == VerificationType.SIMPLIFIED:
            if not region or not region.simplified_kyc_enabled:
                logger.warning(f"Simplified KYC not available for user {user_id} in their region")
                return None, {
                    "success": False, 
                    "error": "Simplified KYC not available in your region"
                }
            
            # Validate simplified KYC
            if not third_party_references:
                logger.warning(f"No references provided for simplified KYC for user {user_id}")
                return None, {
                    "success": False, 
                    "error": "Simplified KYC requires at least one reference"
                }
            
            valid, error, result = validate_simplified_kyc(
                user_data=submitted_data,
                references=third_party_references,
                region_config={
                    "simplified_kyc_enabled": region.simplified_kyc_enabled,
                    "simplified_requirements": region.simplified_requirements,
                    "infrastructure_level": region.infrastructure_level.value
                }
            )
            
            if not valid:
                logger.warning(f"Simplified KYC validation failed for user {user_id}: {error}")
                return None, {"success": False, "error": error}
            
            # Set risk level from validation result
            risk_level = result["risk_assessment"]["risk_level"]
            risk_factors = result["risk_assessment"]["risk_factors"]
        else:
            # Standard verification flow
            # Validate documents if provided
            if documents_provided:
                for doc in documents_provided:
                    doc_type = doc.get("document_type")
                    doc_data = doc.get("document_data", {})
                    
                    if not validate_document_data(doc_type, doc_data):
                        logger.warning(f"Invalid document data for {doc_type}")
                        return None, {
                            "success": False, 
                            "error": f"Invalid data for document type {doc_type}"
                        }
            
            # Calculate basic risk assessment
            risk_assessment = KycValidator.calculate_risk_score(
                user_data=submitted_data if submitted_data else {},
                verification_data={
                    "verification_type": verification_type,
                    "documents_provided": documents_provided
                },
                region_data={"infrastructure_level": region.infrastructure_level.value} if region else None
            )
            
            risk_level = risk_assessment["risk_level"]
            risk_factors = risk_assessment["risk_factors"]
        
        # Set verification expiry date based on region settings
        expires_at = None
        if region and region.verification_expiry_days:
            expires_at = datetime.utcnow() + timedelta(days=region.verification_expiry_days)
        
        # Encrypt sensitive data
        is_encrypted = True
        encryption_metadata = None
        
        if submitted_data:
            encryption_result = encrypt_personal_data(submitted_data)
            encryption_metadata = encryption_result.get("metadata")
        
        # Create verification record
        verification = KycVerificationDB(
            user_id=user_id,
            verification_type=verification_type,
            status=VerificationStatus.PENDING,
            submitted_data=submitted_data,
            documents_provided=documents_provided,
            risk_level=risk_level,
            risk_factors=risk_factors,
            is_encrypted=is_encrypted,
            encryption_metadata=encryption_metadata,
            expires_at=expires_at,
            region_id=region.id if region else None,
            profile_id=profile.id if profile else None,
            verification_method="automated" if verification_type == VerificationType.SIMPLIFIED else "manual",
            audit_log=[{
                "timestamp": datetime.utcnow().isoformat(),
                "action": "created",
                "status": VerificationStatus.PENDING.value
            }]
        )
        
        self.db.add(verification)
        self.db.commit()
        self.db.refresh(verification)
        
        # Update profile status if needed
        if profile and profile.status == ProfileStatus.DRAFT:
            profile.status = ProfileStatus.INCOMPLETE
            self.db.commit()
        
        logger.info(f"Created {verification_type} verification for user {user_id}")
        
        return verification, {"success": True}
    
    def process_verification(
        self,
        verification_id: str,
        admin_id: str,
        new_status: str,
        review_notes: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> Tuple[Optional[KycVerificationDB], Dict[str, Any]]:
        """
        Process a KYC verification (approve, reject, etc.).
        
        Args:
            verification_id: Verification ID
            admin_id: Admin ID processing the verification
            new_status: New status to set
            review_notes: Optional review notes
            rejection_reason: Optional rejection reason
            
        Returns:
            Tuple of (updated verification, operation result)
        """
        # Get the verification
        verification = self.db.query(KycVerificationDB).filter(
            KycVerificationDB.id == verification_id
        ).first()
        
        if not verification:
            logger.warning(f"Verification {verification_id} not found")
            return None, {"success": False, "error": "Verification not found"}
        
        # Log the processing attempt
        self.security.log_security_event(
            event_type="kyc_verification_process",
            user_id=admin_id,
            action=f"process_verification_{new_status}",
            success=True,
            metadata={
                "verification_id": verification_id,
                "user_id": verification.user_id,
                "old_status": verification.status.value,
                "new_status": new_status
            }
        )
        
        # Validate the status change
        if verification.status == VerificationStatus.EXPIRED:
            logger.warning(f"Cannot process expired verification {verification_id}")
            return None, {"success": False, "error": "Cannot process expired verification"}
        
        if new_status not in [s.value for s in VerificationStatus]:
            logger.warning(f"Invalid verification status {new_status}")
            return None, {"success": False, "error": f"Invalid status: {new_status}"}
        
        # Update verification status
        old_status = verification.status
        verification.status = VerificationStatus(new_status)
        verification.updated_at = datetime.utcnow()
        verification.reviewed_by = admin_id
        verification.review_date = datetime.utcnow()
        
        if review_notes:
            verification.review_notes = review_notes
            
        if new_status == VerificationStatus.REJECTED.value and rejection_reason:
            verification.rejection_reason = rejection_reason
        
        # Update audit log
        if not verification.audit_log:
            verification.audit_log = []
            
        verification.audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "status_change",
            "admin_id": admin_id,
            "old_status": old_status.value,
            "new_status": new_status,
            "notes": review_notes
        })
        
        # If the verification is approved, update the user profile
        if new_status == VerificationStatus.APPROVED.value and verification.profile_id:
            profile = self.db.query(KycUserProfileDB).filter(
                KycUserProfileDB.id == verification.profile_id
            ).first()
            
            if profile:
                profile.status = ProfileStatus.VERIFIED
                profile.last_verified_at = datetime.utcnow()
                
                # Update audit log
                if not profile.audit_log:
                    profile.audit_log = []
                    
                profile.audit_log.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "verification_approved",
                    "admin_id": admin_id,
                    "verification_id": verification_id,
                    "verification_type": verification.verification_type.value
                })
        
        self.db.commit()
        self.db.refresh(verification)
        
        logger.info(f"Processed verification {verification_id} to status {new_status}")
        
        return verification, {"success": True}
    
    def get_verification_status(
        self,
        verification_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Get the status and details of a verification.
        
        Args:
            verification_id: Verification ID
            
        Returns:
            Tuple of (verification details, operation result)
        """
        verification = self.db.query(KycVerificationDB).filter(
            KycVerificationDB.id == verification_id
        ).first()
        
        if not verification:
            return None, {"success": False, "error": "Verification not found"}
        
        # Get profile if available
        profile_name = None
        if verification.profile:
            profile_name = verification.profile.full_name
        
        # Get region if available
        region_name = None
        infrastructure_level = None
        if verification.region:
            region_name = verification.region.name
            infrastructure_level = verification.region.infrastructure_level.value
        
        # Format verification details
        details = {
            "id": verification.id,
            "user_id": verification.user_id,
            "verification_type": verification.verification_type.value,
            "status": verification.status.value,
            "created_at": verification.created_at.isoformat(),
            "updated_at": verification.updated_at.isoformat(),
            "expires_at": verification.expires_at.isoformat() if verification.expires_at else None,
            "risk_level": verification.risk_level.value,
            "document_count": len(verification.documents_provided) if verification.documents_provided else 0,
            "profile_name": profile_name,
            "region_name": region_name,
            "infrastructure_level": infrastructure_level,
            "is_simplified": verification.verification_type == VerificationType.SIMPLIFIED
        }
        
        return details, {"success": True}
    
    def get_user_verifications(
        self,
        user_id: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Get all verifications for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (list of verification details, operation result)
        """
        verifications = self.db.query(KycVerificationDB).filter(
            KycVerificationDB.user_id == user_id
        ).all()
        
        result = []
        for v in verifications:
            result.append({
                "id": v.id,
                "verification_type": v.verification_type.value,
                "status": v.status.value,
                "created_at": v.created_at.isoformat(),
                "updated_at": v.updated_at.isoformat(),
                "risk_level": v.risk_level.value,
                "expires_at": v.expires_at.isoformat() if v.expires_at else None
            })
        
        return result, {"success": True}
    
    def get_user_profile(
        self,
        user_id: str,
        include_verifications: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Get a user's KYC profile.
        
        Args:
            user_id: User ID
            include_verifications: Whether to include verification history
            
        Returns:
            Tuple of (profile details, operation result)
        """
        profile = self.db.query(KycUserProfileDB).filter(
            KycUserProfileDB.user_id == user_id
        ).first()
        
        if not profile:
            return None, {"success": False, "error": "Profile not found"}
        
        # Get region if available
        region_name = None
        infrastructure_level = None
        if profile.region:
            region_name = profile.region.name
            infrastructure_level = profile.region.infrastructure_level.value
        
        # Format profile details (with sensitive data masked)
        details = {
            "id": profile.id,
            "user_id": profile.user_id,
            "status": profile.status.value,
            "full_name": profile.full_name,
            "nationality": profile.nationality,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
            "last_verified_at": profile.last_verified_at.isoformat() if profile.last_verified_at else None,
            "has_references": bool(profile.references),
            "region_name": region_name,
            "infrastructure_level": infrastructure_level
        }
        
        # Include verifications if requested
        if include_verifications:
            verifications = self.db.query(KycVerificationDB).filter(
                KycVerificationDB.profile_id == profile.id
            ).all()
            
            verification_list = []
            for v in verifications:
                verification_list.append({
                    "id": v.id,
                    "verification_type": v.verification_type.value,
                    "status": v.status.value,
                    "created_at": v.created_at.isoformat(),
                    "risk_level": v.risk_level.value
                })
                
            details["verifications"] = verification_list
        
        return details, {"success": True}
