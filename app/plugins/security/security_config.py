# /backend/app/plugins/security/security_config.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from pathlib import Path
import yaml

class ThreatIntelConfig(BaseModel):
    enabled: bool
    feeds: List[str]
    update_interval: int = Field(..., gt=0, description="Update interval in seconds")

class WAFRule(BaseModel):
    pattern: str
    action: str = "block"

class WAFConfig(BaseModel):
    enabled: bool = True
    rules: List[WAFRule] = Field(default_factory=list)
    threat_intel: ThreatIntelConfig = Field(default_factory=ThreatIntelConfig)

class DeceptionTrap(BaseModel):
    path: str
    type: str
    response_delay: Optional[str] = None

class DeceptionConfig(BaseModel):
    enabled: bool
    traps: List[DeceptionTrap]

class MFAConfig(BaseModel):
    enabled: bool
    protected_endpoints: List[str]
    code_ttl: int = 300

class SessionConfig(BaseModel):
    secret_key: str
    max_age: int = 86400
    concurrent_sessions: int = 3

class ScanSchedule(BaseModel):
    minute: str = "*"
    hour: str = "*"
    day: str = "*"
    month: str = "*"
    day_of_week: str = "*"

class ZapConfig(BaseModel):
    api_key: str

class VulnerabilityScanning(BaseModel):
    enabled: bool = False  # Default value
    trivy_path: str = 'trivy'
    zap: ZapConfig
    schedule: ScanSchedule = ScanSchedule()
    targets: List[str] = Field(
        default_factory=list,
        description="List of URLs/endpoints to scan"
    )

class MonitoringEmailAlerts(BaseModel):
    sender: str
    recipients: List[str]
    smtp_server: str

class MonitoringConfig(BaseModel):
    slack_enabled: bool
    slack_token: str
    email_alerts: MonitoringEmailAlerts

class SecurityConfig(BaseModel):
    waf: WAFConfig
    deception: DeceptionConfig
    mfa: MFAConfig
    session: SessionConfig
    vulnerability_scanning: VulnerabilityScanning
    monitoring: MonitoringConfig

def load_security_config() -> SecurityConfig:
    """Loads security configuration from YAML file"""
    config_path = Path(__file__).parent / "security_config.yaml"
    
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)
    
    return SecurityConfig(**raw_config)