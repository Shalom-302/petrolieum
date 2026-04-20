# /backend/app/plugins/security/vault_client.py
import hvac
import os
import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from requests.exceptions import ConnectionError, RequestException

logger = logging.getLogger(__name__)

class VaultClient:
    def __init__(self):
        self.vault_url = os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.vault_token = os.getenv("VAULT_TOKEN", "dev-token")
        self.max_retries = 5
        self.retry_delay = 2  # seconds
        self.dev_mode = os.getenv("ENVIRONMENT", "").lower() != "production"
        
        # Mock data for development mode if Vault is not available
        self.mock_secrets = {
            "encryption/aes-key": b"dev-aes-key-for-testing-purposes-only",
            "encryption/fernet-key": b"dev-fernet-key-for-testing-purposes-only"
        }
        
        # Connect to Vault with retries
        self._connect_with_retry()
    
    def _connect_with_retry(self):
        """Connect to Vault with retry logic."""
        for attempt in range(self.max_retries):
            try:
                self.client = hvac.Client(
                    url=self.vault_url,
                    token=self.vault_token
                )
                
                # Test connection
                if self.client.is_authenticated():
                    logger.info("Successfully connected to Vault")
                    return True
                else:
                    logger.warning(f"Vault authentication failed (attempt {attempt+1}/{self.max_retries})")
            
            except (ConnectionError, RequestException) as e:
                logger.warning(f"Failed to connect to Vault (attempt {attempt+1}/{self.max_retries}): {str(e)}")
            
            # Wait before retrying
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
        
        if self.dev_mode:
            logger.warning("Running in DEV mode with mock Vault secrets")
        else:
            logger.error("Failed to connect to Vault after multiple attempts")
    
    def rotate_keys(self):
        """Rotate encryption keys."""
        try:
            if not hasattr(self, 'client') or not self.client.is_authenticated():
                if not self._connect_with_retry():
                    logger.error("Cannot rotate keys: not connected to Vault")
                    return False
            
            self.client.secrets.transit.rotate_key(name="aes-key")
            self.client.secrets.transit.rotate_key(name="fernet-key")
            logger.info("Successfully rotated encryption keys")
            return True
        except Exception as e:
            logger.error(f"Failed to rotate keys: {str(e)}")
            return False
    
    def get_secret(self, path: str) -> bytes:
        """Get a secret from Vault with fallback to mock in dev mode."""
        try:
            if not hasattr(self, 'client') or not self.client.is_authenticated():
                if not self._connect_with_retry():
                    if self.dev_mode and path in self.mock_secrets:
                        logger.warning(f"Using mock secret for {path}")
                        return self.mock_secrets[path]
                    raise Exception("Not connected to Vault")
            
            response = self.client.secrets.kv.v2.read_secret_version(path=path)
            return response['data']['data']['value']
        except Exception as e:
            if self.dev_mode and path in self.mock_secrets:
                logger.warning(f"Using mock secret for {path} due to error: {str(e)}")
                return self.mock_secrets[path]
            logger.error(f"Failed to get secret {path}: {str(e)}")
            raise
    
    def start_key_rotation(self):
        """Start the key rotation scheduler."""
        try:
            scheduler = BackgroundScheduler()
            scheduler.add_job(
                func=self.rotate_keys,
                trigger="interval",
                hours=24
            )
            scheduler.start()
            logger.info("Key rotation scheduler started")
        except Exception as e:
            logger.error(f"Failed to start key rotation scheduler: {str(e)}")