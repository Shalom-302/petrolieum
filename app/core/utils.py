"""
Core utility functions for the application.

This module provides commonly used utility functions across the application.
"""

import uuid
from typing import Optional, Any, Dict
import json
import base64
from datetime import datetime
import secrets
import hashlib
import logging

logger = logging.getLogger(__name__)

def generate_uuid() -> str:
    """
    Generate a random UUID string.
    
    Returns:
        str: Random UUID string
    """
    return str(uuid.uuid4())

def generate_random_string(length: int = 32) -> str:
    """
    Generate a cryptographically secure random string.
    
    Args:
        length: Length of the random string
        
    Returns:
        str: Random string
    """
    return secrets.token_hex(length // 2)

def hash_data(data: str, salt: Optional[str] = None) -> str:
    """
    Create a secure hash of data.
    
    Args:
        data: Data to hash
        salt: Optional salt for the hash
        
    Returns:
        str: Hashed data
    """
    if salt is None:
        salt = secrets.token_hex(16)
        
    hash_obj = hashlib.sha256()
    hash_obj.update(f"{salt}{data}".encode())
    return f"{salt}:{hash_obj.hexdigest()}"

def verify_hash(data: str, hash_value: str) -> bool:
    """
    Verify if data matches a hash.
    
    Args:
        data: Data to verify
        hash_value: Hash to verify against
        
    Returns:
        bool: True if data matches hash
    """
    if ":" not in hash_value:
        return False
        
    salt, hash_part = hash_value.split(":", 1)
    
    hash_obj = hashlib.sha256()
    hash_obj.update(f"{salt}{data}".encode())
    return hash_obj.hexdigest() == hash_part

def encrypt_data(data: Dict[str, Any], key: Optional[str] = None) -> str:
    """
    Simple encryption for non-critical data.
    For sensitive data, use a proper encryption library.
    
    Args:
        data: Data to encrypt
        key: Optional encryption key
        
    Returns:
        str: Encrypted data
    """
    # This is only meant for simple obfuscation, not secure encryption
    # Add timestamp to protect against replay attacks
    data["_timestamp"] = datetime.utcnow().isoformat()
    
    # Convert to JSON and base64 encode
    json_data = json.dumps(data)
    encoded = base64.b64encode(json_data.encode()).decode()
    
    if key:
        # Simple XOR encryption with key (for demonstration only)
        # Real implementations should use proper cryptographic libraries
        key_bytes = key.encode() * (len(encoded) // len(key) + 1)
        encrypted = ''.join(chr(ord(a) ^ ord(b)) for a, b in zip(encoded, key_bytes))
        return base64.b64encode(encrypted.encode()).decode()
    
    return encoded

def decrypt_data(encrypted_data: str, key: Optional[str] = None) -> Dict[str, Any]:
    """
    Decrypt data encrypted with encrypt_data.
    
    Args:
        encrypted_data: Encrypted data
        key: Optional decryption key
        
    Returns:
        Dict: Decrypted data
    """
    try:
        if key:
            # Decrypt with key
            encrypted = base64.b64decode(encrypted_data).decode()
            key_bytes = key.encode() * (len(encrypted) // len(key) + 1)
            decoded = ''.join(chr(ord(a) ^ ord(b)) for a, b in zip(encrypted, key_bytes))
        else:
            decoded = base64.b64decode(encrypted_data).decode()
            
        data = json.loads(decoded)
        
        # Check timestamp if available
        if "_timestamp" in data:
            timestamp = datetime.fromisoformat(data["_timestamp"])
            now = datetime.utcnow()
            
            # Reject if too old (more than 24 hours)
            if (now - timestamp).total_seconds() > 86400:
                logger.warning("Decrypted data is too old")
                return {}
                
        return data
    except Exception as e:
        logger.error(f"Error decrypting data: {str(e)}")
        return {}
