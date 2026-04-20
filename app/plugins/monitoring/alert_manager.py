# /backend/app/plugins/monitoring/alert_manager.py
from slack_sdk import WebClient
import smtplib
from email.mime.text import MIMEText

class AlertManager:
    def __init__(self, config):
        self.slack_enabled = config.slack_enabled
        self.slack_token = config.slack_token
        self.email_config = config.email_alerts
        self.slack = WebClient(config.slack_token) if config.slack_enabled else None
        
    async def send_alert(self, message, priority="medium"):
        if priority in ["high", "critical"]:
            await self._send_slack(f"[URGENT] {message}")
            self._send_email(f"Security Alert: {message}")
            
    async def _send_slack(self, text):
        if self.slack:
            await self.slack.chat_postMessage(
                channel="#security-alerts",
                text=text
            )
            
    def _send_email(self, body):
        msg = MIMEText(body)
        msg['Subject'] = "Security Incident Detected"
        msg['From'] = self.email_config.sender
        msg['To'] = self.email_config.recipients
        
        with smtplib.SMTP(self.email_config.smtp_server) as server:
            server.send_message(msg)