# app/services/ai/globalAI/global_chat_handler.py
"""
Global Chat Endpoints - Fixed for Seamless Context
"""
from __future__ import annotations

from typing import Dict, Any
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import json
import uuid
import asyncio

from app.config.database import get_db
from app.services.ai.globalAI.global_chat_handler import GlobalChatHandler

router = APIRouter()

# Track active websocket connections
active_connections: Dict[str, WebSocket] = {}


@router.post("")
async def global_chat(request: Dict[str, Any], db: Session = Depends(get_db)):
    """Global discovery chat across all businesses."""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "")
    context = request.get("context", {})

    if not message.strip():
        return {"error": "Message cannot be empty", "session_id": session_id}

    # Use Global Chat Handler
    global_handler = GlobalChatHandler(db)
    response = await global_handler.handle_global_chat(
        message=message,
        session_id=session_id,
        context=context
    )
    
    # Preserve all response data
    result = {
        "message": response.get("message", ""),
        "session_id": session_id,
        "success": response.get("success", True),
        "chat_type": response.get("chat_type", "global"),
    }
    
    # Include routing information if present
    if response.get("route_to"):
        result["route_to"] = response["route_to"]
    
    return result


@router.post("/recommendations")
async def get_recommendations(request: Dict[str, Any], db: Session = Depends(get_db)):
    """Get personalized business recommendations."""
    session_id = request.get("session_id") or str(uuid.uuid4())
    user_preferences = request.get("preferences", {})
    
    global_handler = GlobalChatHandler(db)
    response = await global_handler.get_business_recommendations(
        user_preferences=user_preferences,
        session_id=session_id
    )
    
    return {
        "recommendations": response.get("message", ""),
        "session_id": session_id,
        "success": response.get("success", True),
    }


@router.post("/search")
async def search_businesses(request: Dict[str, Any], db: Session = Depends(get_db)):
    """Search for businesses based on query."""
    query = request.get("query", "")
    filters = request.get("filters", {})
    
    if not query.strip():
        return {"error": "Search query cannot be empty"}
    
    global_handler = GlobalChatHandler(db)
    results = await global_handler.search_businesses(
        query=query,
        filters=filters
    )
    
    return {
        "results": results,
        "success": True,
    }


@router.websocket("/ws/{session_id}")
async def websocket_global_chat(
    websocket: WebSocket, 
    session_id: str, 
    db: Session = Depends(get_db)
):
    """WebSocket for global chat with streaming."""
    await websocket.accept()
    active_connections[session_id] = websocket

    await websocket.send_json({
        "type": "connected",
        "message": "Connected to X-SevenAI global chat",
        "chat_type": "global",
        "session_id": session_id
    })

    global_handler = GlobalChatHandler(db)

    try:
        while True:
            data = await websocket.receive_json()
            message_text = data.get("message", "").strip()
            context = data.get("context", {})
            
            if not message_text:
                continue

            # Send typing indicator
            await websocket.send_json({"type": "typing_start"})
            
            try:
                # Get AI response
                response = await global_handler.handle_global_chat(
                    message=message_text,
                    session_id=session_id,  # Use same session_id
                    context=context
                )
                
                full_message = response.get("message", "")
                
                # Prepare complete response
                result = {
                    "type": "message",
                    "message": full_message,
                    "session_id": session_id,
                    "success": response.get("success", True),
                    "chat_type": response.get("chat_type", "global"),
                }
                
                # Include routing info if present
                if response.get("route_to"):
                    result["route_to"] = response["route_to"]
                
                # Stream word by word
                words = full_message.split(' ')
                streamed_text = ""
                
                for i, word in enumerate(words):
                    streamed_text += word
                    if i < len(words) - 1:
                        streamed_text += " "
                    
                    await asyncio.sleep(0.02)  # 20ms delay per word
                    
                    await websocket.send_json({
                        "type": "word",
                        "word": word,
                        "position": i,
                        "partial_message": streamed_text,
                    })
                
                # Send completion with full context
                await websocket.send_json(result)
                
            except Exception as e:
                await websocket.send_json({
                    "type": "error", 
                    "message": "Sorry, something went wrong. Please try again."
                })

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