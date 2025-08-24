"""
Dedicated Chat Endpoints - Business Context Aware Chat API
Handles dedicated chat endpoints with business context awareness from entry points
"""
from __future__ import annotations

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import json
import uuid
import asyncio

from app.config.database import get_db
from app.services.ai.dedicatedchat.dedicated_chat_handler import DedicatedChatHandler

router = APIRouter()

# Track active websocket connections
active_connections: Dict[str, WebSocket] = {}


@router.post("/business/{business_identifier}")
async def dedicated_business_chat(
    business_identifier: str,
    request: Dict[str, Any], 
    db: Session = Depends(get_db)
):
    """
    Dedicated chat for a specific business with entry point context.
    
    This endpoint handles business-specific chats where the business context
    is known from the entry point (direct business chat, QR code, etc.)
    """
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "")
    context = request.get("context", {})
    entry_point = request.get("entry_point", "direct")  # direct, qr_code, business_link, etc.
    table_id = request.get("table_id")

    # Resolve business by numeric ID or slug
    from app.models import Business
    resolved_business = None
    if business_identifier.isdigit():
        resolved_business = db.query(Business).filter(Business.id == int(business_identifier)).first()
    else:
        resolved_business = db.query(Business).filter(Business.slug == business_identifier).first()

    if not resolved_business:
        return {"error": "Business not found", "session_id": session_id}
    business_id = resolved_business.id
    
    # Add business context
    context["business_id"] = business_id
    context["entry_point"] = entry_point
    if table_id:
        context["table_id"] = table_id

    if not message.strip():
        return {"error": "Message cannot be empty", "session_id": session_id}

    # Use Dedicated Chat Handler
    dedicated_handler = DedicatedChatHandler(db)
    response = await dedicated_handler.handle_dedicated_chat(
        message=message,
        session_id=session_id,
        business_id=business_id,
        entry_point=entry_point,
        table_id=table_id,
        context=context
    )
    
    return {
        "message": response.get("message", ""),
        "session_id": session_id,
        "success": response.get("success", True),
        "chat_type": "dedicated",
        "business_id": business_id,
        "entry_point": entry_point,
        "suggested_actions": [],
    }


@router.post("/business/{business_identifier}/initialize")
async def initialize_business_chat_session(
    business_identifier: str,
    request: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Initialize a new business chat session with welcome context.
    """
    session_id = request.get("session_id") or str(uuid.uuid4())
    entry_point = request.get("entry_point", "direct")
    
    # Resolve business by numeric ID or slug
    from app.models import Business
    if business_identifier.isdigit():
        business = db.query(Business).filter(Business.id == int(business_identifier)).first()
    else:
        business = db.query(Business).filter(Business.slug == business_identifier).first()

    if not business:
        return {"success": False, "error": "Business not found", "session_id": session_id}

    dedicated_handler = DedicatedChatHandler(db)
    result = await dedicated_handler.initialize_business_session(
        business_id=business.id,
        session_id=session_id,
        entry_point=entry_point
    )
    
    return result

# Alias for initialize with shorter path `/init`
@router.post("/business/{business_id}/init")
async def initialize_business_chat_session_alias(
    business_id: int,
    request: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Alias route to initialize a new business chat session using `/init`.
    """
    return await initialize_business_chat_session(str(business_id), request, db)

# Initialize by business slug to support frontend using slugs
@router.post("/business/slug/{business_slug}/init")
async def initialize_business_chat_session_by_slug(
    business_slug: str,
    request: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Initialize a business chat session using the business slug.
    """
    from app.models import Business
    business = db.query(Business).filter(Business.slug == business_slug).first()
    if not business:
        return {"success": False, "error": "Business not found", "slug": business_slug}

    # Rewrite to call the id-based initializer
    return await initialize_business_chat_session(str(business.id), request, db)


@router.get("/business/{business_identifier}/context")
async def get_business_context(
    business_identifier: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get business context information for the chat.
    """
    # Resolve business by numeric ID or slug
    from app.models import Business
    if business_identifier.isdigit():
        business = db.query(Business).filter(Business.id == int(business_identifier)).first()
    else:
        business = db.query(Business).filter(Business.slug == business_identifier).first()

    if not business:
        return {"error": "Business not found"}

    dedicated_handler = DedicatedChatHandler(db)
    context = await dedicated_handler.get_business_context_summary(
        business_id=business.id,
        session_id=session_id
    )
    
    return context

# Dedicated business chat by slug (POST messages)
@router.post("/business/slug/{business_slug}")
async def dedicated_business_chat_by_slug(
    business_slug: str,
    request: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Dedicated chat using the business slug instead of numeric ID.
    """
    from app.models import Business
    business = db.query(Business).filter(Business.slug == business_slug).first()
    if not business:
        session_id = request.get("session_id") or str(uuid.uuid4())
        return {"error": "Business not found", "session_id": session_id}

    # Rewrite to call the id-based handler
    return await dedicated_business_chat(str(business.id), request, db)


@router.websocket("/ws/business/{business_id}/{session_id}")
async def websocket_business_chat(
    websocket: WebSocket, 
    business_id: int,
    session_id: str, 
    entry_point: str = "direct",
    table_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    WebSocket for dedicated business chat with streaming and entry point context.
    """
    await websocket.accept()
    connection_key = f"business_{business_id}_{session_id}"
    active_connections[connection_key] = websocket

    # Get business info for welcome message
    from app.models import Business
    business = db.query(Business).filter(Business.id == business_id).first()
    business_name = business.name if business else f"Business {business_id}"

    await websocket.send_json({
        "type": "connected",
        "message": f"Connected to {business_name} chat",
        "chat_type": "dedicated",
        "business_id": business_id,
        "entry_point": entry_point
    })

    dedicated_handler = DedicatedChatHandler(db)

    try:
        while True:
            data = await websocket.receive_json()
            message_text = data.get("message", "").strip()
            context = data.get("context", {})
            
            # Add business context
            context["business_id"] = business_id
            context["entry_point"] = entry_point
            if table_id:
                context["table_id"] = table_id
            
            if not message_text:
                continue

            await websocket.send_json({"type": "typing_start"})
            
            try:
                # Get AI response
                response = await dedicated_handler.handle_dedicated_chat(
                    message=message_text,
                    session_id=session_id,
                    business_id=business_id,
                    entry_point=entry_point,
                    table_id=table_id,
                    context=context
                )
                
                full_message = response.get("message", "")
                
                # Stream word by word
                words = full_message.split(' ')
                streamed_text = ""
                
                for i, word in enumerate(words):
                    streamed_text += word
                    if i < len(words) - 1:
                        streamed_text += " "
                    
                    await asyncio.sleep(0.02)
                    
                    await websocket.send_json({
                        "type": "word",
                        "word": word,
                        "position": i,
                        "partial_message": streamed_text,
                    })
                
                # Send completion
                await websocket.send_json({
                    "type": "typing_complete",
                    "message": full_message,
                    "chat_type": "dedicated",
                    "business_id": business_id,
                    "entry_point": entry_point,
                    "success": response.get("success", True)
                })
                
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
        active_connections.pop(connection_key, None)
