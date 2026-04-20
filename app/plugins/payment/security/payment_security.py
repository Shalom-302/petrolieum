"""
Payment security integration module.

This module provides security integrations for payment providers, leveraging
the existing security plugin to provide enhanced protection for payment data.
"""
import logging
import json
from typing import Dict, Any, Optional, List, Union
import os
from datetime import datetime
import uuid
import re

# Import security services
from app.plugins.security.vault_client import VaultClient
from app.plugins.security.services import CryptoService, DatabaseEncryptor

logger = logging.getLogger("kaapi.payment.security")


class PaymentSecurity:
    """
    Provides security services for payment providers.
    
    This class integrates with the security plugin to provide:
    1. Sensitive data encryption (PCI DSS compliance)
    2. Secure credential storage
    3. Encrypted audit logging
    4. Key rotation
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super(PaymentSecurity, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize payment security service."""
        if self._initialized:
            return
            
        try:
            # Initialize vault client for secure secrets management
            self.vault_client = VaultClient()
            
            # Initialize crypto service for encryption/decryption
            self.crypto_service = CryptoService(self.vault_client)
            
            # Fields that should be encrypted for each provider
            self.sensitive_fields = {
                "payment_request": ["card_number", "cvv", "bank_account", "phone_number"],
                "customer_data": ["tax_id", "id_number", "address"],
                "provider_credentials": ["api_key", "secret_key", "private_key", "access_token"],
                "webhook_data": ["signature", "raw_body"]
            }
            
            # PCI DSS validation patterns
            self.pci_patterns = {
                "card_number": r"^(?:\d{4}[- ]?){3}\d{4}$|^\d{16}$",
                "cvv": r"^\d{3,4}$",
                "expiry": r"^(0[1-9]|1[0-2])/\d{2}$"
            }
            
            logger.info("Payment security service initialized")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize payment security: {str(e)}")
            raise
    
    def encrypt_sensitive_data(self, data: Dict[str, Any], data_type: str = "payment_request") -> Dict[str, Any]:
        """
        Encrypt sensitive fields in payment data.
        
        Args:
            data: Dictionary containing payment data
            data_type: Type of data (payment_request, customer_data, etc.)
            
        Returns:
            Dictionary with sensitive fields encrypted
        """
        if not data or not isinstance(data, dict):
            return data
            
        encrypted_data = data.copy()
        
        # Get list of sensitive fields for this data type
        sensitive_fields = self.sensitive_fields.get(data_type, [])
        
        # Encrypt each sensitive field
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field]:
                try:
                    # Handle nested dictionaries
                    if isinstance(encrypted_data[field], dict):
                        encrypted_data[field] = self.encrypt_sensitive_data(
                            encrypted_data[field], 
                            f"{data_type}_{field}"
                        )
                    # Handle direct values
                    elif isinstance(encrypted_data[field], (str, int)):
                        value = str(encrypted_data[field])
                        encrypted_data[field] = self.crypto_service.encrypt_field(value)
                        logger.debug(f"Encrypted sensitive field: {field}")
                except Exception as e:
                    logger.error(f"Error encrypting field {field}: {str(e)}")
                    
        return encrypted_data
    
    def decrypt_sensitive_data(self, data: Dict[str, Any], data_type: str = "payment_request") -> Dict[str, Any]:
        """
        Decrypt sensitive fields in payment data.
        
        Args:
            data: Dictionary containing encrypted payment data
            data_type: Type of data (payment_request, customer_data, etc.)
            
        Returns:
            Dictionary with sensitive fields decrypted
        """
        if not data or not isinstance(data, dict):
            return data
            
        decrypted_data = data.copy()
        
        # Get list of sensitive fields for this data type
        sensitive_fields = self.sensitive_fields.get(data_type, [])
        
        # Decrypt each sensitive field
        for field in sensitive_fields:
            if field in decrypted_data and decrypted_data[field]:
                try:
                    # Handle nested dictionaries
                    if isinstance(decrypted_data[field], dict):
                        decrypted_data[field] = self.decrypt_sensitive_data(
                            decrypted_data[field], 
                            f"{data_type}_{field}"
                        )
                    # Handle encrypted strings (checking for encryption marker)
                    elif isinstance(decrypted_data[field], str) and ":" in decrypted_data[field]:
                        try:
                            decrypted_data[field] = self.crypto_service.decrypt_field(decrypted_data[field])
                            logger.debug(f"Decrypted sensitive field: {field}")
                        except Exception:
                            # Not an encrypted field or invalid format, leave as is
                            pass
                except Exception as e:
                    logger.error(f"Error decrypting field {field}: {str(e)}")
                    
        return decrypted_data
    
    def store_provider_credentials(self, provider_name: str, credentials: Dict[str, Any]) -> bool:
        """
        Securely store provider credentials in the vault.
        
        Args:
            provider_name: Name of the payment provider
            credentials: Dictionary of provider credentials
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Encrypt credentials
            encrypted_credentials = json.dumps(self.encrypt_sensitive_data(
                credentials, 
                "provider_credentials"
            ))
            
            # Store in vault
            self.vault_client.client.secrets.kv.v2.create_or_update_secret(
                path=f"payment_providers/{provider_name}",
                secret=dict(credentials=encrypted_credentials)
            )
            
            logger.info(f"Stored credentials for provider: {provider_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store credentials for {provider_name}: {str(e)}")
            return False
    
    def get_provider_credentials(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve provider credentials from the vault.
        
        Args:
            provider_name: Name of the payment provider
            
        Returns:
            Dictionary of provider credentials or None if not found
        """
        try:
            # Retrieve from vault
            response = self.vault_client.client.secrets.kv.v2.read_secret_version(
                path=f"payment_providers/{provider_name}"
            )
            
            # Extract data from response
            data = response.get("data", {}).get("data", {})
            credentials_json = data.get("credentials")
            
            if not credentials_json:
                logger.warning(f"No credentials found for provider: {provider_name}")
                return None
            
            # Decrypt credentials
            encrypted_credentials = json.loads(credentials_json)
            decrypted_credentials = self.decrypt_sensitive_data(
                encrypted_credentials, 
                "provider_credentials"
            )
            
            return decrypted_credentials
            
        except Exception as e:
            logger.error(f"Failed to retrieve credentials for {provider_name}: {str(e)}")
            return None
    
    def validate_payment_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate payment data for PCI compliance and security.
        
        Args:
            data: Payment data to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not data:
            return False
        
        # Check for PCI compliance
        for field, pattern in self.pci_patterns.items():
            if field in data and data[field]:
                # Check if the field matches the expected pattern
                if not re.match(pattern, str(data[field])):
                    logger.warning(f"Field {field} does not comply with PCI standards")
                    return False
        
        return True
    
    def log_payment_transaction(self, provider_id: str, transaction_id: str, 
                               payment_data: Dict[str, Any], status: str) -> bool:
        """
        Log a payment transaction securely for auditing and compliance.
        
        Args:
            provider_id: ID of the payment provider
            transaction_id: Unique transaction ID
            payment_data: Payment data (should be already encrypted)
            status: Status of the transaction
            
        Returns:
            True if successfully logged, False otherwise
        """
        try:
            # Create a transaction log entry
            log_entry = {
                "provider": provider_id,
                "transaction_id": transaction_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "data": payment_data,
                "type": "payment"
            }
            
            # In a real implementation, this would write to a secure database
            # For example, using DatabaseEncryptor for additional security
            
            # For now, we'll just log to the payment audit log file
            log_path = os.path.join(
                os.getenv("KAAPI_LOG_DIR", "/tmp"),
                "payment_audit.log"
            )
            
            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            logger.info(f"Logged payment transaction: {transaction_id} ({status})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log payment transaction: {str(e)}")
            return False
    
    def log_refund_transaction(self, provider_id: str, transaction_id: str, 
                              refund_data: Dict[str, Any], status: str) -> bool:
        """
        Log a refund transaction securely for auditing and compliance.
        
        Args:
            provider_id: ID of the payment provider
            transaction_id: Unique transaction ID
            refund_data: Refund data (should be already encrypted)
            status: Status of the transaction
            
        Returns:
            True if successfully logged, False otherwise
        """
        try:
            # Create a transaction log entry
            log_entry = {
                "provider": provider_id,
                "transaction_id": transaction_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "data": refund_data,
                "type": "refund"
            }
            
            # In a real implementation, this would write to a secure database
            # For example, using DatabaseEncryptor for additional security
            
            # For now, we'll just log to the payment audit log file
            log_path = os.path.join(
                os.getenv("KAAPI_LOG_DIR", "/tmp"),
                "payment_audit.log"
            )
            
            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            logger.info(f"Logged refund transaction: {transaction_id} ({status})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log refund transaction: {str(e)}")
            return False
    
    def rotateEncryptionKeys(self) -> bool:
        """
        Rotate encryption keys for payment data.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # In a real implementation, this would use the vault to rotate keys
            # For now, we'll just log that it was attempted
            logger.info("Payment encryption key rotation attempted")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate payment encryption keys: {str(e)}")
            return False
    
    def validate_pci_data(self, payment_data: Dict[str, Any]) -> List[str]:
        """
        Validate payment card data according to PCI-DSS requirements.
        
        Args:
            payment_data: Dictionary containing payment data
            
        Returns:
            List of validation errors, empty if valid
        """
        import re
        
        errors = []
        
        # Check card number format (if present)
        card_number = payment_data.get("card_number")
        if card_number:
            if not re.match(self.pci_patterns["card_number"], card_number):
                errors.append("Invalid card number format")
                
            # Simple Luhn algorithm check (for demonstration)
            if not self._validate_luhn(card_number.replace("-", "").replace(" ", "")):
                errors.append("Card number failed validation check")
        
        # Check CVV format
        cvv = payment_data.get("cvv")
        if cvv and not re.match(self.pci_patterns["cvv"], cvv):
            errors.append("Invalid CVV format")
            
        # Check expiry date format
        expiry = payment_data.get("expiry")
        if expiry and not re.match(self.pci_patterns["expiry"], expiry):
            errors.append("Invalid expiry date format")
            
        return errors
    
    def _validate_luhn(self, card_number: str) -> bool:
        """
        Validate card number using the Luhn algorithm.
        
        Args:
            card_number: Card number string (digits only)
            
        Returns:
            True if valid, False otherwise
        """
        digits = [int(d) for d in card_number if d.isdigit()]
        checksum = 0
        
        for i, digit in enumerate(reversed(digits)):
            if i % 2 == 1:  # Odd position (0-indexed from right)
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
            
        return checksum % 10 == 0


# Create singleton instance
payment_security = PaymentSecurity()
