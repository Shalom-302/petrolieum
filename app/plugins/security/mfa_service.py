# /backend/app/plugins/security/mfa_service.py
import pyotp
import qrcode
from io import BytesIO
from base64 import b64encode
from datetime import datetime
from collections import defaultdict
from cryptography.fernet import Fernet
from ..advanced_auth.schemas import AuthProvider  # Advanced_auth integration

class MFAService:
    def __init__(self, auth_provider: AuthProvider):
        self.auth = auth_provider
        self.mfa_secrets = {}
        self.failed_attempts = defaultdict(int)

    async def generate_mfa_secret(self, user_id: str) -> str:
        secret = pyotp.random_base32()
        self.mfa_secrets[user_id] = secret
        
        # Generate QR Code
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(
            name=await self.auth.get_user_email(user_id),
            issuer_name="SecurityPlugin"
        )
        img = qrcode.make(uri)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return b64encode(buffer.getvalue()).decode()

    async def verify_mfa_code(self, user_id: str, code: str) -> bool:
        if self.failed_attempts[user_id] >= 3:
            raise PermissionError("Too many failed attempts")
            
        secret = self.mfa_secrets.get(user_id)
        if not secret or not pyotp.TOTP(secret).verify(code, valid_window=2):
            self.failed_attempts[user_id] += 1
            return False
            
        self.failed_attempts[user_id] = 0
        return True

    async def toggle_mfa(self, user_id: str, enable: bool):
        await self.auth.update_user_security_flag(
            user_id, 
            "mfa_enabled", 
            enable,
            metadata={
                "last_modified": datetime.utcnow().isoformat(),
                "modified_by": "security_plugin"
            }
        )