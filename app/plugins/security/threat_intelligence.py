# /backend/app/plugins/security/threat_intelligence.py
class ThreatIntel:
    def __init__(self):
        self.suspicious_patterns = load_known_iocs()  # Charging from a feed
    
    def detect_malicious_payload(self, encrypted_data: str):
        decrypted = self.crypto.decrypt_field(encrypted_data)
        return any(p in decrypted for p in self.suspicious_patterns)