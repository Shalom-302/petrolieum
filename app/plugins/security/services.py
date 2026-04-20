# /backend/app/plugins/security/services.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet
import os
from sqlalchemy import event
from sqlalchemy.orm import Session
import json
from datetime import datetime

class CryptoService:
    def __init__(self, vault_client):
        self.vault = vault_client
        self.aes_key = self.vault.get_secret("encryption/aes-key")
        self.fernet_key = self.vault.get_secret("encryption/fernet-key")

    def encrypt_field(self, data: str) -> str:
        aesgcm = AESGCM(self.aes_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, data.encode(), None)
        return f"{nonce.hex()}:{ciphertext.hex()}"
    
    def encrypt_audit_log(self, log_data: dict, 
                         gdpr_compliant: bool = True,
                         hipaa_compliant: bool = False) -> str:
        """
        Encrypts audit logs with compliance metadata
        Args:
            log_data: Dictionary containing audit details
            gdpr_compliant: Mask personal data if True
            hipaa_compliant: Add medical data protection if True
        Returns:
            Encrypted log string with compliance headers
        """
        # Add compliance metadata
        log_metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "data_classification": "sensitive",
            "compliance_tags": {
                "GDPR": gdpr_compliant,
                "HIPAA": hipaa_compliant
            }
        }
        
        # Apply data masking for GDPR
        if gdpr_compliant:
            log_data = self._mask_personal_data(log_data)
            
        # Merge metadata with actual log data
        full_log = {**log_metadata, **log_data}
        
        return self.encrypt_field(json.dumps(full_log))
    
    def decrypt_field(self, encrypted: str) -> str:
        nonce_hex, ct_hex = encrypted.split(":")
        nonce = bytes.fromhex(nonce_hex)
        ct = bytes.fromhex(ct_hex)
        aesgcm = AESGCM(self.aes_key)
        return aesgcm.decrypt(nonce, ct, None).decode()

class DatabaseEncryptor:
    def __init__(self, crypto_service):
        self.crypto = crypto_service
        self.sensitive_fields = {}  # {'ModelName': ['field1', 'field2']}
        # Register event listeners
        event.listen(Session, 'before_flush', self._encrypt_entity)
        event.listen(Session, 'loaded_as_persistent', self._decrypt_entity)

    def register_model(self, model_class, fields):
        self.sensitive_fields[model_class.__name__] = fields

    def _encrypt_entity(self, session, flush_context, instances):
        """Encrypt sensitive fields before flush"""
        for obj in session.new.union(session.dirty):
            model_name = obj.__class__.__name__
            if model_name in self.sensitive_fields:
                for field in self.sensitive_fields[model_name]:
                    value = getattr(obj, field, None)
                    if value is not None:
                        setattr(obj, field, self.crypto.encrypt_field(value))

    def _decrypt_entity(self, session, obj):
        """Decrypt sensitive fields after loading from database"""
        model_name = obj.__class__.__name__
        if model_name in self.sensitive_fields:
            for field in self.sensitive_fields[model_name]:
                encrypted = getattr(obj, field, None)
                if encrypted is not None:
                    setattr(obj, field, self.crypto.decrypt_field(encrypted))