"""
Configuration routes for Matomo integration.
Handles setting up Matomo instance URL, authentication, and site settings.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_active_admin_user
from ..services.config_service import MatomoConfigService
from ..schemas import MatomoConfig, MatomoSiteSettings

router = APIRouter()

@router.get("/", status_code=status.HTTP_200_OK)
async def get_matomo_config(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Get the current Matomo configuration.
    Restricted to admin users.
    """
    config_service = MatomoConfigService(db)
    config = config_service.get_config()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matomo configuration not found"
        )
    
    return config

@router.post("/", status_code=status.HTTP_200_OK)
async def update_matomo_config(
    config_data: MatomoConfig,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Update the Matomo configuration.
    Restricted to admin users.
    """
    config_service = MatomoConfigService(db)
    result = config_service.update_config(config_data)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Matomo configuration"
        )
    
    return {"status": "success", "detail": "Matomo configuration updated successfully"}

@router.post("/site-settings", status_code=status.HTTP_200_OK)
async def update_site_settings(
    settings: MatomoSiteSettings,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Update the Matomo site settings for the Kaapi instance.
    Restricted to admin users.
    """
    config_service = MatomoConfigService(db)
    result = await config_service.update_site_settings(settings)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Matomo site settings"
        )
    
    return {"status": "success", "detail": "Matomo site settings updated successfully"}

@router.get("/tracking-code", status_code=status.HTTP_200_OK)
async def get_tracking_code(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Get the JavaScript tracking code snippet for Matomo.
    Restricted to admin users.
    """
    config_service = MatomoConfigService(db)
    tracking_code = config_service.get_tracking_code()
    
    if not tracking_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matomo tracking code not found. Please configure Matomo first."
        )
    
    return {"tracking_code": tracking_code}
