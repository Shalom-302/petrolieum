"""
Embed routes for Matomo integration.
Handles embedding Matomo dashboards and reports in the Kaapi interface.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_active_admin_user
from ..services.embed_service import MatomoEmbedService
from ..schemas import EmbedRequest, DashboardType

router = APIRouter()

@router.post("/dashboard", status_code=status.HTTP_200_OK)
async def get_dashboard_embed_url(
    dashboard: EmbedRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Get a URL for embedding a Matomo dashboard in an iframe.
    The URL includes authentication tokens for seamless access.
    Restricted to admin users.
    """
    embed_service = MatomoEmbedService(db)
    embed_url = await embed_service.get_embed_url(dashboard)
    
    if not embed_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embed URL"
        )
    
    return {"embed_url": embed_url}

@router.get("/dashboards", status_code=status.HTTP_200_OK)
async def get_available_dashboards(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Get a list of available dashboards from Matomo.
    Restricted to admin users.
    """
    embed_service = MatomoEmbedService(db)
    dashboards = await embed_service.get_available_dashboards()
    
    if dashboards is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available dashboards"
        )
    
    return {"dashboards": dashboards}

@router.get("/reports", status_code=status.HTTP_200_OK)
async def get_available_reports(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Get a list of available reports from Matomo.
    Restricted to admin users.
    """
    embed_service = MatomoEmbedService(db)
    reports = await embed_service.get_available_reports()
    
    if reports is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available reports"
        )
    
    return {"reports": reports}

@router.post("/report", status_code=status.HTTP_200_OK)
async def get_report_embed_url(
    report: EmbedRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Get a URL for embedding a specific Matomo report in an iframe.
    The URL includes authentication tokens for seamless access.
    Restricted to admin users.
    """
    embed_service = MatomoEmbedService(db)
    embed_url = await embed_service.get_embed_url(report, is_report=True)
    
    if not embed_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embed URL for report"
        )
    
    return {"embed_url": embed_url}
