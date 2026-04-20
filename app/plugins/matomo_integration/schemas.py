"""
Schema definitions for the Matomo integration plugin.
"""
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime

class DashboardType(str, Enum):
    OVERVIEW = "overview"
    VISITORS = "visitors"
    BEHAVIOR = "behavior"
    ACQUISITION = "acquisition"
    CONVERSION = "conversion"
    CUSTOM = "custom"

class MatomoConfig(BaseModel):
    """Configuration for Matomo integration."""
    matomo_url: HttpUrl = Field(..., description="URL of the Matomo instance")
    site_id: int = Field(..., description="Matomo site ID for this Kaapi instance")
    auth_token: Optional[str] = Field(None, description="Authentication token for Matomo API")
    enabled: bool = Field(True, description="Whether Matomo tracking is enabled")
    track_admin_users: bool = Field(False, description="Whether to track admin users")
    heartbeat_timer: int = Field(15, description="Heartbeat timer in seconds for tracking activity")
    
class MatomoSiteSettings(BaseModel):
    """Settings for the Matomo site representing this Kaapi instance."""
    name: str = Field(..., description="Name of the site in Matomo")
    urls: List[str] = Field(..., description="List of URLs for this site")
    timezone: Optional[str] = Field(None, description="Timezone for the site")
    currency: Optional[str] = Field(None, description="Currency code (e.g., EUR, USD)")
    excluded_ips: Optional[List[str]] = Field(None, description="IPs to exclude from tracking")
    excluded_query_params: Optional[List[str]] = Field(None, description="Query parameters to exclude")

class MatomoUserSync(BaseModel):
    """Data for synchronizing a user between Kaapi and Matomo."""
    kaapi_user_id: str = Field(..., description="User ID in Kaapi")
    email: str = Field(..., description="User email")
    login: Optional[str] = Field(None, description="Login username")
    password: Optional[str] = Field(None, description="Initial password for Matomo user")
    access_level: Optional[str] = Field("view", description="Access level in Matomo")

class MatomoCredentials(BaseModel):
    """Credentials for Matomo authentication."""
    username: str = Field(..., description="Matomo username or email")
    password: str = Field(..., description="Matomo password")
    remember_me: bool = Field(True, description="Whether to remember the session")

class EmbedRequest(BaseModel):
    """Request to embed a Matomo dashboard or report."""
    dashboard_type: DashboardType = Field(..., description="Type of dashboard to embed")
    date_range: Optional[str] = Field("last7", description="Date range for the dashboard")
    custom_id: Optional[str] = Field(None, description="ID of custom dashboard or report")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")

class MatomoTrackingEvent(BaseModel):
    """An event to be tracked in Matomo."""
    category: str = Field(..., description="Event category")
    action: str = Field(..., description="Event action")
    name: Optional[str] = Field(None, description="Event name")
    value: Optional[float] = Field(None, description="Event value")

class MatomoPageView(BaseModel):
    """A page view to be tracked in Matomo."""
    url: str = Field(..., description="Page URL")
    title: Optional[str] = Field(None, description="Page title")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    custom_dimensions: Optional[Dict[str, str]] = Field(None, description="Custom dimensions")
