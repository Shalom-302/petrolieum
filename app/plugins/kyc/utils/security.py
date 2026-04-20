"""
Security utilities for the KYC plugin.

This module provides security functions for handling sensitive KYC data,
including encryption, validation, and audit logging.
"""

import logging
import hashlib
import hmac
import json
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings
from app.core.security import create_hmac_signature, verify_hmac_signature

logger = logging.getLogger(__name__)


class KycSecurity:
    """Security handler for KYC operations."""
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize the KYC security handler.
        
        Args:
            secret_key: Optional custom secret key
        """
        self.secret_key = secret_key or settings.SECRET_KEY
        self._setup_encryption()
        logger.info("KYC Security initialized")
    
    def _setup_encryption(self) -> None:
        """Set up the encryption components."""
        # For demonstration, we derive a key from the secret key
        # In production, use a proper key management solution
        salt = b'kyc_secure_salt'  # In production, store this securely
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))
        self.cipher = Fernet(key)
    
    def encrypt_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive data in a dictionary.
        
        Args:
            data: Dictionary containing data to encrypt
            
        Returns:
            Dictionary with encrypted data and metadata
        """
        if not data:
            return {}
            
        # Serialize the data to JSON
        serialized = json.dumps(data)
        
        # Generate a signature before encryption for integrity checking
        signature = create_hmac_signature(serialized, self.secret_key)
        
        # Encrypt the data
        encrypted_data = self.cipher.encrypt(serialized.encode())
        
        # Create metadata for decryption
        metadata = {
            "algorithm": "Fernet",
            "created_at": datetime.utcnow().isoformat(),
            "signature": signature,
        }
        
        return {
            "encrypted_data": base64.urlsafe_b64encode(encrypted_data).decode(),
            "metadata": metadata
        }
    
    def decrypt_data(self, encrypted_package: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt data that was encrypted with encrypt_data.
        
        Args:
            encrypted_package: Dictionary with encrypted data and metadata
            
        Returns:
            Original dictionary with decrypted data
        """
        if not encrypted_package or "encrypted_data" not in encrypted_package:
            return {}
            
        try:
            # Get the encrypted data
            encrypted_data = base64.urlsafe_b64decode(encrypted_package["encrypted_data"])
            
            # Decrypt the data
            decrypted_data = self.cipher.decrypt(encrypted_data).decode()
            
            # Verify the signature to ensure integrity
            if "metadata" in encrypted_package and "signature" in encrypted_package["metadata"]:
                signature = encrypted_package["metadata"]["signature"]
                if not verify_hmac_signature(decrypted_data, signature, self.secret_key):
                    logger.warning("Data integrity check failed during decryption")
                    return {}
            
            # Parse the JSON
            return json.loads(decrypted_data)
            
        except Exception as e:
            logger.error(f"Error decrypting data: {str(e)}")
            return {}
    
    def mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask sensitive data for logging or public display.
        
        Args:
            data: Dictionary containing data to mask
            
        Returns:
            Dictionary with masked sensitive fields
        """
        if not data:
            return {}
            
        result = data.copy()
        
        # Fields to mask
        sensitive_fields = [
            "full_name", "date_of_birth", "tax_id", "passport_number",
            "id_number", "address", "phone_number", "email"
        ]
        
        for field in sensitive_fields:
            if field in result:
                if isinstance(result[field], str):
                    # Mask the middle part of the string
                    value = result[field]
                    if len(value) > 6:
                        visible_prefix = value[:2]
                        visible_suffix = value[-2:]
                        masked_length = len(value) - 4
                        result[field] = f"{visible_prefix}{'*' * masked_length}{visible_suffix}"
                    else:
                        result[field] = "******"
                elif isinstance(result[field], dict):
                    # For nested objects like address
                    result[field] = {"masked": True}
        
        return result
    
    def log_security_event(
        self, 
        event_type: str, 
        user_id: str, 
        action: str, 
        success: bool, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a security-related event.
        
        Args:
            event_type: Type of security event
            user_id: User ID associated with the event
            action: Action being performed
            success: Whether the action was successful
            metadata: Additional metadata for the event
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "success": success,
        }
        
        if metadata:
            # Make sure we don't log sensitive data
            safe_metadata = self.mask_sensitive_data(metadata)
            log_data["metadata"] = safe_metadata
        
        if success:
            logger.info(f"Security event: {json.dumps(log_data)}")
        else:
            logger.warning(f"Security event (FAILED): {json.dumps(log_data)}")


# Instantiate a global security handler for the KYC plugin
kyc_security = KycSecurity()


def initialize_kyc_security(secret_key: Optional[str] = None) -> None:
    """
    Initialize the KYC security subsystem with the specified secret key.
    
    This function should be called during plugin initialization to ensure
    that the security components are properly set up before any KYC
    operations are performed.
    
    Args:
        secret_key: Optional custom secret key. If not provided, 
                   the application's SECRET_KEY will be used.
    """
    global kyc_security
    kyc_security = KycSecurity(secret_key)
    logger.info("KYC Security subsystem initialized with custom configuration")
    
    # Log security initialization without sensitive details
    kyc_security.log_security_event(
        event_type="security_init",
        user_id="system",
        action="initialize_security",
        success=True,
        metadata={
            "timestamp": datetime.utcnow().isoformat(),
            "component": "kyc_plugin",
            "encryption_algorithm": "Fernet"
        }
    )


def encrypt_personal_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt personal data using the global KYC security handler.
    
    Args:
        data: Dictionary containing personal data to encrypt
        
    Returns:
        Dictionary with encrypted data and metadata
    """
    return kyc_security.encrypt_data(data)


def validate_document_data(
    document_type: str, 
    document_data: Dict[str, Any]
) -> bool:
    """
    Validate submitted document data.
    
    Args:
        document_type: Type of document
        document_data: Document data to validate
        
    Returns:
        True if document data is valid, False otherwise
    """
    # Basic validation for different document types
    if not document_data:
        return False
    
    if document_type == "passport":
        required_fields = ["passport_number", "issuing_country", "expiry_date"]
    elif document_type == "national_id":
        required_fields = ["id_number", "issuing_authority"]
    elif document_type == "drivers_license":
        required_fields = ["license_number", "issuing_authority", "expiry_date"]
    elif document_type == "utility_bill":
        required_fields = ["service_provider", "issue_date", "customer_name"]
    elif document_type == "third_party_reference":
        required_fields = ["reference_name", "contact_information", "relationship"]
    else:
        # For other document types, require at least an ID and issuer
        required_fields = ["document_id", "issuing_authority"]
    
    # Check if all required fields are present
    for field in required_fields:
        if field not in document_data:
            return False
            
    # Additional validation for specific document types could be added here
    
    return True


def _validate_passport(data: Dict[str, Any]) -> bool:
    """Validate passport data."""
    required_fields = ["passport_number", "country", "expiry_date"]
    return all(field in data for field in required_fields)


def _validate_national_id(data: Dict[str, Any]) -> bool:
    """Validate national ID data."""
    required_fields = ["id_number", "country"]
    return all(field in data for field in required_fields)


def _validate_drivers_license(data: Dict[str, Any]) -> bool:
    """Validate driver's license data."""
    required_fields = ["license_number", "issuing_authority", "expiry_date"]
    return all(field in data for field in required_fields)
