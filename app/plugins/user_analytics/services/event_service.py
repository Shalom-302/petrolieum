"""
Service for managing user events and interactions in the analytics system.
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..models import AnalyticsUserEvent, AnalyticsUserSession
from ..schemas import EventCreate, HeatmapFilter, UserJourneyFilter
from datetime import datetime
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

class EventService:
    """Service for managing user events and journey tracking"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def record_event(self, session_id: str, event_data: EventCreate) -> Optional[AnalyticsUserEvent]:
        """
        Records a new event for the given session
        
        Args:
            session_id: ID of the session associated with the event
            event_data: Event data to record
            
        Returns:
            UserEvent object if successful, None otherwise
        """
        # Check if session exists
        session = self.db.query(AnalyticsUserSession).filter(AnalyticsUserSession.id == session_id).first()
        if not session:
            logger.error(f"Attempted to record event for non-existent session: {session_id}")
            return None
            
        # Create the event
        event = AnalyticsUserEvent(
            session_id=session_id,
            event_type=event_data.event_type,
            target_type=event_data.target_type,
            target_id=event_data.target_id,
            target_path=event_data.target_path,
            component_name=event_data.component_name,
            duration_ms=event_data.duration_ms,
            event_metadata=event_data.metadata,
            x_position=event_data.x_position,
            y_position=event_data.y_position,
            screen_width=event_data.screen_width,
            screen_height=event_data.screen_height
        )
        
        self.db.add(event)
        
        # Create an entry in the audit logs for significant events
        if event_data.event_type in ['click', 'submit', 'download', 'upload']:
            try:
                from app.plugins.advanced_audit.models import AuditLog
                
                # Create audit log entry
                audit_log = AuditLog(
                    user_id=None if not session.user_id or not session.user_id.isdigit() else int(session.user_id),
                    action=f"UI_{event_data.event_type.upper()}",
                    resource=event_data.target_type,
                    details=f"Path: {event_data.target_path}, Component: {event_data.component_name}, Target ID: {event_data.target_id}"
                )
                
                self.db.add(audit_log)
            except ImportError:
                logger.warning("Could not create audit log - advanced_audit plugin may not be available")
            except Exception as e:
                logger.error(f"Error creating audit log: {str(e)}")
        
        self.db.commit()
        self.db.refresh(event)
        return event
        
    def get_session_events(self, session_id: str, limit: int = 100, offset: int = 0) -> List[AnalyticsUserEvent]:
        """
        Retrieves events for a specific session
        
        Args:
            session_id: ID of the session
            limit: Maximum number of events to return
            offset: Number of events to skip
            
        Returns:
            List of UserEvent objects
        """
        return (
            self.db.query(AnalyticsUserEvent)
            .filter(AnalyticsUserEvent.session_id == session_id)
            .order_by(AnalyticsUserEvent.timestamp)
            .offset(offset)
            .limit(limit)
            .all()
        )
        
    def get_user_journey(self, filter_params: UserJourneyFilter) -> List[Dict[str, Any]]:
        """
        Retrieves complete user journey data structured by session
        
        Args:
            filter_params: Filtering criteria for the journey
            
        Returns:
            List of journey events organized by session
        """
        query = self.db.query(AnalyticsUserEvent).join(AnalyticsUserSession)
        
        if filter_params.user_id:
            query = query.filter(AnalyticsUserSession.user_id == filter_params.user_id)
            
        if filter_params.session_id:
            query = query.filter(AnalyticsUserEvent.session_id == filter_params.session_id)
            
        if filter_params.start_date:
            query = query.filter(AnalyticsUserEvent.timestamp >= filter_params.start_date)
            
        if filter_params.end_date:
            query = query.filter(AnalyticsUserEvent.timestamp <= filter_params.end_date)
            
        # Get most recent sessions first
        query = query.order_by(desc(AnalyticsUserSession.session_start), AnalyticsUserEvent.timestamp)
        
        # Limit the number of results
        events = query.limit(1000).all()  # Hard limit to prevent too many results
        
        # Organize events by session for easier analysis
        sessions = {}
        for event in events:
            if event.session_id not in sessions:
                sessions[event.session_id] = {
                    'session_id': event.session_id,
                    'start_time': event.session.session_start,
                    'end_time': event.session.session_end,
                    'events': []
                }
            
            # Add event to the session
            sessions[event.session_id]['events'].append({
                'id': event.id,
                'timestamp': event.timestamp,
                'event_type': event.event_type,
                'target_type': event.target_type,
                'target_id': event.target_id,
                'target_path': event.target_path,
                'component_name': event.component_name,
                'duration_ms': event.duration_ms,
                'metadata': event.event_metadata
            })
        
        # Convert to a list and sort by start time (newest first)
        journey = list(sessions.values())
        journey.sort(key=lambda x: x['start_time'], reverse=True)
        
        # Limit the number of sessions if user_id is provided (not for specific session_id)
        if filter_params.user_id and not filter_params.session_id:
            journey = journey[:filter_params.limit]
            
        return journey
        
    def get_heatmap_data(self, filter_params: HeatmapFilter) -> List[AnalyticsUserEvent]:
        """
        Retrieves filtered data for generating heatmaps
        
        Args:
            filter_params: Filtering criteria for the heatmap
            
        Returns:
            List of UserEvent objects
        """
        query = self.db.query(AnalyticsUserEvent)
        
        # Apply filters
        if filter_params.page_path:
            query = query.filter(AnalyticsUserEvent.target_path == filter_params.page_path)
            
        if filter_params.event_type:
            query = query.filter(AnalyticsUserEvent.event_type == filter_params.event_type)
            
        if filter_params.component_name:
            query = query.filter(AnalyticsUserEvent.component_name == filter_params.component_name)
            
        if filter_params.start_date:
            query = query.filter(AnalyticsUserEvent.timestamp >= filter_params.start_date)
            
        if filter_params.end_date:
            query = query.filter(AnalyticsUserEvent.timestamp <= filter_params.end_date)
            
        if filter_params.user_id:
            query = query.join(AnalyticsUserSession).filter(AnalyticsUserSession.user_id == filter_params.user_id)
            
        # Only retrieve events with coordinates for heatmaps
        query = query.filter(AnalyticsUserEvent.x_position.isnot(None), AnalyticsUserEvent.y_position.isnot(None))
        
        return query.all()
