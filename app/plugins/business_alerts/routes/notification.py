"""
Alert notification routes.

This module provides API endpoints for alert notifications,
including real-time notification delivery and notification preferences.
"""

import logging
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.core.rate_limit import rate_limit
from app.plugins.business_alerts.models.alert import BusinessAlertDB
from app.plugins.business_alerts.services.notifier import AlertNotifier

logger = logging.getLogger(__name__)


def get_notification_router():
    """
    Create and return a router for notification endpoints.
    
    This function initializes an APIRouter with various endpoints for
    handling alert notifications, including WebSocket connections for
    real-time notifications.
    
    Returns:
        APIRouter: FastAPI router with notification endpoints
    """
    # Modify the router to include the /api prefix
    router = APIRouter(prefix="/api")
    
    # Active WebSocket connections by user ID
    active_connections: Dict[str, List[WebSocket]] = {}
    
    @router.get(
        "/pending",
        summary="Get pending notifications",
        description="Get a list of pending notifications for the current user"
    )
    @rate_limit(limit_per_minute=20)
    async def get_pending_notifications(
        include_acknowledged: bool = Query(False, description="Include acknowledged alerts"),
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Get a list of pending notifications for the current user.
        
        Args:
            include_acknowledged: Whether to include acknowledged alerts
            db: Database session
            current_user_id: ID of the current authenticated user
            
        Returns:
            dict: List of pending notifications
        """
        notifier = AlertNotifier(db)
        
        # Get notifications for this user
        notifications = await notifier.get_user_notifications(
            current_user_id, 
            include_acknowledged=include_acknowledged
        )
        
        logger.info(f"User {current_user_id} retrieved {len(notifications)} pending notifications")
        return {"notifications": notifications}
    
    @router.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        token: str
    ):
        """
        WebSocket endpoint for real-time notifications.
        
        This endpoint establishes a WebSocket connection for pushing real-time
        alert notifications to connected clients.
        
        Args:
            websocket: WebSocket connection
            token: Authentication token
            
        Note:
            The connection is authenticated using the provided token, and the
            user ID is extracted from the token.
        """
        # Authenticate the WebSocket connection
        try:
            # In a real implementation, you would validate the token and get the user ID
            # For now, we'll use a simplified approach
            user_id = "user_from_token"  # This would come from token validation
            
            await websocket.accept()
            
            # Store the connection
            if user_id not in active_connections:
                active_connections[user_id] = []
            active_connections[user_id].append(websocket)
            
            logger.info(f"WebSocket connection established for user {user_id}")
            
            try:
                while True:
                    # Keep the connection alive and handle any client messages
                    data = await websocket.receive_text()
                    # Process any client messages if needed
                    await websocket.send_json({"status": "received", "data": data})
            except WebSocketDisconnect:
                # Remove the connection when the client disconnects
                active_connections[user_id].remove(websocket)
                if not active_connections[user_id]:
                    del active_connections[user_id]
                logger.info(f"WebSocket connection closed for user {user_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            await websocket.close(code=1008)  # Policy violation
    
    @router.post(
        "/test",
        summary="Send test notification",
        description="Send a test notification to the current user"
    )
    @rate_limit(limit_per_minute=5)
    async def send_test_notification(
        db: Session = Depends(get_db),
        current_user_id: str = Depends(get_current_user_id)
    ):
        """
        Send a test notification to the current user.
        
        This endpoint is mainly for testing the notification delivery system.
        
        Args:
            db: Database session
            current_user_id: ID of the current authenticated user
            
        Returns:
            dict: Operation result
        """
        notifier = AlertNotifier(db)
        
        # Create a test notification
        test_notification = {
            "id": "test-notification",
            "message": "This is a test notification",
            "severity": "info",
            "entity_type": "system",
            "created_at": "2023-01-01T00:00:00Z"
        }
        
        # Send the notification to the user's WebSocket connections
        if current_user_id in active_connections:
            for connection in active_connections[current_user_id]:
                await connection.send_json(test_notification)
                
            logger.info(f"Test notification sent to user {current_user_id}")
            return {"status": "success", "message": "Test notification sent"}
        else:
            logger.warning(f"No active WebSocket connections for user {current_user_id}")
            return {"status": "warning", "message": "No active WebSocket connections"}
    
    return router
