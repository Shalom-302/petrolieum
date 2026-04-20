"""Security plugin implementation with encryption, MFA, and intrusion detection."""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.config import settings as config
import re
import asyncio
import aiohttp
from .services import CryptoService
from .vault_client import VaultClient
from .schemas import EncryptionRequest, DecryptionRequest
# from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from .mfa_service import MFAService
from sqlalchemy.ext.asyncio import AsyncSession
from .intrusion_detection import IntrusionDetector
from .waf import ThreatIntelFeed
from fastapi.responses import JSONResponse
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload
from app.core.db import engine, AsyncSessionFactory as async_session
from app.logger import logger
from .models import UserSession
from .deception_service import DeceptionService

# Global patterns for security checks
SUSPICIOUS_PATTERNS = [
    r"([';]+|--|\b(select|union|drop)\b)",  # SQLi (SQL injection)
    r"(<script|alert\(|onerror=)",  # XSS (Cross-site scripting)
    r"(\bexec\b|\bshell\b|\bwget\b)",  # Command injection
    r"\.\./\.\./",  # Path traversal
    r"\$({\w+}|\(|\{)" # Template injection
]

def get_router() -> APIRouter:
    """Return the main router for the security plugin."""
    router = APIRouter()
    
    # Sub-routers - organiser pour éviter les doublons
    crypto_router = APIRouter()
    mfa_router = APIRouter()
    session_router = APIRouter()
    deception_router = APIRouter(include_in_schema=False)
    
    # Services
    deception_service = DeceptionService()
    

    # Setting limits
    DECRYPT_RATE_LIMIT = "10/minute"  # 10 requests/min for /decrypt
    HONEYPOT_RATE_LIMIT = "2/minute"  # 2 requests/min for /decrypt-fake

    # Service dependencies
    def get_crypto_service():
        vault = VaultClient()
        return CryptoService(vault)

    def get_intrusion_detector():
        return IntrusionDetector()

    async def get_async_session() -> AsyncSession:
        return AsyncSession(engine)

    # Feed update logic
    async def run_periodic_feed_update(feed):
        while True:
            try:
                await feed.update_feeds()
                await asyncio.sleep(feed.update_interval)
            except aiohttp.ClientError as e:
                logger.error(f"Network error : {str(e)}")
                await asyncio.sleep(300)  # Backoff on failure
            except Exception as e:
                logger.critical(f"WAF updater crash : {str(e)}")
                break


    ## Deception Service endpoints ------------------------
    @deception_router.get("/internal/users")
    async def fake_users_endpoint(request: Request):
        await deception_service.log_deception_event(request, "fake_users_api")
        return {"users": deception_service.fake_db["users"]}

    @deception_router.post("/admin/backup")
    async def fake_backup_endpoint(request: Request):
        await deception_service.log_deception_event(request, "fake_backup_api")
        return {"status": "Backup started", "path": "/backups/2023.tar.gz"}

    @deception_router.get("/.env")
    async def fake_env_endpoint(request: Request):
        await deception_service.log_deception_event(request, "fake_env_file")
        return {"error": "Unauthorized", "debug_info": deception_service.generate_credential_leak()}

    @router.get("/health-check")
    async def health_check():
        """Endpoint de vérification de l'état de santé du plugin de sécurité."""
        async with async_session() as session:
            try:
                await session.execute(text("SELECT 1"))
                return {"status": "ok", "database_connection": "successful"}
            except Exception as e:
                return {"status": "error", "database_connection": "failed", "detail": str(e)}

    @session_router.get("/active")
    async def list_active_sessions(request: Request):
        current_user = request.state.user
        async with async_session() as session:
            sessions = await session.execute(
                select(UserSession)
                .where(UserSession.user_id == current_user.id)
                .where(UserSession.revoked == False)
            )
            return sessions.scalars().all()

    ## MFA endpoints -------------------------------------
    @mfa_router.post("/setup")
    async def setup_mfa(request: Request):
        user = request.state.user
        mfa_service = request.app.state.mfa_service
        try:
            qr_code = await mfa_service.generate_mfa_secret(user.id)
            return {"qr_code": qr_code, "manual_secret": mfa_service.mfa_secrets[user.id]}
        except Exception as e:
            raise HTTPException(500, detail=str(e))

    @mfa_router.post("/verify")
    async def verify_mfa(request: Request, code: str):
        user = request.state.user
        mfa_service = request.app.state.mfa_service
        try:
            if await mfa_service.verify_mfa_code(user.id, code):
                await mfa_service.toggle_mfa(user.id, True)
                return {"status": "MFA enabled successfully"}
            raise HTTPException(400, "Invalid verification code")
        except PermissionError as pe:
            raise HTTPException(403, detail=str(pe))

    @mfa_router.post("/disable")
    async def disable_mfa(request: Request):
        user = request.state.user
        mfa_service = request.app.state.mfa_service
        await mfa_service.toggle_mfa(user.id, False)
        return {"status": "MFA disabled successfully"}

    ## Encryption endpoints -------------------------------------
    @crypto_router.post("/encrypt")
    async def encrypt_data(
        request: EncryptionRequest,  # Schema usage
        crypto: CryptoService = Depends(get_crypto_service)
    ):
        return {"encrypted": crypto.encrypt_field(request.data)}

    @crypto_router.post("/decrypt")
    # @limiter.limit(DECRYPT_RATE_LIMIT)
    async def decrypt_data(
        request: DecryptionRequest,  # Validation reinforced
        crypto: CryptoService = Depends(get_crypto_service)
    ):
        return {"decrypted": crypto.decrypt_field(request.encrypted)}

    @crypto_router.post("/decrypt-fake")
    # @limiter.limit(HONEYPOT_RATE_LIMIT)
    async def fake_decrypt_endpoint(
        request: Request,
        detector: IntrusionDetector = Depends(get_intrusion_detector),
        session: AsyncSession = Depends(get_async_session)
    ):
        """Endpoint decoy with advanced security analysis"""
        request_data = await request.body()
        decoded_data = request_data.decode(errors='ignore').lower() if request_data else ""
        
        # Payload analysis
        payload_risk = 0
        patterns_found = []
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, decoded_data):
                payload_risk += 25
                patterns_found.append(pattern)

        # Header verification
        suspicious_headers = {
            "User-Agent": ["curl", "wget", "nikto", "sqlmap"], # User-Agent attack tools
            "X-Forwarded-For": ["127.0.0.1", "::1", "localhost"], # Local IP in X-Forwarded-For 
            "Accept": ["*/*"], # Accept headers that are too permissive
            "Authorization": ["Basic "] # Absence of safety-critical headers
        }
        
        header_anomalies = []
        for header, values in suspicious_headers.items():
            if header_value := request.headers.get(header):
                if any(v.lower() in header_value.lower() for v in values):
                    header_anomalies.append(header)

        # Complete logging
        detector.log_security_event(
            event_type="honeypot_triggered",
            metadata={
                "source_ip": request.client.host,
                "user_agent": request.headers.get("user-agent"),
                "risk_score": f"{min(payload_risk, 100)}%",
                "payload_analysis": {
                    "length": len(decoded_data) if request_data else 0,
                    "suspicious_patterns": patterns_found
                },
                "header_anomalies": header_anomalies,
                "missing_security_headers": [
                    h for h in ["Content-Security-Policy", "X-Content-Type-Options"]
                    if not request.headers.get(h)
                ]
            }
        )

        # Credible decoy
        import random
        await asyncio.sleep(random.uniform(1.5, 3.0))
        
        return {"error": "Decryption failed - Invalid key"}

    # Plugin information
    @router.get("/", tags=["Security"])
    async def plugin_info():
        """Return information about the security plugin."""
        return {
            "name": "Security Plugin",
            "version": "1.0.0",
            "features": [
                "Encryption and decryption",
                "Multi-factor authentication",
                "Session management",
                "Intrusion detection",
                "Web Application Firewall"
            ]
        }

    # Organiser les sous-routeurs logiquement pour éviter les doublons
    # Chaque route apparaît dans une seule section distincte
    router.include_router(crypto_router, prefix="/crypto")
    router.include_router(mfa_router, prefix="/mfa")
    router.include_router(session_router, prefix="/sessions")
    router.include_router(deception_router)

    return router

# Export the router
security_router = get_router()