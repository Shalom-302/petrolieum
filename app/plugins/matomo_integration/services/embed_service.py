"""
Embed service for Matomo integration.
Handles embedding Matomo dashboards and reports in the Kaapi interface.
"""
import logging
import httpx
import json
from urllib.parse import urlencode
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List

from ..models import MatomoSettings
from ..schemas import EmbedRequest, DashboardType

logger = logging.getLogger(__name__)

class MatomoEmbedService:
    """Service for embedding Matomo dashboards and reports."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_embed_url(self, request: EmbedRequest, is_report: bool = False) -> Optional[str]:
        """
        Get a URL for embedding a Matomo dashboard or report.
        
        Args:
            request: Dashboard or report request details
            is_report: Whether this is a report embed (True) or dashboard embed (False)
            
        Returns:
            URL for embedding in an iframe, or None if generation fails
        """
        try:
            # Get Matomo settings
            settings = self.db.query(MatomoSettings).first()
            if not settings or not settings.auth_token:
                logger.error("Matomo settings not found or missing auth token")
                return None
            
            # Map dashboard type to Matomo module and action
            module = "Dashboard" if not is_report else "CoreHome"
            action = "embeddedIndex" if not is_report else "index"
            
            # Build base URL
            base_url = f"{settings.matomo_url}/index.php"
            
            # Build query parameters
            params = {
                "module": module,
                "action": action,
                "idSite": settings.site_id,
                "period": "range" if request.date_range.startswith("custom:") else request.date_range.split(":")[0],
                "token_auth": settings.auth_token,
                "widget": 1,
                "disableLink": 1,
                "widget": 1
            }
            
            # Add date parameter based on date_range
            if request.date_range.startswith("custom:"):
                date_parts = request.date_range.split(":")[1].split(",")
                params["date"] = f"{date_parts[0]},{date_parts[1]}"
            else:
                params["date"] = request.date_range
            
            # Handle dashboard type specific parameters
            if not is_report:
                if request.dashboard_type == DashboardType.OVERVIEW:
                    params["category"] = "Dashboard_Overview"
                elif request.dashboard_type == DashboardType.VISITORS:
                    params["category"] = "Dashboard_Visitors"
                elif request.dashboard_type == DashboardType.BEHAVIOR:
                    params["category"] = "Dashboard_Behavior"
                elif request.dashboard_type == DashboardType.ACQUISITION:
                    params["category"] = "Dashboard_Acquisition"
                elif request.dashboard_type == DashboardType.CONVERSION:
                    params["category"] = "Dashboard_Conversion"
                elif request.dashboard_type == DashboardType.CUSTOM and request.custom_id:
                    params["category"] = "Dashboard_Custom"
                    params["subcategory"] = request.custom_id
            else:
                # For reports, set the appropriate report category and subcategory
                if request.custom_id:
                    report_parts = request.custom_id.split(".")
                    if len(report_parts) >= 2:
                        params["category"] = report_parts[0]
                        params["subcategory"] = report_parts[1]
            
            # Add any additional filters from the request
            if request.filters:
                for key, value in request.filters.items():
                    params[key] = value
            
            # Build the full URL
            url = f"{base_url}?{urlencode(params)}"
            return url
        except Exception as e:
            logger.error(f"Error generating Matomo embed URL: {str(e)}")
            return None
    
    async def get_available_dashboards(self) -> Optional[List[Dict[str, Any]]]:
        """Get a list of available dashboards from Matomo."""
        try:
            # Get Matomo settings
            settings = self.db.query(MatomoSettings).first()
            if not settings or not settings.auth_token:
                logger.error("Matomo settings not found or missing auth token")
                return None
            
            # Call Matomo API to get dashboards
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.matomo_url}/index.php",
                    params={
                        "module": "API",
                        "method": "Dashboard.getDashboards",
                        "idSite": settings.site_id,
                        "token_auth": settings.auth_token,
                        "format": "json"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Error retrieving dashboards from Matomo: {response.text}")
                    return None
                
                try:
                    dashboards = response.json()
                    return dashboards
                except json.JSONDecodeError:
                    logger.error("Error decoding dashboards JSON response from Matomo")
                    return None
        except Exception as e:
            logger.error(f"Error retrieving dashboards from Matomo: {str(e)}")
            return None
    
    async def get_available_reports(self) -> Optional[List[Dict[str, Any]]]:
        """Get a list of available reports from Matomo."""
        try:
            # Get Matomo settings
            settings = self.db.query(MatomoSettings).first()
            if not settings or not settings.auth_token:
                logger.error("Matomo settings not found or missing auth token")
                return None
            
            # Call Matomo API to get available reports
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.matomo_url}/index.php",
                    params={
                        "module": "API",
                        "method": "API.getReportMetadata",
                        "idSite": settings.site_id,
                        "token_auth": settings.auth_token,
                        "format": "json"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Error retrieving reports from Matomo: {response.text}")
                    return None
                
                try:
                    reports = response.json()
                    return reports
                except json.JSONDecodeError:
                    logger.error("Error decoding reports JSON response from Matomo")
                    return None
        except Exception as e:
            logger.error(f"Error retrieving reports from Matomo: {str(e)}")
            return None
