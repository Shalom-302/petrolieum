"""
Security utilities for the offline synchronization plugin.

Provides standardized encryption, hashing, and data validation functions.
"""

import os
import json
import logging
import hashlib
import hmac
import base64
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from app.core.config import settings

logger = logging.getLogger(__name__)


class SyncSecurity:
    """Security utilities for offline synchronization."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize the security manager.
        
        Args:
            encryption_key: Optional encryption key (will use settings if not provided)
        """
        self.encryption_key = encryption_key or settings.SECRET_KEY
        self._fernet = None
        
    @property
    def fernet(self):
        """Lazy-load encryption key."""
        if self._fernet is None:
            # Derive a key from the secret key
            salt = b'kaapi_offline_sync_salt'  # In production, this should be securely stored
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.encryption_key.encode()))
            self._fernet = Fernet(key)
        return self._fernet
        
    def encrypt_data(self, data: Any) -> Dict[str, Any]:
        """
        Encrypt data for secure storage.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Dict with encrypted data and metadata
        """
        # Convert data to JSON string
        data_str = json.dumps(data)
        
        # Encrypt the data
        encrypted_data = self.fernet.encrypt(data_str.encode())
        
        # Create a data signature for integrity verification
        signature = self._create_signature(data_str)
        
        logger.debug(f"Data encrypted successfully")
        
        return {
            "encrypted_data": base64.b64encode(encrypted_data).decode(),
            "metadata": {
                "encryption_method": "fernet",
                "signature": signature,
                "timestamp": str(int(os.times().elapsed))
            }
        }
        
    def decrypt_data(self, encrypted_package: Dict[str, Any]) -> Any:
        """
        Decrypt data from secure storage.
        
        Args:
            encrypted_package: Dict with encrypted data and metadata
            
        Returns:
            Decrypted data
        """
        try:
            # Get encrypted data and decode from base64
            encrypted_data = base64.b64decode(encrypted_package["encrypted_data"])
            
            # Decrypt the data
            decrypted_data_str = self.fernet.decrypt(encrypted_data).decode()
            
            # Verify data integrity with signature
            expected_signature = self._create_signature(decrypted_data_str)
            actual_signature = encrypted_package.get("metadata", {}).get("signature")
            
            if actual_signature and not hmac.compare_digest(expected_signature, actual_signature):
                logger.warning("Data integrity verification failed - signature mismatch")
                raise ValueError("Data integrity verification failed")
                
            # Parse the JSON string back to the original data
            decrypted_data = json.loads(decrypted_data_str)
            
            logger.debug(f"Data decrypted successfully")
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Error decrypting data: {str(e)}")
            raise
            
    def _create_signature(self, data_str: str) -> str:
        """
        Create a signature for data integrity verification.
        
        Args:
            data_str: String data to sign
            
        Returns:
            Base64-encoded signature
        """
        key = self.encryption_key.encode()
        h = hmac.new(key, data_str.encode(), hashlib.sha256)
        return base64.b64encode(h.digest()).decode()
        
    def validate_payload(self, payload: Dict[str, Any], required_fields: list = None) -> bool:
        """
        Validate that a payload contains required fields and sanitize content.
        
        Args:
            payload: Data payload to validate
            required_fields: List of required field names
            
        Returns:
            True if valid, False otherwise
        """
        if not payload:
            logger.warning("Empty payload received")
            return False
            
        if required_fields:
            missing_fields = [field for field in required_fields if field not in payload]
            if missing_fields:
                logger.warning(f"Payload missing required fields: {', '.join(missing_fields)}")
                return False
                
        # Sanitize payload - in a real implementation this would do more
        # such as check for injection attacks, XSS, etc.
        if any(self._contains_injection(str(v)) for v in payload.values()):
            logger.warning(f"Payload contains potentially malicious content")
            return False
            
        return True
        
    def _contains_injection(self, value: str) -> bool:
        """
        Simple check for basic injection patterns.
        
        Args:
            value: String to check
            
        Returns:
            True if suspicious patterns found, False otherwise
        """
        suspicious_patterns = [
            "UNION SELECT", 
            "OR 1=1", 
            "<script>",
            "javascript:",
            "EXEC(",
            "eval("
        ]
        
        lowercase_value = value.lower()
        return any(pattern.lower() in lowercase_value for pattern in suspicious_patterns)


# Singleton instance
sync_security = SyncSecurity()
