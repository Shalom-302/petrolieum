"""
API routes for tracking user events and interactions.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Cookie, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.db import get_db
from ..schemas import EventCreate, EventResponse
from ..services.event_service import EventService
from ..services.session_service import SessionService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/event", response_model=EventResponse)
async def record_event(
    event_data: EventCreate,
    request: Request,
    session_token: Optional[str] = Cookie(None),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: Session = Depends(get_db)
):
    """
    Records a single user event.
    
    This endpoint captures user interactions like clicks, page views,
    form submissions, etc. for analytics purposes.
    """
    # Get session token from cookie or header
    token = session_token or x_session_token
    if not token:
        raise HTTPException(status_code=400, detail="Session token is required")
    
    # Extract session ID from event data
    session_id = event_data.session_token
    
    # Validate the session
    session_service = SessionService(db)
    if not session_service.validate_session(token, session_id):
        raise HTTPException(status_code=403, detail="Invalid session token")
    
    # Update session activity
    session_service.update_session_activity(session_id)
    
    # Record the event
    event_service = EventService(db)
    event = event_service.record_event(session_id, event_data)
    
    if not event:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return EventResponse(
        id=event.id,
        received_at=event.timestamp
    )

@router.post("/events/batch", response_model=List[EventResponse])
async def batch_record_events(
    events_data: List[EventCreate],
    request: Request,
    session_token: Optional[str] = Cookie(None),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: Session = Depends(get_db)
):
    """
    Records multiple user events in a single request.
    
    This batch endpoint is more efficient for capturing a sequence of
    interactions that happened in a short timeframe.
    """
    # Get token from cookie or header
    token = session_token or x_session_token
    if not token:
        raise HTTPException(status_code=400, detail="Session token is required")
    
    responses = []
    event_service = EventService(db)
    session_service = SessionService(db)
    
    for event_data in events_data:
        session_id = event_data.session_token
        
        # Validate the session
        if not session_service.validate_session(token, session_id):
            continue  # Skip events with invalid session
        
        # Update session activity
        session_service.update_session_activity(session_id)
        
        # Record the event
        event = event_service.record_event(session_id, event_data)
        if event:
            responses.append(EventResponse(
                id=event.id,
                received_at=event.timestamp
            ))
    
    if not responses:
        raise HTTPException(status_code=400, detail="No valid events were processed")
    
    return responses
