"""
Service for managing user sessions in the analytics system.
"""
import secrets
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import AnalyticsUserSession
from app.core.security import get_password_hash, verify_password
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class SessionService:
    """Service for managing user analytics sessions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_timeout = timedelta(minutes=30)  # Session expires after 30 min of inactivity
    
    def create_session(self, 
                      user_id: Optional[str] = None, 
                      device_info: Optional[Dict[str, Any]] = None, 
                      ip_address: Optional[str] = None, 
                      user_agent_string: Optional[str] = None, 
                      referrer: Optional[str] = None) -> Tuple[AnalyticsUserSession, str]:
        """
        Creates a new user session for analytics tracking
        
        Args:
            user_id: ID of the authenticated user (if any)
            device_info: Information about the user's device
            ip_address: User's IP address
            user_agent_string: User's browser agent string
            referrer: Referring URL
            
        Returns:
            Tuple containing session object and session token
        """
        # Create the session object
        session = AnalyticsUserSession(
            user_id=user_id,
            device_info=device_info or {},
            ip_address=ip_address,
            user_agent=user_agent_string,
            referrer=referrer
        )
        
        # Handle anonymization if necessary
        if not user_id:
            session.is_anonymized = True
        
        # Generate a secure session token
        session_token = secrets.token_urlsafe(32)
        session_token_hash = get_password_hash(session_token)
        
        # Store the secure hash in metadata for validation
        if not session.device_info:
            session.device_info = {}
        session.device_info["token_hash"] = session_token_hash
        
        # Save to database
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session, session_token
        
    def validate_session(self, session_token: str, session_id: str) -> bool:
        """
        Validates if a session token is valid for the given session ID
        
        Args:
            session_token: Token to validate
            session_id: ID of the session
            
        Returns:
            Boolean indicating if the token is valid
        """
        session = self.db.query(AnalyticsUserSession).filter(AnalyticsUserSession.id == session_id).first()
        
        if not session or "token_hash" not in session.device_info:
            return False
            
        # Verify token against stored hash
        token_hash = session.device_info["token_hash"]
        is_valid = verify_password(session_token, token_hash)
        
        # Check if session hasn't expired
        if is_valid and session.session_end is None:
            # Get last activity time from events or session start
            if session.events:
                last_activity = max([e.timestamp for e in session.events]) 
            else:
                last_activity = session.session_start
            
            if datetime.utcnow() - last_activity > self.session_timeout:
                # Close session if expired
                session.session_end = last_activity + self.session_timeout
                self.db.commit()
                return False
                
        return is_valid
        
    def update_session_activity(self, session_id: str) -> bool:
        """
        Updates a session's activity to prevent it from expiring
        
        Args:
            session_id: ID of the session to update
            
        Returns:
            Boolean indicating success
        """
        session = self.db.query(AnalyticsUserSession).filter(AnalyticsUserSession.id == session_id).first()
        if session and session.session_end is None:
            # Session is still active, implicit update via events
            return True
        return False
        
    def end_session(self, session_id: str) -> bool:
        """
        Ends a user session
        
        Args:
            session_id: ID of the session to end
            
        Returns:
            Boolean indicating success
        """
        session = self.db.query(AnalyticsUserSession).filter(AnalyticsUserSession.id == session_id).first()
        if session and session.session_end is None:
            session.session_end = datetime.utcnow()
            self.db.commit()
            return True
        return False
        
    def anonymize_session(self, session_id: str) -> bool:
        """
        Anonymizes session data by removing identifiable information
        
        Args:
            session_id: ID of the session to anonymize
            
        Returns:
            Boolean indicating success
        """
        session = self.db.query(AnalyticsUserSession).filter(AnalyticsUserSession.id == session_id).first()
        if session and not session.is_anonymized:
            # Remove user ID and IP address
            session.user_id = None
            session.ip_address = None
            
            # Anonymize user agent
            if session.user_agent:
                # Extract just generic info like browser family and device type
                session.user_agent = self._extract_browser_platform(session.user_agent)
            
            session.is_anonymized = True
            self.db.commit()
            return True
        return False
    
    def _extract_browser_platform(self, user_agent: str) -> str:
        """
        Extracts minimal browser and platform info from user agent
        
        Args:
            user_agent: Raw user agent string
            
        Returns:
            String with generalized browser/platform info
        """
        # This is a simple implementation - in production, use a proper user agent parser
        platform = "Unknown"
        if "Windows" in user_agent:
            platform = "Windows"
        elif "Macintosh" in user_agent:
            platform = "Mac"
        elif "Linux" in user_agent:
            platform = "Linux"
        elif "Android" in user_agent:
            platform = "Android"
        elif "iPhone" in user_agent or "iPad" in user_agent:
            platform = "iOS"
            
        browser = "Unknown"
        if "Chrome" in user_agent:
            browser = "Chrome"
        elif "Firefox" in user_agent:
            browser = "Firefox"
        elif "Safari" in user_agent:
            browser = "Safari"
        elif "Edge" in user_agent:
            browser = "Edge"
        
        return f"{browser} / {platform}"
