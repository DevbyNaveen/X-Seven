"""
Simple chat endpoints (HTTP + WebSocket) powered by SimpleAIHandler.
Replaces complex chat handlers with a minimal, maintainable version.
"""
from __future__ import annotations

from typing import Dict, Any
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json
import uuid
import asyncio

from app.config.database import get_db
from app.services.ai.simple_ai_handler import SimpleAIHandler

router = APIRouter()

# Track active websocket connections if needed later
active_connections: Dict[str, WebSocket] = {}


@router.post("/message")
async def chat_message(request: Dict[str, Any], db: Session = Depends(get_db)):
    """Simple chat endpoint like modern AI companies."""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "")
    context = request.get("context", {})

    if not message.strip():
        return {"error": "Message cannot be empty", "session_id": session_id}

    ai = SimpleAIHandler(db)
    response = await ai.chat(message, session_id, context)
    
    return {
        "message": response.get("message", ""),
        "session_id": session_id,
        "success": response.get("success", True),
        "metadata": {k: v for k, v in response.items() if k not in {"message", "success", "session_id"}},
    }


@router.get("/stream/{session_id}")
async def stream_chat(
    session_id: str,
    message: str,
    db: Session = Depends(get_db)
):
    """Stream AI response with typewriter effect using Server-Sent Events."""
    
    ai = SimpleAIHandler(db)
    
    async def generate_stream():
        try:
            resp = await ai.chat(message, session_id)
            full_message = resp.get("message", "")
            # Typewriter effect: stream one character at a time
            for i, ch in enumerate(full_message):
                await asyncio.sleep(0.015)
                yield (
                    "data: "
                    + json.dumps({
                        "type": "character",
                        "data": {
                            "character": ch,
                            "position": i,
                            "partial_message": full_message[: i + 1],
                        },
                    })
                    + "\n\n"
                )
            # Completion event
            yield (
                "data: "
                + json.dumps({
                    "type": "complete",
                    "data": {"full_message": full_message},
                })
                + "\n\n"
            )
        except Exception as e:
            error_chunk = {"type": "error", "data": {"message": str(e)}}
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)):
    """WebSocket chat with natural typing effect."""
    await websocket.accept()
    active_connections[session_id] = websocket

    await websocket.send_json({
        "type": "connected",
        "message": "Connected to X-SevenAI! How can I help you today?"
    })

    ai = SimpleAIHandler(db)

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except:
                message_data = {"message": data}

            user_message = message_data.get("message", "").strip()
            context = message_data.get("context", {})
            
            if not user_message:
                continue

            # Send typing indicator
            await websocket.send_json({"type": "typing_start"})

            # Get full AI response then typewriter it over WebSocket
            try:
                resp = await ai.chat(user_message, session_id, context)
                full_message = resp.get("message", "")
                for i, ch in enumerate(full_message):
                    await asyncio.sleep(0.015)
                    await websocket.send_json({
                        "type": "character",
                        "character": ch,
                        "position": i,
                        "partial_message": full_message[: i + 1],
                    })
                await websocket.send_json({
                    "type": "message_complete",
                    "full_message": full_message,
                })
            except Exception as e:
                try:
                    await websocket.send_json({"type": "error", "message": str(e)})
                except:
                    pass

            await websocket.send_json({"type": "typing_end"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        active_connections.pop(session_id, None)
