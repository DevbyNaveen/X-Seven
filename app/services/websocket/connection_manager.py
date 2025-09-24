"""WebSocket connection manager for real-time updates."""
from typing import Dict, List, Any
from fastapi import WebSocket
import json


class ConnectionManager:
    """Manages WebSocket connections for real-time communication."""
    
    def __init__(self):
        # Store active connections by session ID
        self.active_connections: Dict[str, WebSocket] = {}
        # Store business connections for broadcasting
        self.business_connections: Dict[int, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and store a new connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        """Remove a connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        
        # Remove from business connections
        for business_id, sessions in self.business_connections.items():
            if session_id in sessions:
                sessions.remove(session_id)
    
    async def send_to_session(self, session_id: str, message: Dict[str, Any]):
        """Send message to specific session."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)
    
    async def broadcast_to_business(self, business_id: int, message: Dict[str, Any]):
        """Broadcast message to all connections for a business."""
        sessions = self.business_connections.get(business_id, [])
        for session_id in sessions:
            await self.send_to_session(session_id, message)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        for session_id in self.active_connections:
            await self.send_to_session(session_id, message)
    
    def add_to_business(self, session_id: str, business_id: int):
        """Add session to business group."""
        if business_id not in self.business_connections:
            self.business_connections[business_id] = []
        
        if session_id not in self.business_connections[business_id]:
            self.business_connections[business_id].append(session_id)
    
    def remove_from_business(self, session_id: str, business_id: int):
        """Remove session from business group."""
        if business_id in self.business_connections:
            if session_id in self.business_connections[business_id]:
                self.business_connections[business_id].remove(session_id)


# Create global instance
manager = ConnectionManager()