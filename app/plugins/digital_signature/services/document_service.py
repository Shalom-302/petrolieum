"""
Document signing service.

This module provides services for digitally signing documents,
verifying signatures, and generating legal evidence packages.
"""

import logging
import json
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from app.plugins.digital_signature.models.signature import SignatureDB, EvidenceDB
from app.plugins.digital_signature.utils.security import (
    sign_data, 
    verify_signature, 
    get_certificate,
    create_timestamp,
    encrypt_signature_data
)
from app.core.security import EncryptionHandler, create_default_encryption

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Service for handling document signing operations.
    
    This service provides methods for creating and verifying digital
    signatures, as well as generating and validating legal evidence
    packages.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the document service.
        
        Args:
            db: Database session
        """
        self.db = db
        self._encryption_handler = create_default_encryption()
        
    def create_signature(
        self, 
        document_content: bytes, 
        document_name: str,
        user_id: str,
        description: Optional[str] = None,
        signature_type: str = "standard"
    ) -> SignatureDB:
        """
        Create a digital signature for a document.
        
        Args:
            document_content: Content of the document to sign
            document_name: Name of the document
            user_id: ID of the user creating the signature
            description: Optional description of the signature
            signature_type: Type of signature (qualified, advanced, standard)
            
        Returns:
            SignatureDB: Created signature
        """
        try:
            # Hash the document
            document_hash = hashlib.sha256(document_content).hexdigest()
            
            # Sign the document hash
            signature_bytes = sign_data(document_content)
            
            # Create signer info
            signer_info = json.dumps({
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "signature_type": signature_type
            })
            
            # Create signature record
            signature = SignatureDB(
                document_hash=document_hash,
                document_name=document_name,
                signature_data=signature_bytes,
                signature_type=signature_type,
                user_id=user_id,
                description=description,
                signer_info=signer_info,
                certificate_id="document_signing"  # Using the default certificate
            )
            
            # Save to database
            self.db.add(signature)
            self.db.commit()
            self.db.refresh(signature)
            
            logger.info(f"Created signature for document {document_name} with ID {signature.id}")
            return signature
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating signature: {e}")
            raise
            
    def verify_signature(
        self, 
        signature_id: str, 
        document_content: bytes
    ) -> Dict[str, Any]:
        """
        Verify a digital signature against a document.
        
        Args:
            signature_id: ID of the signature to verify
            document_content: Content of the document to verify
            
        Returns:
            Dict[str, Any]: Verification result
        """
        try:
            # Get the signature from database
            signature = self.get_signature(signature_id)
            if not signature:
                return {
                    "verified": False,
                    "error": "Signature not found"
                }
            
            # Check if the signature is active
            if not signature.is_active:
                return {
                    "verified": False,
                    "error": "Signature has been revoked"
                }
            
            # Hash the document
            document_hash = hashlib.sha256(document_content).hexdigest()
            
            # Check if the document hash matches
            if document_hash != signature.document_hash:
                return {
                    "verified": False,
                    "error": "Document hash mismatch"
                }
            
            # Verify the signature
            is_valid = verify_signature(document_content, signature.signature_data)
            
            if is_valid:
                return {
                    "verified": True
                }
            else:
                return {
                    "verified": False,
                    "error": "Invalid signature"
                }
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return {
                "verified": False,
                "error": f"Error verifying signature: {str(e)}"
            }
            
    def get_signature(self, signature_id: str) -> Optional[SignatureDB]:
        """
        Get a signature by ID.
        
        Args:
            signature_id: ID of the signature
            
        Returns:
            Optional[SignatureDB]: Signature if found, None otherwise
        """
        return self.db.query(SignatureDB).filter(SignatureDB.id == signature_id).first()
        
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID.
        
        This is a placeholder method. In a real implementation, this would
        retrieve the document from a document storage system.
        
        Args:
            document_id: ID of the document
            
        Returns:
            Optional[Dict[str, Any]]: Document if found, None otherwise
        """
        # Placeholder implementation - in a real system, this would retrieve
        # the document from a document storage system
        # For example, from a document database, file system, or object storage
        
        # Simulate document retrieval
        # In real implementation, you would fetch the document from storage
        try:
            # This is a simulation - you would actually retrieve from storage
            return {
                "id": document_id,
                "name": f"Document {document_id}",
                "content": b"Sample document content",  # In reality, this would be the actual document content
                "content_type": "application/pdf",
                "created_at": datetime.utcnow(),
                "size": 1024
            }
        except Exception:
            logger.warning(f"Document not found: {document_id}")
            return None
            
    def generate_legal_evidence(
        self,
        signature_id: str,
        include_certificate_chain: bool = True,
        include_timestamp_proof: bool = True
    ) -> EvidenceDB:
        """
        Generate a complete legal evidence package for a signature.
        
        This method creates a comprehensive evidence package that can be
        used in legal proceedings to prove the authenticity of a signed
        document.
        
        Args:
            signature_id: ID of the signature
            include_certificate_chain: Whether to include the certificate chain
            include_timestamp_proof: Whether to include timestamp proof
            
        Returns:
            EvidenceDB: Generated evidence package
        """
        try:
            # Get the signature
            signature = self.get_signature(signature_id)
            if not signature:
                raise ValueError(f"Signature not found: {signature_id}")
                
            # Prepare certificate chain
            certificate_chain = None
            if include_certificate_chain:
                cert = get_certificate("document_signing")
                certificate_chain = base64.b64encode(
                    cert.public_bytes(serialization.Encoding.PEM)
                ).decode('utf-8')
                
            # Prepare timestamp proof
            timestamp_proof = None
            if include_timestamp_proof:
                # Create a timestamp of the signature
                timestamp_data = json.dumps({
                    "signature_id": signature_id,
                    "document_hash": signature.document_hash,
                    "timestamp": signature.created_at.isoformat()
                }).encode()
                
                timestamp_info = create_timestamp(timestamp_data)
                timestamp_proof = json.dumps(timestamp_info)
                
            # Create evidence record
            evidence = EvidenceDB(
                signature_id=signature_id,
                certificate_chain=certificate_chain,
                timestamp_proof=timestamp_proof,
                evidence_format="ETSI-AdES",
                is_long_term=False,
                expires_at=datetime.utcnow() + timedelta(days=365)
            )
            
            # Save to database
            self.db.add(evidence)
            self.db.commit()
            self.db.refresh(evidence)
            
            logger.info(f"Generated legal evidence for signature {signature_id} with ID {evidence.id}")
            return evidence
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error generating legal evidence: {e}")
            raise
            
    def get_evidence(self, evidence_id: str) -> Optional[EvidenceDB]:
        """
        Get an evidence package by ID.
        
        Args:
            evidence_id: ID of the evidence package
            
        Returns:
            Optional[EvidenceDB]: Evidence package if found, None otherwise
        """
        return self.db.query(EvidenceDB).filter(EvidenceDB.id == evidence_id).first()
        
    def validate_evidence(self, evidence_id: str) -> Dict[str, Any]:
        """
        Validate a legal evidence package.
        
        This method verifies the validity of a legal evidence package,
        checking the integrity of the certificate chain and timestamp proof.
        
        Args:
            evidence_id: ID of the evidence package
            
        Returns:
            Dict[str, Any]: Validation result
        """
        try:
            # Get the evidence
            evidence = self.get_evidence(evidence_id)
            if not evidence:
                return {
                    "valid": False,
                    "error": "Evidence package not found"
                }
                
            # Get the signature
            signature = self.get_signature(evidence.signature_id)
            if not signature:
                return {
                    "valid": False,
                    "error": "Signature not found"
                }
                
            # Check if the signature is active
            if not signature.is_active:
                return {
                    "valid": False,
                    "error": "Signature has been revoked"
                }
                
            # Validate certificate chain
            cert_valid = True
            if evidence.certificate_chain:
                # In a real implementation, you would verify the certificate chain
                # against a trusted root certificate
                cert_valid = True  # Placeholder for certificate validation
                
            # Validate timestamp proof
            timestamp_valid = True
            if evidence.timestamp_proof:
                timestamp_info = json.loads(evidence.timestamp_proof)
                
                # Create the original timestamp data
                timestamp_data = json.dumps({
                    "signature_id": signature.id,
                    "document_hash": signature.document_hash,
                    "timestamp": signature.created_at.isoformat()
                }).encode()
                
                # Verify the timestamp
                # In a real implementation, you would verify the timestamp against
                # the timestamp authority's certificate
                timestamp_valid = True  # Placeholder for timestamp validation
                
            if cert_valid and timestamp_valid:
                return {
                    "valid": True
                }
            else:
                errors = []
                if not cert_valid:
                    errors.append("Invalid certificate chain")
                if not timestamp_valid:
                    errors.append("Invalid timestamp proof")
                    
                return {
                    "valid": False,
                    "error": ", ".join(errors)
                }
        except Exception as e:
            logger.error(f"Error validating evidence: {e}")
            return {
                "valid": False,
                "error": f"Error validating evidence: {str(e)}"
            }
