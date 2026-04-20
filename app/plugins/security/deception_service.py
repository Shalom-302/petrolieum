# backend/app/plugins/security/deception_service.py
from fastapi import Request
import logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DeceptionService:
    """
    A service to create honeypots and deception mechanisms to trap and identify attackers.
    """
    def __init__(self):
        self.fake_db = {
            "users": [
                {"id": 1, "username": "admin", "email": "admin@example.com"},
                {"id": 2, "username": "support", "email": "support@example.com"}
            ]
        }
        self.deception_events = []

    async def log_deception_event(self, request: Request, event_type: str):
        """Logs a deception event with detailed information from the request"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "source_ip": request.client.host,
            "user_agent": request.headers.get("user-agent", "N/A"),
            "path": request.url.path,
            "headers": dict(request.headers),
        }
        self.deception_events.append(event)
        logger.warning(f"Deception Event Triggered: {event_type} from {request.client.host}")

    def generate_credential_leak(self):
        """Generates fake credential data for honeypot endpoints"""
        return {
            "DATABASE_URL": f"postgres://user:{random.randint(1000, 9999)}@db.internal:5432/main_db",
            "S3_ACCESS_KEY": f"AKIA{random.randint(100000, 999999)}",
        }