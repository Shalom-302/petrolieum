"""
Database models for digital signatures.

This module contains SQLAlchemy models for storing digital signatures
and related data in the database.
"""

import datetime
import uuid
from sqlalchemy import Column, String, DateTime, LargeBinary, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.core.db import Base


class SignatureDB(Base):
    """
    Database model for digital signatures.
    
    This model stores information about digitally signed documents,
    including references to the document content, signature data,
    and metadata about the signing process.
    """
    __tablename__ = "digital_signatures"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    document_hash = Column(String, nullable=False, index=True, comment="Hash of the signed document")
    document_name = Column(String, nullable=False, comment="Name of the original document")
    signature_data = Column(LargeBinary, nullable=False, comment="Raw signature data")
    signature_type = Column(String, nullable=False, default="standard", comment="Type of signature (qualified, advanced, standard)")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, comment="When the signature was created")
    user_id = Column(String, nullable=False, index=True, comment="User who created the signature")
    description = Column(Text, nullable=True, comment="Optional description of the signature")
    
    # Metadata about the signer
    signer_info = Column(String, nullable=True, comment="JSON-encoded information about the signer")
    
    # Relationships
    evidence = relationship("EvidenceDB", back_populates="signature", cascade="all, delete-orphan")
    
    # Public key used for this signature (optional, references the key store)
    certificate_id = Column(String, nullable=True, comment="Reference to the certificate used for signing")
    
    # Status information
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether the signature is active")
    revoked_at = Column(DateTime, nullable=True, comment="When the signature was revoked (if it was)")
    revocation_reason = Column(String, nullable=True, comment="Reason for revocation (if applicable)")
    

class EvidenceDB(Base):
    """
    Database model for legal evidence packages.
    
    This model stores comprehensive evidence packages that can be used
    in legal proceedings to prove the authenticity of signed documents.
    """
    __tablename__ = "digital_signature_evidence"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    signature_id = Column(String, ForeignKey("digital_signatures.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # Evidence components
    certificate_chain = Column(Text, nullable=True, comment="PEM-encoded certificate chain")
    timestamp_proof = Column(Text, nullable=True, comment="Timestamp proof data in JSON format")
    validation_data = Column(Text, nullable=True, comment="Additional validation data in JSON format")
    
    # Relationship to the signature
    signature = relationship("SignatureDB", back_populates="evidence")
    
    # Metadata
    evidence_format = Column(String, nullable=False, default="ETSI-AdES", comment="Format of the evidence package")
    is_long_term = Column(Boolean, default=False, nullable=False, comment="Whether this is a long-term preservation evidence")
    expires_at = Column(DateTime, nullable=True, comment="When the evidence expires (if applicable)")
