"""
Digital signature routes.

This module provides API endpoints for digitally signing documents,
including single and batch signing operations.
"""

import logging
from typing import List, Optional
import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.core.rate_limit import rate_limit
from app.plugins.digital_signature.utils.security import sign_data, get_certificate
from app.plugins.digital_signature.models.signature import SignatureDB
from app.plugins.digital_signature.schemas.signature import (
    SignatureResponse,
    SignatureCreate,
    SignatureVerify,
    BatchSignatureRequest
)
from app.plugins.digital_signature.services.document_service import DocumentService

logger = logging.getLogger(__name__)


def get_signature_router():
    """
    Create and return a router for signature endpoints.
    
    This function initializes an APIRouter with various endpoints for
    handling digital signatures, including document signing and verification.
    
    Returns:
        APIRouter: FastAPI router with signature endpoints
    """
    router = APIRouter()
    
    @router.post(
        "/document",
        response_model=SignatureResponse,
        summary="Sign a document",
        description="Digitally sign a document using PKI"
    )
    @rate_limit(limit_per_minute=20)
    async def sign_document(
        document: UploadFile = File(...),
        description: str = Form(None),
        signature_type: str = Form("qualified", description="Type of signature (qualified, advanced, standard)"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Digitally sign a document using PKI.
        
        Args:
            document: Document to sign
            description: Optional description of the signed document
            signature_type: Type of signature (qualified, advanced, standard)
            db: Database session
            current_user_id: ID of the current user
            
        Returns:
            SignatureResponse: Information about the created signature
        """
        try:
            # Log detailed request information
            logger.info(f"Received sign_document request with params:")
            logger.info(f"  - document: {document.filename} ({document.content_type}, {document.size} bytes)")
            logger.info(f"  - description: {description}")
            logger.info(f"  - signature_type: {signature_type}")
            logger.info(f"  - current_user_id: {current_user_id}")
            
            # Validate input parameters
            if not document:
                logger.error("Missing document in request")
                raise HTTPException(status_code=422, detail="Document file is required")
                
            if signature_type not in ["qualified", "advanced", "standard"]:
                logger.error(f"Invalid signature_type: {signature_type}")
                raise HTTPException(status_code=422, detail="Invalid signature type")
            
            # Read document content
            document_content = await document.read()
            logger.info(f"Successfully read document content: {len(document_content)} bytes")
            
            # Create signature
            document_service = DocumentService(db)
            signature = document_service.create_signature(
                document_content=document_content,
                document_name=document.filename,
                description=description,
                user_id=current_user_id,
                signature_type=signature_type
            )
            logger.info(f"Document signature created successfully: {signature.id}")
            
            return SignatureResponse(
                id=signature.id,
                document_name=signature.document_name,
                signature_timestamp=signature.created_at,
                signature_type=signature.signature_type,
                status="completed"
            )
        except Exception as e:
            error_msg = f"Error signing document: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=error_msg)
    
    @router.post(
        "/batch",
        response_model=List[SignatureResponse],
        summary="Sign multiple documents",
        description="Digitally sign multiple documents in a batch operation"
    )
    @rate_limit(limit_per_minute=5)
    async def sign_batch(
        request: BatchSignatureRequest,
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Digitally sign multiple documents in a batch operation.
        
        Args:
            request: Batch signature request containing document IDs and options
            db: Database session
            current_user_id: ID of the current user
            
        Returns:
            List[SignatureResponse]: Information about each created signature
        """
        try:
            document_service = DocumentService(db)
            signatures = []
            
            for document_id in request.document_ids:
                # Get document from storage
                document = document_service.get_document(document_id)
                
                if not document:
                    logger.warning(f"Document not found: {document_id}")
                    signatures.append(SignatureResponse(
                        id=None,
                        document_name=f"Document {document_id}",
                        signature_timestamp=None,
                        signature_type=request.signature_type,
                        status="failed",
                        error=f"Document not found: {document_id}"
                    ))
                    continue
                
                # Create signature
                signature = document_service.create_signature(
                    document_content=document.content,
                    document_name=document.name,
                    description=request.description,
                    user_id=current_user_id,
                    signature_type=request.signature_type
                )
                
                signatures.append(SignatureResponse(
                    id=signature.id,
                    document_name=signature.document_name,
                    signature_timestamp=signature.created_at,
                    signature_type=signature.signature_type,
                    status="completed"
                ))
            
            return signatures
        except Exception as e:
            logger.error(f"Error in batch signing: {e}")
            raise HTTPException(status_code=500, detail=f"Error in batch signing: {str(e)}")
    
    @router.get(
        "/certificate",
        summary="Get signing certificate",
        description="Get the certificate used for document signing"
    )
    async def get_signing_certificate():
        """
        Get the certificate used for document signing.
        
        This endpoint returns the public certificate used for document signing,
        encoded in PEM format. This certificate can be used to verify signatures.
        
        Returns:
            dict: Certificate in PEM format
        """
        try:
            certificate = get_certificate("document_signing")
            pem_cert = certificate.public_bytes(
                encoding=serialization.Encoding.PEM
            ).decode('utf-8')
            
            return {
                "certificate": pem_cert,
                "issuer": {
                    "organization": certificate.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value,
                    "common_name": certificate.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
                },
                "valid_from": certificate.not_valid_before,
                "valid_until": certificate.not_valid_after
            }
        except Exception as e:
            logger.error(f"Error getting signing certificate: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting signing certificate: {str(e)}")
    
    return router
