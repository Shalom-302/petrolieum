"""
Security utilities for digital signatures.

This module contains security-related utility functions for the
digital signature plugin, implementing the standardized security approach
used across the application.
"""

import logging
import os
import secrets
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID
import datetime

from app.core.security import (
    create_encryption_handler, 
    EncryptionHandler,
    create_default_encryption
)

logger = logging.getLogger(__name__)

# Module-level variables
_signature_security_initialized = False
_signature_encryption_handler = None
_key_pairs = {}
_certificates = {}


def initialize_signature_security(secret_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Initialize security utilities for the digital signature plugin.
    
    This function sets up encryption handlers, key pairs, and other security
    utilities needed by the digital signature plugin. It follows the
    standardized security approach used across the application.
    
    Args:
        secret_key: Optional custom secret key for encryption
        
    Returns:
        Dict[str, Any]: Initialization status
    """
    global _signature_security_initialized, _signature_encryption_handler
    
    if _signature_security_initialized:
        logger.info("Digital signature security already initialized")
        return {"status": "already_initialized"}
        
    try:
        # Use provided secret key or generate a new one
        if not secret_key:
            # Use application default or generate a new one
            logger.info("Using default encryption for digital signatures")
            _signature_encryption_handler = create_default_encryption()
        else:
            # Use custom encryption with the provided secret key
            logger.info("Using custom encryption for digital signatures")
            _signature_encryption_handler = create_encryption_handler(secret_key)
            
        # Initialize RSA key pairs and certificates if they don't exist
        _init_key_pairs()
            
        _signature_security_initialized = True
        logger.info("Digital signature security initialized successfully")
        return {"status": "initialized"}
    except Exception as e:
        logger.error(f"Failed to initialize digital signature security: {e}")
        raise


def _init_key_pairs():
    """Initialize RSA key pairs and certificates for digital signatures."""
    global _key_pairs, _certificates
    
    # Create different key pairs for different purposes if they don't exist
    if not _key_pairs.get("document_signing"):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        _key_pairs["document_signing"] = {
            "private": private_key,
            "public": private_key.public_key()
        }
        
        # Generate a self-signed certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "KAAPI Application"),
            x509.NameAttribute(NameOID.COMMON_NAME, "digital-signature.kaapi.app"),
        ])
        
        certificate = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName("digital-signature.kaapi.app")]),
            critical=False,
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        _certificates["document_signing"] = certificate
        
        logger.info("Generated RSA key pair and certificate for document signing")
    
    if not _key_pairs.get("timestamping"):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        _key_pairs["timestamping"] = {
            "private": private_key,
            "public": private_key.public_key()
        }
        
        # Generate a self-signed certificate for timestamping
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "KAAPI Timestamping Authority"),
            x509.NameAttribute(NameOID.COMMON_NAME, "timestamp.kaapi.app"),
        ])
        
        certificate = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName("timestamp.kaapi.app")]),
            critical=False,
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        _certificates["timestamping"] = certificate
        
        logger.info("Generated RSA key pair and certificate for timestamping")


def get_signature_encryption_handler() -> EncryptionHandler:
    """
    Get the encryption handler for digital signatures.
    
    Returns:
        EncryptionHandler: Encryption handler for digital signatures
        
    Note:
        This will initialize security if not already initialized.
    """
    global _signature_security_initialized, _signature_encryption_handler
    
    if not _signature_security_initialized:
        initialize_signature_security()
        
    return _signature_encryption_handler


def encrypt_signature_data(data: Dict[str, Any]) -> str:
    """
    Encrypt sensitive signature data.
    
    Args:
        data: Data to encrypt
        
    Returns:
        str: Encrypted data
    """
    handler = get_signature_encryption_handler()
    return handler.encrypt(str(data))


def decrypt_signature_data(encrypted_data: str) -> Dict[str, Any]:
    """
    Decrypt sensitive signature data.
    
    Args:
        encrypted_data: Encrypted data to decrypt
        
    Returns:
        Dict[str, Any]: Decrypted data
    """
    handler = get_signature_encryption_handler()
    decrypted = handler.decrypt(encrypted_data)
    # Convert string representation back to dictionary (simplified for example)
    # In a real implementation, you'd use a proper serialization format
    return eval(decrypted)


def get_key_pair(purpose: str = "document_signing"):
    """
    Get a key pair for the specified purpose.
    
    Args:
        purpose: Purpose of the key pair (e.g., "document_signing", "timestamping")
        
    Returns:
        Dict with "private" and "public" keys
    """
    global _key_pairs
    
    if not _signature_security_initialized:
        initialize_signature_security()
        
    if purpose not in _key_pairs:
        raise ValueError(f"No key pair found for purpose: {purpose}")
        
    return _key_pairs[purpose]


def get_certificate(purpose: str = "document_signing"):
    """
    Get a certificate for the specified purpose.
    
    Args:
        purpose: Purpose of the certificate (e.g., "document_signing", "timestamping")
        
    Returns:
        x509.Certificate: Certificate for the specified purpose
    """
    global _certificates
    
    if not _signature_security_initialized:
        initialize_signature_security()
        
    if purpose not in _certificates:
        raise ValueError(f"No certificate found for purpose: {purpose}")
        
    return _certificates[purpose]


def sign_data(data: bytes, purpose: str = "document_signing") -> bytes:
    """
    Sign data using RSA-PSS.
    
    Args:
        data: Data to sign
        purpose: Purpose of the key to use for signing
        
    Returns:
        bytes: Signature
    """
    key_pair = get_key_pair(purpose)
    private_key = key_pair["private"]
    
    signature = private_key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    return signature


def verify_signature(data: bytes, signature: bytes, purpose: str = "document_signing") -> bool:
    """
    Verify a signature using RSA-PSS.
    
    Args:
        data: Original data that was signed
        signature: Signature to verify
        purpose: Purpose of the key used for signing
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        key_pair = get_key_pair(purpose)
        public_key = key_pair["public"]
        
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


def create_timestamp(data: bytes) -> Dict[str, Any]:
    """
    Create a secure timestamp for data.
    
    Args:
        data: Data to timestamp
        
    Returns:
        Dict with timestamp information
    """
    # Create a timestamp with current time
    timestamp = datetime.datetime.utcnow().isoformat()
    
    # Hash the data
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(data)
    data_hash = digest.finalize()
    
    # Sign the hash and timestamp
    timestamp_data = timestamp.encode() + data_hash
    signature = sign_data(timestamp_data, purpose="timestamping")
    
    return {
        "timestamp": timestamp,
        "data_hash": data_hash.hex(),
        "signature": signature.hex()
    }


def verify_timestamp(data: bytes, timestamp_info: Dict[str, Any]) -> bool:
    """
    Verify a timestamp for data.
    
    Args:
        data: Original data
        timestamp_info: Timestamp information returned by create_timestamp
        
    Returns:
        bool: True if timestamp is valid, False otherwise
    """
    try:
        # Hash the data
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(data)
        data_hash = digest.finalize()
        
        # Check if the hash matches
        if data_hash.hex() != timestamp_info["data_hash"]:
            return False
            
        # Verify the signature
        timestamp_data = timestamp_info["timestamp"].encode() + bytes.fromhex(timestamp_info["data_hash"])
        return verify_signature(
            timestamp_data, 
            bytes.fromhex(timestamp_info["signature"]),
            purpose="timestamping"
        )
    except Exception:
        return False
