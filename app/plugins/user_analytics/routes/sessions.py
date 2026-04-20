"""
API routes for managing user analytics sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy.orm import Session
from typing import Optional
from app.core.db import get_db
from app.core.security import get_current_user
from ..schemas import SessionCreate, SessionResponse
from ..services.session_service import SessionService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/session", response_model=SessionResponse)
async def create_session(
    request: Request,
    session_data: SessionCreate,
    db: Session = Depends(get_db)
):
    """
    Creates a new user analytics session.
    
    This endpoint is called when a user starts a new browsing session.
    It captures basic information about the client device for analytics purposes.
    """
    session_service = SessionService(db)
    
    # Get information from the request
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer") or session_data.referrer
    
    # Create the session
    try:
        session, session_token = session_service.create_session(
            user_id=session_data.user_id,
            device_info=session_data.device_info.dict() if session_data.device_info else None,
            ip_address=ip_address,
            user_agent_string=user_agent,
            referrer=referrer
        )
        
        response = SessionResponse(
            id=session.id,
            session_token=session_token,
            created_at=session.session_start
        )
        
        return response
    except Exception as e:
        logger.error(f"Error creating analytics session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create analytics session")

@router.post("/session/{session_id}/end")
async def end_session(
    session_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """
    Ends a user analytics session.
    
    Called when a user explicitly ends their session or when the application
    detects that the session should be terminated (e.g., user logs out).
    """
    session_service = SessionService(db)
    
    # Get token from cookie or header
    if not session_token:
        session_token = request.headers.get("X-Session-Token")
    
    # Validate the session token
    if not session_token or not session_service.validate_session(session_token, session_id):
        raise HTTPException(status_code=403, detail="Invalid session token")
    
    success = session_service.end_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or already ended")
    
    return {"message": "Session ended successfully"}

@router.post("/session/{session_id}/anonymize")
async def anonymize_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Anonymizes session data by removing personal identifiers.
    
    This endpoint is restricted to administrators as it permanently modifies
    analytics data. It's provided for privacy compliance purposes.
    """
    # Only allow admin users to anonymize sessions
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only administrators can anonymize sessions")
    
    session_service = SessionService(db)
    success = session_service.anonymize_session(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or already anonymized")
    
    return {"message": "Session anonymized successfully"}

@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Retrieves session information for analytics purposes.
    
    This endpoint is restricted to administrators as it provides
    access to potentially sensitive user data.
    """
    # Only allow admin users to view session details
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only administrators can view session details")
    
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "id": session.id,
        "user_id": session.user_id,
        "session_start": session.session_start,
        "session_end": session.session_end,
        "device_info": session.device_info,
        "referrer": session.referrer,
        "is_anonymized": session.is_anonymized,
        "event_count": len(session.events) if session.events else 0
    }
