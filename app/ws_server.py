"""
WebSocket server module for simple_kaapi
This module provides a separate FastAPI application specifically for WebSocket connections
without any security middleware that might interfere with WebSocket handshakes.
"""

import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ws_server")

# Create a FastAPI application dedicated to WebSockets
app = FastAPI(title="Kaapi WebSocket Server")

# Configure CORS - accept all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, limit to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple classe de gestionnaire de connexions WebSocket
class ConnectionManager:
    def __init__(self):
        # Structure: {conversation_id: {user_id: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, conversation_id: str, user_id: str = "anonymous"):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = {}
        self.active_connections[conversation_id][user_id] = websocket
        logger.info(f"User {user_id} connected to conversation {conversation_id}")
        
    def disconnect(self, conversation_id: str, user_id: str = "anonymous"):
        if conversation_id in self.active_connections:
            if user_id in self.active_connections[conversation_id]:
                del self.active_connections[conversation_id][user_id]
                logger.info(f"User {user_id} disconnected from conversation {conversation_id}")
            
            # Remove conversation if empty
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]
                
    async def broadcast_to_conversation(self, message: Dict[str, Any], conversation_id: str, exclude_user: str = None):
        if conversation_id in self.active_connections:
            for user_id, connection in self.active_connections[conversation_id].items():
                if exclude_user and user_id == exclude_user:
                    continue
                await connection.send_json(message)


# Create the connection manager
manager = ConnectionManager()

# WebSocket test route - no authentication required
@app.websocket(f"{settings.API_PREFIX}/ws-test")
async def websocket_test(websocket: WebSocket):
    await websocket.accept()
    try:
        # Send a welcome message
        await websocket.send_json({"status": "connected", "message": "Test connection successful"})
        
        # Simple echo loop
        while True:
            data = await websocket.receive_text()
            # Echo the received message
            await websocket.send_json({"echo": data})
    except WebSocketDisconnect:
        logger.info("Client disconnected from test WebSocket")

# WebSocket route with conversation ID
@app.websocket(f"{settings.API_PREFIX}/ws/{{conversation_id}}")
async def websocket_endpoint(
    websocket: WebSocket, 
    conversation_id: str, 
    token: Optional[str] = Query(None),
    user_id: Optional[str] = Query("anonymous")
):
    """
    Endpoint WebSocket without authentication for development
    Accepts all connections and provides an echo service
    """
    # Log for debugging
    logger.info(f"WebSocket connection attempt to conversation {conversation_id}")
    if token:
        logger.info(f"Token provided: {token[:10]}...")
    
    # Accept the connection without verification
    await manager.connect(websocket, conversation_id, user_id)
    
    try:
        # Send a confirmation message
        await websocket.send_json({
            "type": "connection_established",
            "data": {
                "conversation_id": conversation_id,
                "user_id": user_id
            }
        })
        
        # Main loop to receive messages
        while True:
            # Wait for messages
            data = await websocket.receive_json()
            
            # Log the received message
            logger.info(f"Message from user {user_id} in conversation {conversation_id}: {data}")
            
            # Determine message type
            message_type = data.get("type", "text")
            
            # Process message based on type
            if message_type == "text":
                # Create a structured message for broadcast
                message_to_broadcast = {
                    "type": "message",
                    "data": {
                        "id": data.get("id", "unknown"),
                        "sender_id": user_id,
                        "conversation_id": conversation_id,
                        "content": data.get("content", ""),
                        "timestamp": data.get("timestamp", ""),
                    }
                }
                
                # Broadcast to all participants in the conversation (excluding sender)
                await manager.broadcast_to_conversation(
                    message_to_broadcast, 
                    conversation_id,
                    exclude_user=None  # Optional: exclude sender with user_id
                )
                
                # Confirm message receipt to sender
                await websocket.send_json({
                    "type": "message_received",
                    "data": {
                        "message_id": data.get("id", "unknown")
                    }
                })
            
            elif message_type == "typing":
                # Broadcast typing indicator
                await manager.broadcast_to_conversation(
                    {
                        "type": "typing",
                        "data": {
                            "user_id": user_id,
                            "is_typing": data.get("is_typing", False)
                        }
                    },
                    conversation_id,
                    exclude_user=user_id
                )
    
    except WebSocketDisconnect:
        # Handle disconnection
        manager.disconnect(conversation_id, user_id)
        
        # Inform other users of the disconnection
        await manager.broadcast_to_conversation(
            {
                "type": "user_offline",
                "data": {
                    "user_id": user_id
                }
            },
            conversation_id
        )
    
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
        manager.disconnect(conversation_id, user_id)


if __name__ == "__main__":
    import uvicorn
    # Launch the server on port 8001 to avoid conflicts with the main API
    uvicorn.run("ws_server:app", host="0.0.0.0", port=8001, reload=True)
