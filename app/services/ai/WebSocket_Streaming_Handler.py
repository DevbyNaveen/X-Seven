"""WebSocket Streaming Handler

Handles real-time streaming of AI responses with natural typing effects.
Integrates with the modern conversation handler for seamless user experience.
"""
from typing import Any, Dict, Optional, AsyncGenerator
import json
import asyncio
import logging
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.services.ai.modern_conversation_handler import ModernConversationHandler
from app.database import get_db


logger = logging.getLogger(__name__)


class WebSocketStreamingHandler:
    """Handles WebSocket connections for streaming AI responses."""
    
    def __init__(self):
        # Active connections tracking
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Accept WebSocket connection and track it."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.connection_metadata[session_id] = {
            "connected_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "message_count": 0
        }
        
        logger.info(f"WebSocket connected: {session_id}")
        
        # Send connection confirmation
        await self.send_message(websocket, {
            "type": "connection_established",
            "data": {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "message": "Connected to X-SevenAI"
            }
        })
    
    def disconnect(self, session_id: str) -> None:
        """Clean up connection tracking."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.connection_metadata:
            del self.connection_metadata[session_id]
        
        logger.info(f"WebSocket disconnected: {session_id}")
    
    async def handle_message(
        self,
        websocket: WebSocket,
        session_id: str,
        message_data: Dict[str, Any],
        db: Session
    ) -> None:
        """Handle incoming message and stream AI response."""
        try:
            # Update activity tracking
            if session_id in self.connection_metadata:
                self.connection_metadata[session_id]["last_activity"] = datetime.now().isoformat()
                self.connection_metadata[session_id]["message_count"] += 1
            
            # Extract message content and context
            user_message = message_data.get("message", "")
            context = message_data.get("context", {})
            phone_number = message_data.get("phone_number")
            location = message_data.get("location")
            
            if not user_message.strip():
                await self.send_error(websocket, "Empty message received")
                return
            
            # Initialize conversation handler
            conversation_handler = ModernConversationHandler(db)
            
            # Send typing indicator
            await self.send_message(websocket, {
                "type": "typing_start",
                "data": {"timestamp": datetime.now().isoformat()}
            })
            
            # Stream the AI response
            async for chunk in conversation_handler.stream_response(
                session_id=session_id,
                message=user_message,
                channel="websocket",
                context=context,
                phone_number=phone_number,
                location=location,
                delay_ms=30  # Natural typing speed
            ):
                await self.send_message(websocket, chunk)
            
            # Send typing end indicator
            await self.send_message(websocket, {
                "type": "typing_end",
                "data": {"timestamp": datetime.now().isoformat()}
            })
            
        except Exception as e:
            logger.error(f"Error handling message for session {session_id}: {e}")
            await self.send_error(websocket, f"Failed to process message: {str(e)}")
    
    async def send_message(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """Send message through WebSocket with error handling."""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
    
    async def send_error(self, websocket: WebSocket, error_message: str) -> None:
        """Send error message to client."""
        await self.send_message(websocket, {
            "type": "error",
            "data": {
                "message": error_message,
                "timestamp": datetime.now().isoformat()
            }
        })
    
    async def broadcast_to_session(self, session_id: str, message: Dict[str, Any]) -> None:
        """Broadcast message to specific session if connected."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await self.send_message(websocket, message)
    
    def get_connection_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get connection status and metadata."""
        if session_id in self.connection_metadata:
            return {
                "connected": True,
                "metadata": self.connection_metadata[session_id]
            }
        return {"connected": False}
    
    def get_active_connections_count(self) -> int:
        """Get count of active connections."""
        return len(self.active_connections)


# Global instance for WebSocket management
websocket_manager = WebSocketStreamingHandler()


async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Main WebSocket endpoint for streaming conversations."""
    try:
        # Connect to WebSocket
        await websocket_manager.connect(websocket, session_id)
        
        # Get database session
        db = next(get_db())
        
        # Handle messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Process message and stream response
                await websocket_manager.handle_message(
                    websocket, session_id, message_data, db
                )
                
            except WebSocketDisconnect:
                logger.info(f"Client disconnected: {session_id}")
                break
            except json.JSONDecodeError:
                await websocket_manager.send_error(websocket, "Invalid JSON format")
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                await websocket_manager.send_error(websocket, "Internal server error")
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Clean up connection
        websocket_manager.disconnect(session_id)
        db.close()


class StreamingResponse:
    """Helper class for creating streaming responses outside WebSocket context."""
    
    def __init__(self, db: Session):
        self.conversation_handler = ModernConversationHandler(db)
    
    async def stream_to_generator(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        phone_number: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream response as server-sent events."""
        
        async for chunk in self.conversation_handler.stream_response(
            session_id=session_id,
            message=message,
            channel="sse",
            context=context,
            phone_number=phone_number,
            location=location,
            delay_ms=25  # Slightly faster for SSE
        ):
            # Format as server-sent event
            chunk_json = json.dumps(chunk, ensure_ascii=False)
            yield f"data: {chunk_json}\n\n"
        
        # Send final event
        yield "data: [DONE]\n\n"
    
    async def get_complete_response(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        phone_number: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get complete response without streaming."""
        
        return await self.conversation_handler.process_message(
            session_id=session_id,
            message=message,
            channel="api",
            context=context,
            phone_number=phone_number,
            location=location
        )


# Utility functions for integration

async def send_notification_to_session(
    session_id: str,
    notification_type: str,
    data: Dict[str, Any]
) -> bool:
    """Send notification to specific session via WebSocket."""
    try:
        message = {
            "type": "notification",
            "notification_type": notification_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        await websocket_manager.broadcast_to_session(session_id, message)
        return True
        
    except Exception as e:
        logger.error(f"Failed to send notification to session {session_id}: {e}")
        return False


async def send_system_message_to_session(
    session_id: str,
    message: str,
    message_type: str = "info"
) -> bool:
    """Send system message to specific session."""
    try:
        system_message = {
            "type": "system_message",
            "data": {
                "message": message,
                "message_type": message_type,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await websocket_manager.broadcast_to_session(session_id, system_message)
        return True
        
    except Exception as e:
        logger.error(f"Failed to send system message to session {session_id}: {e}")
        return False


def get_session_connection_info(session_id: str) -> Dict[str, Any]:
    """Get connection information for a session."""
    return websocket_manager.get_connection_status(session_id)


def get_active_sessions_count() -> int:
    """Get count of active WebSocket sessions."""
    return websocket_manager.get_active_connections_count()