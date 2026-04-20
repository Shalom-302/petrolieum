"""
Configuration service for Matomo integration.
Handles retrieving and updating Matomo configuration.
"""
import logging
import httpx
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Dict, Any

from ..models import MatomoSettings
from ..schemas import MatomoConfig, MatomoSiteSettings

logger = logging.getLogger(__name__)

class MatomoConfigService:
    """Service for managing Matomo configuration."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """Get the current Matomo configuration."""
        try:
            settings = self.db.query(MatomoSettings).first()
            if not settings:
                return None
                
            return {
                "matomo_url": settings.matomo_url,
                "site_id": settings.site_id,
                "enabled": settings.enabled,
                "track_admin_users": settings.track_admin_users,
                "heartbeat_timer": settings.heartbeat_timer,
                "additional_settings": settings.additional_settings
            }
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving Matomo configuration: {str(e)}")
            return None
    
    def update_config(self, config: MatomoConfig) -> bool:
        """Update the Matomo configuration."""
        try:
            settings = self.db.query(MatomoSettings).first()
            
            if not settings:
                # Create new settings if none exist
                settings = MatomoSettings(
                    matomo_url=str(config.matomo_url),
                    site_id=config.site_id,
                    auth_token=config.auth_token,
                    enabled=config.enabled,
                    track_admin_users=config.track_admin_users,
                    heartbeat_timer=config.heartbeat_timer
                )
                self.db.add(settings)
            else:
                # Update existing settings
                settings.matomo_url = str(config.matomo_url)
                settings.site_id = config.site_id
                settings.auth_token = config.auth_token
                settings.enabled = config.enabled
                settings.track_admin_users = config.track_admin_users
                settings.heartbeat_timer = config.heartbeat_timer
            
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating Matomo configuration: {str(e)}")
            return False
    
    async def update_site_settings(self, settings: MatomoSiteSettings) -> bool:
        """Update the Matomo site settings for the Kaapi instance."""
        try:
            config = self.get_config()
            if not config or not config.get("auth_token"):
                logger.error("Matomo configuration not found or missing auth token")
                return False
            
            # Call Matomo API to update site settings
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{config['matomo_url']}/index.php",
                    params={
                        "module": "API",
                        "method": "SitesManager.updateSite",
                        "idSite": config["site_id"],
                        "token_auth": config["auth_token"],
                        "name": settings.name,
                        "urls": ",".join(settings.urls),
                        "timezone": settings.timezone or "",
                        "currency": settings.currency or "",
                        "excludedIps": ",".join(settings.excluded_ips or []),
                        "excludedQueryParameters": ",".join(settings.excluded_query_params or []),
                        "format": "json"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Error updating Matomo site settings: {response.text}")
                    return False
                
                return True
        except Exception as e:
            logger.error(f"Error updating Matomo site settings: {str(e)}")
            return False
    
    def get_tracking_code(self) -> Optional[str]:
        """Get the JavaScript tracking code snippet for Matomo."""
        try:
            config = self.get_config()
            if not config:
                return None
            
            # Create tracking code snippet
            tracking_code = f"""
<!-- Matomo -->
<script>
  var _paq = window._paq = window._paq || [];
  /* Track as a single page application without hash */
  _paq.push(['disableCookies']);
  _paq.push(['trackPageView']);
  _paq.push(['enableLinkTracking']);
  {'_paq.push(["enableHeartBeatTimer", ' + str(config['heartbeat_timer']) + ']);' if config['heartbeat_timer'] > 0 else ''}
  (function() {{
    var u="{config['matomo_url']}/";
    _paq.push(['setTrackerUrl', u+'matomo.php']);
    _paq.push(['setSiteId', '{config["site_id"]}']);
    var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0];
    g.async=true; g.src=u+'matomo.js'; s.parentNode.insertBefore(g,s);
  }})();
</script>
<!-- End Matomo Code -->
"""
            return tracking_code
        except Exception as e:
            logger.error(f"Error generating Matomo tracking code: {str(e)}")
            return None

def initialize_default_config():
    """Initialize default Matomo configuration if none exists."""
    from app.core.db import SessionLocal
    
    try:
        db = SessionLocal()
        config_service = MatomoConfigService(db)
        settings = db.query(MatomoSettings).first()
        
        if not settings:
            # Create default settings
            db.add(MatomoSettings(
                matomo_url="http://matomo.example.com",  # Default placeholder URL
                site_id=1,  # Default site ID
                enabled=False,  # Disabled by default until properly configured
                track_admin_users=False,
                heartbeat_timer=15
            ))
            db.commit()
            logger.info("Initialized default Matomo configuration")
        
        db.close()
    except Exception as e:
        logger.error(f"Error initializing default Matomo configuration: {str(e)}")
        if 'db' in locals():
            db.close()
