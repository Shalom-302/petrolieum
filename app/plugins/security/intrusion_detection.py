# /backend/app/plugins/security/intrusion_detection.py
from datetime import datetime, timedelta
from collections import defaultdict
from app.plugins.monitoring import AlertManager
from .incident_response import IncidentResponder
from app.plugins.security.security_config import load_security_config
from .vulnerability_scanner import VulnerabilityScanner
from apscheduler.schedulers.background import BackgroundScheduler
import json
import logging

logger = logging.getLogger("security")
security_config = load_security_config()
if not hasattr(security_config, 'monitoring'):
    alert_manager = AlertManager(security_config)
else:
    alert_manager = AlertManager(security_config.monitoring)

class IntrusionDetector:
    def __init__(self):
        self.decryption_logs = defaultdict(list)
        self.lockouts = {}
        self.responder = IncidentResponder(self)
        self.scanner = VulnerabilityScanner(security_config.vulnerability_scanning)
        
        self.SECURITY_CONFIG = {
            'alert_thresholds': {
                'decrypt_failures': 5,
                'decrypt_rate': 20
            },
            'lockout_policy': {
                'max_attempts': 5,
                'duration': timedelta(minutes=15),
                'cooldown': timedelta(hours=1)
            }
        }

    def schedule_vulnerability_scans(self):
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            self._run_scheduled_scans,
            'cron',
            **security_config.vulnerability_scanning.schedule.dict()
        )
        scheduler.start()

    def _run_scheduled_scans(self):
        targets = [t for t in security_config.vulnerability_scanning.targets]
        results = {
            'trivy': [self.scanner.run_trivy_scan(t) for t in targets],
            'zap': self.scanner.run_zap_scan(security_config.vulnerability_scanning.target_url)
        }
        self._process_scan_results(results)

    def check_lockout(self, user_id: str) -> bool:
        lockout_time = self.lockouts.get(user_id)
        if lockout_time and datetime.now() < lockout_time:
            return True
        if lockout_time:
            del self.lockouts[user_id]
        return False

    def log_decryption_attempt(self, success: bool, user_id: str):
        if self.check_lockout(user_id):
            raise PermissionError("Account locked - Contact administrator")
            
        timestamp = datetime.now()
        entry = {'timestamp': timestamp, 'success': success}
        self.decryption_logs[user_id].append(entry)
        
        cutoff = timestamp - self.SECURITY_CONFIG['lockout_policy']['cooldown']
        self.decryption_logs[user_id] = [e for e in self.decryption_logs[user_id] if e['timestamp'] > cutoff]
        
        self._analyze_security_events(user_id, timestamp)

    def _analyze_security_events(self, user_id: str, timestamp: datetime):
        recent_events = [
            e for e in self.decryption_logs[user_id]
            if timestamp - e['timestamp'] < timedelta(minutes=1)
        ]
        
        if len(recent_events) > self.SECURITY_CONFIG['alert_thresholds']['decrypt_rate']:
            self._trigger_alert(
                "rate_alert",
                user_id,
                f"High decryption rate: {len(recent_events)}/min"
            )
        
        failures = sum(not e['success'] for e in recent_events)
        if failures >= self.SECURITY_CONFIG['alert_thresholds']['decrypt_failures']:
            self._trigger_alert(
                "failure_alert", 
                user_id,
                f"Multiple failures: {failures} attempts"
            )
            
            if failures >= self.SECURITY_CONFIG['lockout_policy']['max_attempts']:
                self._apply_account_lockout(user_id)

    def _trigger_alert(self, alert_type: str, user_id: str, message: str):
        self.log_security_event(
            event_type=f"alert_{alert_type}",
            metadata={
                "message": message,
                "user_id": user_id,
                "alert_type": alert_type
            }
        )

    def log_security_event(self, event_type: str, metadata: dict):
        severity = self._get_severity_level(event_type)
        
        alert_manager.send_alert(
            message=f"[{event_type.upper()}] Security Event: {json.dumps(metadata)}",
            priority=severity
        )
        
        self.responder.execute_response(event_type, metadata)
        logger.warning("%s - %s: %s", datetime.now(), event_type, metadata)

    def _get_severity_level(self, event_type: str) -> str:
        severity_map = {
            "alert_rate": "warning",
            "alert_failure": "critical",
            "account_lockout": "high",
            "account_unlock": "info",
            "honeypot_triggered": "critical"
        }
        return severity_map.get(event_type, "info")

    def _apply_account_lockout(self, user_id: str):
        lockout_end = datetime.now() + self.SECURITY_CONFIG['lockout_policy']['duration']
        self.lockouts[user_id] = lockout_end
        
        self.log_security_event(
            event_type="account_lockout",
            metadata={
                "user_id": user_id,
                "lockout_end": lockout_end.isoformat()
            }
        )

    def clear_lockout(self, user_id: str):
        if user_id in self.lockouts:
            del self.lockouts[user_id]
            self.log_security_event(
                event_type="account_unlock",
                metadata={
                    "user_id": user_id,
                    "action": "manual_unlock"
                }
            )