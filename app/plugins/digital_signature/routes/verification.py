"""
Signature verification routes.

This module provides API endpoints for verifying digital signatures
and validating signed documents against trusted certificates.
"""

import logging
from typing import List, Optional, Dict, Any
import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.core.rate_limit import rate_limit
from app.plugins.digital_signature.utils.security import verify_signature
from app.plugins.digital_signature.models.signature import SignatureDB
from app.plugins.digital_signature.schemas.signature import (
    SignatureVerify,
    SignatureVerifyResponse
)
from app.plugins.digital_signature.services.document_service import DocumentService

logger = logging.getLogger(__name__)


def get_verification_router():
    """
    Create and return a router for verification endpoints.
    
    This function initializes an APIRouter with various endpoints for
    verifying digital signatures and checking document authenticity.
    
    Returns:
        APIRouter: FastAPI router with verification endpoints
    """
    router = APIRouter()
    
    @router.post(
        "/signature",
        response_model=SignatureVerifyResponse,
        summary="Verify a digital signature",
        description="Verify the authenticity of a digitally signed document"
    )
    @rate_limit(limit_per_minute=50)
    async def verify_document_signature(
        document: UploadFile = File(...),
        signature_id: str = Form(...),
        db: Session = Depends(get_db)
    ):
        """
        Verify the authenticity of a digitally signed document.
        
        This endpoint checks if a document's signature is valid and was issued
        by the trusted certificate authority.
        
        Args:
            document: Document to verify
            signature_id: ID of the signature to verify against
            db: Database session
            
        Returns:
            SignatureVerifyResponse: Verification result with signature details
        """
        try:
            # Read document content
            document_content = await document.read()
            
            # Verify signature using the document service
            document_service = DocumentService(db)
            verification_result = document_service.verify_signature(
                signature_id=signature_id,
                document_content=document_content
            )
            
            if verification_result["verified"]:
                signature = document_service.get_signature(signature_id)
                return SignatureVerifyResponse(
                    verified=True,
                    document_name=signature.document_name,
                    signature_timestamp=signature.created_at,
                    signer_info=signature.signer_info,
                    signature_type=signature.signature_type
                )
            else:
                return SignatureVerifyResponse(
                    verified=False,
                    error=verification_result["error"]
                )
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return SignatureVerifyResponse(
                verified=False,
                error=f"Error verifying signature: {str(e)}"
            )
    
    @router.post(
        "/legal-evidence",
        summary="Generate legal evidence package",
        description="Generate a complete evidence package for legal proceedings"
    )
    @rate_limit(limit_per_minute=10)
    async def generate_legal_evidence(
        signature_id: str = Form(...),
        include_certificate_chain: bool = Form(True),
        include_timestamp_proof: bool = Form(True),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Generate a complete evidence package for legal proceedings.
        
        This endpoint creates a comprehensive evidence package that can be
        used in legal proceedings to prove the authenticity of a signed document.
        
        Args:
            signature_id: ID of the signature
            include_certificate_chain: Whether to include the certificate chain
            include_timestamp_proof: Whether to include timestamp proof
            db: Database session
            current_user_id: ID of the current user
            
        Returns:
            dict: Evidence package with all relevant information
        """
        try:
            document_service = DocumentService(db)
            signature = document_service.get_signature(signature_id)
            
            if not signature:
                raise HTTPException(
                    status_code=404, 
                    detail="Signature not found"
                )
            
            # Check if the user has access to this signature
            if signature.user_id != current_user_id:
                logger.warning(f"Unauthorized access attempt to signature {signature_id} by user {current_user_id}")
                raise HTTPException(
                    status_code=403, 
                    detail="You don't have permission to access this signature"
                )
            
            # Generate evidence package
            evidence = document_service.generate_legal_evidence(
                signature_id=signature_id,
                include_certificate_chain=include_certificate_chain,
                include_timestamp_proof=include_timestamp_proof
            )
            
            return {
                "evidence_id": evidence.id,
                "signature_id": signature_id,
                "document_name": signature.document_name,
                "timestamp": signature.created_at,
                "signature_type": signature.signature_type,
                "signer_info": signature.signer_info,
                "certificate_chain": evidence.certificate_chain if include_certificate_chain else None,
                "timestamp_proof": evidence.timestamp_proof if include_timestamp_proof else None,
                "legal_validity": "Valid for court proceedings",
                "validation_url": f"/api/digital-signature/verify/evidence/{evidence.id}"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating legal evidence: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error generating legal evidence: {str(e)}"
            )
    
    @router.get(
        "/evidence/{evidence_id}",
        summary="Validate evidence package",
        description="Validate a legal evidence package"
    )
    async def validate_evidence_package(
        evidence_id: str,
        db: Session = Depends(get_db)
    ):
        """
        Validate a legal evidence package.
        
        This endpoint verifies the validity of a legal evidence package,
        which can be used to prove the authenticity of a signed document
        in legal proceedings.
        
        Args:
            evidence_id: ID of the evidence package
            db: Database session
            
        Returns:
            dict: Validation result
        """
        try:
            document_service = DocumentService(db)
            validation_result = document_service.validate_evidence(evidence_id)
            
            if validation_result["valid"]:
                evidence = document_service.get_evidence(evidence_id)
                return {
                    "valid": True,
                    "evidence_id": evidence_id,
                    "signature_id": evidence.signature_id,
                    "timestamp": evidence.created_at,
                    "validation_authority": "KAAPI Digital Signature Authority",
                    "legal_validity": "Valid for court proceedings"
                }
            else:
                return {
                    "valid": False,
                    "error": validation_result["error"]
                }
        except Exception as e:
            logger.error(f"Error validating evidence: {e}")
            return {
                "valid": False,
                "error": f"Error validating evidence: {str(e)}"
            }
            
    return router
