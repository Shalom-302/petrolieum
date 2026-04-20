"""
Authentication routes for Matomo integration.
Handles user synchronization between Kaapi and Matomo.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_active_admin_user
from app.plugins.advanced_auth.models import User
from ..services.auth_service import MatomoAuthService
from ..schemas import MatomoUserSync, MatomoCredentials

router = APIRouter()

@router.post("/sync-user", status_code=status.HTTP_200_OK)
async def sync_user_to_matomo(
    user_data: MatomoUserSync,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Synchronize a Kaapi user with Matomo.
    Creates or updates the corresponding user in Matomo.
    Restricted to admin users.
    """
    auth_service = MatomoAuthService(db)
    result = await auth_service.sync_user(user_data)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to synchronize user with Matomo"
        )
    
    return {"status": "success", "detail": "User synchronized with Matomo", "user_id": result.get("matomo_id")}

@router.post("/login-matomo", status_code=status.HTTP_200_OK)
async def login_to_matomo(
    credentials: MatomoCredentials,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Login to Matomo with admin credentials.
    This creates a session token that can be used for embedding dashboards.
    Restricted to admin users.
    """
    auth_service = MatomoAuthService(db)
    result = await auth_service.login(credentials)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with Matomo"
        )
    
    return result

@router.get("/sync-all-users", status_code=status.HTTP_202_ACCEPTED)
async def sync_all_users(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_admin_user)
):
    """
    Synchronize all Kaapi users with Matomo.
    This is a long-running task that runs in the background.
    Restricted to admin users.
    """
    auth_service = MatomoAuthService(db)
    
    # Get all active users
    users = db.query(User).filter(User.is_active == True).all()
    
    # Start background task for synchronization
    task_id = await auth_service.sync_all_users(users)
    
    return {
        "status": "success", 
        "detail": f"Started synchronization of {len(users)} users with Matomo", 
        "task_id": task_id
    }
