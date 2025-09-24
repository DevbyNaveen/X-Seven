"""
Real-time Voice WebSocket Handler

Handles WebSocket connections for real-time voice communication
with PipeCat AI integration.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Set
from datetime import datetime
import uuid
import base64

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from .integration_manager import get_voice_integration_manager
from .pipecat_config import get_pipecat_config

logger = logging.getLogger(__name__)


class VoiceWebSocketManager:
    """Manages WebSocket connections for voice communication."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.voice_sessions: Dict[str, Dict[str, Any]] = {}
        self.integration_manager = get_voice_integration_manager()
        
        logger.info("VoiceWebSocketManager initialized")
    
    async def connect(self, websocket: WebSocket, session_id: str) -> bool:
        """Accept WebSocket connection and initialize voice session."""
        try:
            await websocket.accept()
            
            self.active_connections[session_id] = websocket
            self.voice_sessions[session_id] = {
                "connected_at": datetime.now(),
                "status": "connected",
                "audio_buffer": [],
                "conversation_history": [],
                "metadata": {}
            }
            
            logger.info(f"WebSocket connected for session {session_id}")
            
            # Send welcome message
            await self.send_message(session_id, {
                "type": "connection_established",
                "session_id": session_id,
                "message": "Voice session connected",
                "timestamp": datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {e}")
            return False
    
    async def disconnect(self, session_id: str):
        """Disconnect WebSocket and cleanup session."""
        try:
            if session_id in self.active_connections:
                websocket = self.active_connections[session_id]
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close()
                
                del self.active_connections[session_id]
            
            if session_id in self.voice_sessions:
                self.voice_sessions[session_id]["status"] = "disconnected"
                self.voice_sessions[session_id]["disconnected_at"] = datetime.now()
                
                # Keep session data for a while for potential reconnection
                # In production, you might want to persist this to a database
            
            logger.info(f"WebSocket disconnected for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")
    
    async def send_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """Send message to WebSocket client."""
        try:
            if session_id not in self.active_connections:
                logger.warning(f"No active connection for session {session_id}")
                return False
            
            websocket = self.active_connections[session_id]
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.warning(f"WebSocket not connected for session {session_id}")
                return False
            
            await websocket.send_text(json.dumps(message))
            return True
            
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            return False
    
    async def send_audio(self, session_id: str, audio_data: bytes) -> bool:
        """Send audio data to WebSocket client."""
        try:
            if session_id not in self.active_connections:
                return False
            
            websocket = self.active_connections[session_id]
            if websocket.client_state != WebSocketState.CONNECTED:
                return False
            
            # Encode audio as base64 for JSON transmission
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            message = {
                "type": "audio_data",
                "session_id": session_id,
                "audio": audio_b64,
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send_text(json.dumps(message))
            return True
            
        except Exception as e:
            logger.error(f"Error sending audio data: {e}")
            return False
    
    async def handle_message(self, session_id: str, message: Dict[str, Any]):
        """Handle incoming WebSocket message."""
        try:
            message_type = message.get("type", "unknown")
            
            if message_type == "audio_data":
                await self._handle_audio_data(session_id, message)
            elif message_type == "text_message":
                await self._handle_text_message(session_id, message)
            elif message_type == "voice_command":
                await self._handle_voice_command(session_id, message)
            elif message_type == "session_control":
                await self._handle_session_control(session_id, message)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send_message(session_id, {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_message(session_id, {
                "type": "error",
                "message": f"Error processing message: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
    
    async def _handle_audio_data(self, session_id: str, message: Dict[str, Any]):
        """Handle incoming audio data."""
        try:
            audio_b64 = message.get("audio", "")
            if not audio_b64:
                return
            
            # Decode audio data
            audio_data = base64.b64decode(audio_b64)
            
            # Store in session buffer
            if session_id in self.voice_sessions:
                self.voice_sessions[session_id]["audio_buffer"].append({
                    "data": audio_data,
                    "timestamp": datetime.now(),
                    "size": len(audio_data)
                })
            
            # Process audio through voice pipeline
            await self._process_audio_through_pipeline(session_id, audio_data)
            
        except Exception as e:
            logger.error(f"Error handling audio data: {e}")
    
    async def _handle_text_message(self, session_id: str, message: Dict[str, Any]):
        """Handle text message (for testing or fallback)."""
        try:
            text = message.get("text", "")
            if not text:
                return
            
            # Store in conversation history
            if session_id in self.voice_sessions:
                self.voice_sessions[session_id]["conversation_history"].append({
                    "type": "user_text",
                    "content": text,
                    "timestamp": datetime.now()
                })
            
            # Process through voice integration
            result = await self.integration_manager.process_voice_call(session_id, {
                "message": text,
                "type": "text_input",
                "context": self.voice_sessions.get(session_id, {}).get("metadata", {})
            })
            
            # Send response
            response_text = result.get("message", "I understand your message.")
            await self.send_message(session_id, {
                "type": "text_response",
                "text": response_text,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Store response in history
            if session_id in self.voice_sessions:
                self.voice_sessions[session_id]["conversation_history"].append({
                    "type": "assistant_text",
                    "content": response_text,
                    "timestamp": datetime.now()
                })
            
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
    
    async def _handle_voice_command(self, session_id: str, message: Dict[str, Any]):
        """Handle voice commands (start recording, stop recording, etc.)."""
        try:
            command = message.get("command", "")
            
            if command == "start_recording":
                await self._start_voice_recording(session_id)
            elif command == "stop_recording":
                await self._stop_voice_recording(session_id)
            elif command == "mute":
                await self._mute_session(session_id)
            elif command == "unmute":
                await self._unmute_session(session_id)
            else:
                logger.warning(f"Unknown voice command: {command}")
                
        except Exception as e:
            logger.error(f"Error handling voice command: {e}")
    
    async def _handle_session_control(self, session_id: str, message: Dict[str, Any]):
        """Handle session control messages."""
        try:
            action = message.get("action", "")
            
            if action == "get_status":
                session_info = self.voice_sessions.get(session_id, {})
                await self.send_message(session_id, {
                    "type": "session_status",
                    "session_info": {
                        "status": session_info.get("status", "unknown"),
                        "connected_at": session_info.get("connected_at", datetime.now()).isoformat(),
                        "conversation_length": len(session_info.get("conversation_history", [])),
                        "audio_buffer_size": len(session_info.get("audio_buffer", []))
                    },
                    "timestamp": datetime.now().isoformat()
                })
            elif action == "clear_history":
                if session_id in self.voice_sessions:
                    self.voice_sessions[session_id]["conversation_history"] = []
                    self.voice_sessions[session_id]["audio_buffer"] = []
                
                await self.send_message(session_id, {
                    "type": "history_cleared",
                    "message": "Conversation history cleared",
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling session control: {e}")
    
    async def _process_audio_through_pipeline(self, session_id: str, audio_data: bytes):
        """Process audio data through the voice pipeline."""
        try:
            # This is a placeholder for actual audio processing
            # In a real implementation, you would:
            # 1. Convert audio to appropriate format
            # 2. Run speech-to-text
            # 3. Process through voice integration
            # 4. Generate response
            # 5. Convert response to audio
            # 6. Send back to client
            
            logger.info(f"Processing {len(audio_data)} bytes of audio for session {session_id}")
            
            # Mock processing - in reality this would be much more complex
            await asyncio.sleep(0.1)  # Simulate processing time
            
            # Send acknowledgment
            await self.send_message(session_id, {
                "type": "audio_processed",
                "message": "Audio received and processed",
                "audio_size": len(audio_data),
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
    
    async def _start_voice_recording(self, session_id: str):
        """Start voice recording for session."""
        if session_id in self.voice_sessions:
            self.voice_sessions[session_id]["recording"] = True
            self.voice_sessions[session_id]["recording_started"] = datetime.now()
        
        await self.send_message(session_id, {
            "type": "recording_started",
            "message": "Voice recording started",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _stop_voice_recording(self, session_id: str):
        """Stop voice recording for session."""
        if session_id in self.voice_sessions:
            self.voice_sessions[session_id]["recording"] = False
            self.voice_sessions[session_id]["recording_stopped"] = datetime.now()
        
        await self.send_message(session_id, {
            "type": "recording_stopped",
            "message": "Voice recording stopped",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _mute_session(self, session_id: str):
        """Mute voice session."""
        if session_id in self.voice_sessions:
            self.voice_sessions[session_id]["muted"] = True
        
        await self.send_message(session_id, {
            "type": "session_muted",
            "message": "Session muted",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _unmute_session(self, session_id: str):
        """Unmute voice session."""
        if session_id in self.voice_sessions:
            self.voice_sessions[session_id]["muted"] = False
        
        await self.send_message(session_id, {
            "type": "session_unmuted",
            "message": "Session unmuted",
            "timestamp": datetime.now().isoformat()
        })
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active voice sessions."""
        return {
            session_id: {
                "status": session_data.get("status", "unknown"),
                "connected_at": session_data.get("connected_at", datetime.now()).isoformat(),
                "conversation_length": len(session_data.get("conversation_history", [])),
                "audio_buffer_size": len(session_data.get("audio_buffer", [])),
                "recording": session_data.get("recording", False),
                "muted": session_data.get("muted", False)
            }
            for session_id, session_data in self.voice_sessions.items()
            if session_data.get("status") == "connected"
        }
    
    def get_session_metrics(self) -> Dict[str, Any]:
        """Get metrics about voice WebSocket sessions."""
        active_count = len([s for s in self.voice_sessions.values() if s.get("status") == "connected"])
        total_sessions = len(self.voice_sessions)
        
        return {
            "active_connections": active_count,
            "total_sessions": total_sessions,
            "disconnected_sessions": total_sessions - active_count,
            "average_session_duration": self._calculate_average_session_duration(),
            "total_audio_processed": self._calculate_total_audio_processed()
        }
    
    def _calculate_average_session_duration(self) -> float:
        """Calculate average session duration in seconds."""
        durations = []
        for session_data in self.voice_sessions.values():
            connected_at = session_data.get("connected_at")
            disconnected_at = session_data.get("disconnected_at", datetime.now())
            
            if connected_at:
                duration = (disconnected_at - connected_at).total_seconds()
                durations.append(duration)
        
        return sum(durations) / len(durations) if durations else 0.0
    
    def _calculate_total_audio_processed(self) -> int:
        """Calculate total audio data processed in bytes."""
        total_bytes = 0
        for session_data in self.voice_sessions.values():
            audio_buffer = session_data.get("audio_buffer", [])
            total_bytes += sum(item.get("size", 0) for item in audio_buffer)
        
        return total_bytes


# Global WebSocket manager instance
_websocket_manager: Optional[VoiceWebSocketManager] = None


def get_voice_websocket_manager() -> VoiceWebSocketManager:
    """Get the global voice WebSocket manager instance."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = VoiceWebSocketManager()
    return _websocket_manager


async def handle_voice_websocket(websocket: WebSocket, session_id: str = None):
    """Handle voice WebSocket connection."""
    if not session_id:
        session_id = str(uuid.uuid4())
    
    manager = get_voice_websocket_manager()
    
    # Connect WebSocket
    connected = await manager.connect(websocket, session_id)
    if not connected:
        return
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await manager.handle_message(session_id, message)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
                await manager.send_message(session_id, {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                })
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
    finally:
        await manager.disconnect(session_id)
