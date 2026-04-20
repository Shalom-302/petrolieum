"""
Public API routes for the advanced authentication plugin.
These routes are accessible without authentication.
"""
from typing import Dict, Any, List
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings
from .service import AuthService

logger = logging.getLogger(__name__)

# Create public router
public_router = APIRouter(
    prefix="/providers",  
    tags=["public_authentication"],
    responses={
        404: {"description": "Not found"}
    }
)

@public_router.get("", response_model=List[Dict[str, Any]])
async def get_public_providers(db: Session = Depends(get_db)):
    """
    Public endpoint for getting auth providers without authentication.
    This is used by the login page to display available login methods.
    """
    auth_service = AuthService(db)
    providers = await auth_service.get_available_providers()
    return providers
