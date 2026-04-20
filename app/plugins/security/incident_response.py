# /backend/app/plugins/security/incident_response.py
from datetime import datetime, timedelta
from .vault_client import VaultClient

class IncidentResponder:
    def __init__(self, detector):
        self.detector = detector
        self.vault = VaultClient()
        self.blocked_ips = dict()  # {ip: expiration_time}

    RESPONSE_PLANS = {
        "critical": {
            "actions": ["block_ip", "rotate_keys", "notify_soc"],
            "ttl": timedelta(hours=1)
        },
        "high": {
            "actions": ["require_mfa", "throttle_user"],
            "ttl": timedelta(minutes=30)
        },
        "medium": ["log_only"]
    }

    async def execute_response(self, event_type: str, metadata: dict):
        risk_level = self._calculate_risk_level(event_type, metadata)
        plan = self.RESPONSE_PLANS.get(risk_level, [])

        for action in plan.get("actions", []):
            if action == "block_ip":
                await self._block_ip(metadata["source_ip"], plan["ttl"])
            elif action == "rotate_keys":
                self.vault.rotate_keys()
            elif action == "notify_soc":
                self._trigger_soc_alert(metadata)

    def _calculate_risk_level(self, event_type: str, metadata: dict) -> str:
        score = 0
        if event_type == "honeypot_triggered":
            score += 70
        if metadata.get("risk_score", 0) > 75:
            score += 25
        return "critical" if score >= 90 else "high" if score >= 70 else "medium"