from fastapi import WebSocket
from typing import List
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages active WebSocket connections and broadcasts messages to all connected clients.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection and add to active connections."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection from active connections."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Remaining connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected WebSocket clients."""
        if not self.active_connections:
            return

        import json
        message_str = json.dumps(message)
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                self.disconnect(connection)

# Global instance of the connection manager
manager = ConnectionManager()

def get_cors_config():
    """
    Returns CORS configuration for FastAPI middleware.
    
    Returns:
        dict: CORS configuration
    """
    # List of allowed origins (add your frontend URLs here)
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5501",
        "http://127.0.0.1:5501",
        "https://*.v0.dev",
        "https://v0.dev",
    ]
    
    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["*"],  # Allow all methods including OPTIONS
        "allow_headers": ["*"],
        "expose_headers": ["*"],
        "max_age": 600  # Cache preflight request for 10 minutes
    }

def init_websocket_endpoints(app):
    """
    Initialize WebSocket endpoints.
    
    Args:
        app: FastAPI application instance
    """
    @app.websocket("/ws/dashboard")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time dashboard updates."""
        await manager.connect(websocket)
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            manager.disconnect(websocket)

# Example usage in your FastAPI app:
# from app.ngrok_config import init_websocket_endpoints, get_cors_config
# app.add_middleware(CORSMiddleware, **get_cors_config())
# init_websocket_endpoints(app)
