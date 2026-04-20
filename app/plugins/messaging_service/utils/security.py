"""
Security Utilities for Messaging Service

This module implements security functions for the messaging service plugin,
following the standardized security approach used across KAAPI plugins.
"""
import logging
import json
import hashlib
import base64
import os
from typing import Dict, Any, Optional
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class MessageSecurity:
    """
    Security handler for messaging service plugin, implementing the standardized
    approach for encryption, data protection, and secure logging.
    """
    
    def __init__(self, encryption_handler=None):
        """
        Initialize security handler with the application's core encryption handler.
        
        Args:
            encryption_handler: The application's encryption handler instance
        """
        self.encryption_handler = encryption_handler
        self._conversation_keys = {}  # Cache for conversation keys
    
    def encrypt_message(self, message_content: str, recipient_id: str) -> str:
        """
        Encrypt a message for a specific recipient using the standardized approach.
        
        Args:
            message_content: The content to encrypt
            recipient_id: ID of the recipient
            
        Returns:
            Encrypted message content
        """
        if not self.encryption_handler:
            logger.warning("Encryption handler not available, message not encrypted")
            return message_content
            
        # Use the application's encryption handler if available
        try:
            return self.encryption_handler.encrypt_sensitive_data(
                message_content, 
                context={"recipient_id": recipient_id}
            )
        except Exception as e:
            logger.error(f"Error using encryption handler: {str(e)}")
            # Fallback to basic encryption
            return self._fallback_encrypt(message_content, recipient_id)
    
    def decrypt_message(self, encrypted_content: str, user_id: str) -> str:
        """
        Decrypt a message for a specific user using the standardized approach.
        
        Args:
            encrypted_content: The encrypted content
            user_id: ID of the user who should decrypt the message
            
        Returns:
            Decrypted message content
        """
        if not self.encryption_handler:
            logger.warning("Encryption handler not available, assuming message is not encrypted")
            return encrypted_content
            
        # Use the application's encryption handler if available
        try:
            return self.encryption_handler.decrypt_sensitive_data(
                encrypted_content,
                context={"user_id": user_id}
            )
        except Exception as e:
            logger.error(f"Error using encryption handler: {str(e)}")
            # Fallback to basic decryption
            return self._fallback_decrypt(encrypted_content, user_id)
    
    def _fallback_encrypt(self, data: str, context_id: str) -> str:
        """
        Fallback encryption method when the application's handler is unavailable.
        
        Args:
            data: Data to encrypt
            context_id: Contextual ID to derive encryption key
            
        Returns:
            Encrypted data string
        """
        key = self._derive_key(context_id)
        iv = os.urandom(16)
        
        # Pad the data
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data.encode('utf-8')) + padder.finalize()
        
        # Encrypt the data
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine IV and encrypted data and encode to base64
        result = base64.b64encode(iv + encrypted_data).decode('utf-8')
        return result
    
    def _fallback_decrypt(self, encrypted_data: str, context_id: str) -> str:
        """
        Fallback decryption method when the application's handler is unavailable.
        
        Args:
            encrypted_data: Encrypted data string
            context_id: Contextual ID to derive decryption key
            
        Returns:
            Decrypted data string
        """
        key = self._derive_key(context_id)
        
        # Decode from base64
        data = base64.b64decode(encrypted_data.encode('utf-8'))
        
        # Extract IV (first 16 bytes) and encrypted data
        iv = data[:16]
        ciphertext = data[16:]
        
        # Decrypt the data
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Unpad the data
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        
        return data.decode('utf-8')
    
    def _derive_key(self, context_id: str) -> bytes:
        """
        Derive an encryption key from a context ID.
        
        Args:
            context_id: ID to use for key derivation
            
        Returns:
            32-byte key for AES-256
        """
        # Simple key derivation using SHA-256
        key_material = f"messaging_service_{context_id}".encode('utf-8')
        return hashlib.sha256(key_material).digest()
    
    def validate_message_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validate message request data for security issues.
        
        Args:
            request_data: Request data to validate
            
        Returns:
            True if request is valid, False otherwise
        """
        # Check content length to prevent abuse
        if "content" in request_data and isinstance(request_data["content"], str):
            if len(request_data["content"]) > 5000:  # 5KB limit
                logger.warning("Message content too large", 
                              extra={"length": len(request_data["content"])})
                return False
                
        # Check for suspicious patterns (XSS, injections, etc.)
        if "content" in request_data and isinstance(request_data["content"], str):
            suspicious_patterns = [
                "<script", 
                "javascript:", 
                "onerror=", 
                "SELECT * FROM", 
                "DROP TABLE",
                "UNION SELECT"
            ]
            for pattern in suspicious_patterns:
                if pattern.lower() in request_data["content"].lower():
                    logger.warning("Suspicious pattern detected in message", 
                                  extra={"pattern": pattern})
                    return False
        
        # Additional validation logic can be added here
        
        return True
    
    def secure_log(self, message: str, data: Dict[str, Any], level: str = "info"):
        """
        Securely log events with sensitive data protected.
        
        Args:
            message: Log message
            data: Data to log (will be protected)
            level: Log level ('info', 'warning', 'error')
        """
        # Hash or remove any sensitive fields
        secure_data = data.copy()
        
        # Protect user identifiers
        sensitive_fields = ["user_id", "sender_id", "recipient_id", "blocked_id", "blocker_id"]
        for field in sensitive_fields:
            if field in secure_data:
                secure_data[f"{field}_hash"] = self.hash_identifier(str(secure_data[field]))
                del secure_data[field]
            
        # Protect message content
        if "content" in secure_data:
            secure_data["content_length"] = len(secure_data["content"])
            del secure_data["content"]
            
        # Add timestamp
        secure_data["timestamp"] = datetime.utcnow().isoformat()
        
        # Log with appropriate level
        if level == "warning":
            logger.warning(message, extra=secure_data)
        elif level == "error":
            logger.error(message, extra=secure_data)
        else:
            logger.info(message, extra=secure_data)
    
    def hash_identifier(self, identifier: str) -> str:
        """
        Create a secure hash of an identifier for logging.
        
        Args:
            identifier: Identifier to hash
            
        Returns:
            Hashed identifier
        """
        if self.encryption_handler and hasattr(self.encryption_handler, "hash_sensitive_data"):
            return self.encryption_handler.hash_sensitive_data(identifier)
            
        # Fallback if encryption handler not available
        salt = "messaging_service_salt"
        return hashlib.sha256(f"{identifier}{salt}".encode()).hexdigest()
        
    def encrypt_metadata(self, metadata: Dict[str, Any]) -> str:
        """
        Encrypt metadata using the standardized approach.
        
        Args:
            metadata: Dictionary containing metadata
            
        Returns:
            Encrypted metadata string
        """
        if not metadata:
            return ""
            
        metadata_str = json.dumps(metadata)
        
        if self.encryption_handler:
            return self.encryption_handler.encrypt_sensitive_data(metadata_str)
            
        # Fallback encryption
        return self._fallback_encrypt(metadata_str, "metadata")
        
    def decrypt_metadata(self, encrypted_metadata: str) -> Dict[str, Any]:
        """
        Decrypt metadata using the standardized approach.
        
        Args:
            encrypted_metadata: Encrypted metadata string
            
        Returns:
            Dictionary containing decrypted metadata
        """
        if not encrypted_metadata:
            return {}
            
        if self.encryption_handler:
            decrypted = self.encryption_handler.decrypt_sensitive_data(encrypted_metadata)
        else:
            # Fallback decryption
            decrypted = self._fallback_decrypt(encrypted_metadata, "metadata")
            
        return json.loads(decrypted)
        
    def generate_conversation_key(self, conversation_id: str) -> str:
        """
        Generate a secure key for a conversation.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            Secure conversation key
        """
        random_bytes = os.urandom(32)
        key_material = f"{conversation_id}_{base64.b64encode(random_bytes).decode()}"
        return hashlib.sha256(key_material.encode()).hexdigest()
        
    def store_conversation_key(self, conversation_id: str, key: str):
        """
        Store a conversation encryption key.
        
        Args:
            conversation_id: ID of the conversation
            key: Encryption key
        """
        # In a real implementation, this should be stored securely
        # For now, we'll just cache it in memory
        self._conversation_keys[conversation_id] = key
        
    def get_conversation_key(self, conversation_id: str) -> Optional[str]:
        """
        Get a stored conversation encryption key.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            Encryption key if found, None otherwise
        """
        return self._conversation_keys.get(conversation_id)
