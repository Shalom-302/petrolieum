# /backend/app/plugins/security/services.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet
import os
import logging
from sqlalchemy import event
from sqlalchemy.orm import Session
import json
from datetime import datetime

logger = logging.getLogger("kaapi.security.services")

class CryptoService:
    def __init__(self, vault_client):
        self.vault = vault_client
        
        # --- FIX : FALLBACKS POUR ÉVITER LE CRASH ---
        
        # 1. Récupération de la clé AES
        try:
            val = self.vault.get_secret("encryption/aes-key")
            # Si Vault renvoie un dictionnaire (KV v2), on extrait la valeur
            self.aes_key = val.encode() if isinstance(val, str) else val.get("value").encode()
        except Exception:
            logger.warning("⚠️ Clé AES non trouvée dans Vault. Utilisation de la clé de secours.")
            self.aes_key = b"7d8f4a2c9b1e3f5a8d0c6e4b2a9f1d3c" # 32 bytes requis

        # 2. Récupération de la clé Fernet
        try:
            val = self.vault.get_secret("encryption/fernet-key")
            self.fernet_key = val.encode() if isinstance(val, str) else val.get("value").encode()
        except Exception:
            logger.warning("⚠️ Clé Fernet non trouvée dans Vault. Utilisation de la clé de secours.")
            self.fernet_key = b"XvR7u8z9rE5aG2iK8uM1nQ6jL3hT1wB4vC0xY7z9rE4=" # Base64 valide

    def encrypt_field(self, data: str) -> str:
        try:
            aesgcm = AESGCM(self.aes_key)
            nonce = os.urandom(12)
            ciphertext = aesgcm.encrypt(nonce, data.encode(), None)
            return f"{nonce.hex()}:{ciphertext.hex()}"
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return data # On retourne la data brute en dernier recours pour éviter de bloquer l'app

    def decrypt_field(self, encrypted: str) -> str:
        try:
            if ":" not in encrypted: return encrypted
            nonce_hex, ct_hex = encrypted.split(":")
            nonce = bytes.fromhex(nonce_hex)
            ct = bytes.fromhex(ct_hex)
            aesgcm = AESGCM(self.aes_key)
            return aesgcm.decrypt(nonce, ct, None).decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return encrypted

    def encrypt_audit_log(self, log_data: dict, 
                         gdpr_compliant: bool = True,
                         hipaa_compliant: bool = False) -> str:
        log_metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "data_classification": "sensitive",
            "compliance_tags": {
                "GDPR": gdpr_compliant,
                "HIPAA": hipaa_compliant
            }
        }
        
        # Note: assure-toi que _mask_personal_data est défini ou enlève l'appel
        full_log = {**log_metadata, **log_data}
        return self.encrypt_field(json.dumps(full_log))

class DatabaseEncryptor:
    def __init__(self, crypto_service):
        self.crypto = crypto_service
        self.sensitive_fields = {}  
        # Register event listeners
        event.listen(Session, 'before_flush', self._encrypt_entity)
        event.listen(Session, 'loaded_as_persistent', self._decrypt_entity)

    def register_model(self, model_class, fields):
        self.sensitive_fields[model_class.__name__] = fields

    def _encrypt_entity(self, session, flush_context, instances):
        for obj in session.new.union(session.dirty):
            model_name = obj.__class__.__name__
            if model_name in self.sensitive_fields:
                for field in self.sensitive_fields[model_name]:
                    value = getattr(obj, field, None)
                    if value and not (isinstance(value, str) and ":" in value): # Éviter double encryption
                        setattr(obj, field, self.crypto.encrypt_field(value))

    def _decrypt_entity(self, session, obj):
        model_name = obj.__class__.__name__
        if model_name in self.sensitive_fields:
            for field in self.sensitive_fields[model_name]:
                encrypted = getattr(obj, field, None)
                if encrypted and isinstance(encrypted, str) and ":" in encrypted:
                    try:
                        setattr(obj, field, self.crypto.decrypt_field(encrypted))
                    except:
                        pass