# app/api/v1/endpoints/central_chat_endpoints.py
"""
Unified Chat Endpoints - Consolidated API for all chat types
Handles global, dedicated, and dashboard chat through Central AI Brain
"""
from __future__ import annotations

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json
import uuid
import asyncio

from app.config.database import get_db
from app.services.ai import CentralAIHandler, ChatType
from app.core.dependencies import get_current_business, get_current_user
from app.models import Message, Business, User

router = APIRouter()

# Track active websocket connections
active_connections: Dict[str, WebSocket] = {}


@router.post("/global")
async def global_chat(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    stream: bool = Query(False, description="If true, stream the response word‑by‑word (typewriter effect)"),
    action: Optional[str] = Query(None, description="Optional action: 'recommendations' or 'search'"),
) -> Any:
    """Global discovery chat across all businesses.

    - When `stream=False` (default) the endpoint behaves like the original JSON response.
    - When `stream=True` it returns a `StreamingResponse` that yields Server‑Sent Events
      containing each word of the AI answer, mimicking the previous `/stream/global/...`
      endpoint.
    """
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "")
    context = request.get("context", {})

    if not message.strip():
        return {"error": "Message cannot be empty", "session_id": session_id}

    # If an explicit action is requested, handle it specially
    if action == "recommendations":
        # Recommendations flow – same as the original /recommendations endpoint
        preferences = request.get("preferences", {})
        central_ai = CentralAIHandler(db)
        rec_response = await central_ai.chat(
            message="Get business recommendations",
            session_id=session_id,
            chat_type=ChatType.GLOBAL,
            context={"action": "recommendations", "preferences": preferences},
        )
        return {
            "recommendations": rec_response.get("message", ""),
            "session_id": session_id,
            "success": rec_response.get("success", True),
        }

    if action == "search":
        # Search flow – same as the original /search endpoint
        query = request.get("query", "")
        filters = request.get("filters", {})
        if not query.strip():
            return {"error": "Search query cannot be empty", "session_id": session_id}
        central_ai = CentralAIHandler(db)
        search_response = await central_ai.chat(
            message=query,
            session_id=session_id,
            chat_type=ChatType.GLOBAL,
            context={"action": "search", "filters": filters},
        )
        return {"results": search_response.get("message", ""), "success": True}

    # Default: normal global chat (same as before)
    # Use Central AI with global chat type
    central_ai = CentralAIHandler(db)
    response = await central_ai.chat(
        message=message,
        session_id=session_id,
        chat_type=ChatType.GLOBAL,
        context=context,
    )

    if not stream:
        # Normal JSON response
        return {
            "message": response.get("message", ""),
            "session_id": session_id,
            "success": response.get("success", True),
            "chat_type": "global",
            "suggested_actions": [],
        }

    # Streaming response (typewriter effect)
    async def generate_stream() -> Any:
        full_message = response.get("message", "")
        words = full_message.split(" ")
        streamed_text = ""
        for i, word in enumerate(words):
            streamed_text += word
            if i < len(words) - 1:
                streamed_text += " "
            # Small delay to simulate typing
            await asyncio.sleep(0.05)
            data_chunk = {
                "type": "word",
                "word": word,
                "position": i,
                "partial_message": streamed_text,
            }
            yield "data: " + json.dumps(data_chunk) + "\n\n"
        # Completion event
        complete_chunk = {
            "type": "complete",
            "message": full_message,
            "chat_type": "global",
        }
        yield "data: " + json.dumps(complete_chunk) + "\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.delete("/dashboard/{business_id}/{session_id}")
async def delete_dashboard_conversation(
    business_id: int,
    session_id: str,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete all messages for a dashboard chat session scoped to a business.

    Secured: requires authenticated user and that user's business matches the path business_id.
    """
    # Ensure the authenticated user's business matches the requested business_id
    if business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this business's conversations",
        )

    # Delete messages for this session and business
    deleted = db.query(Message).filter(
        Message.session_id == session_id,
        Message.business_id == business_id,
    ).delete(synchronize_session=False)
    db.commit()

    return {
        "status": "success",
        "deleted": deleted,
        "session_id": session_id,
        "business_id": business_id,
    }


@router.post("/dedicated/{business_identifier}")
async def dedicated_chat(
    business_identifier: str,
    request: Dict[str, Any], 
    db: Session = Depends(get_db)
):
    """Dedicated chat for a specific business."""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "")
    context = request.get("context", {})
    entry_point = request.get("entry_point", "direct")
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
    context["selected_business"] = business_id
    context["entry_point"] = entry_point
    if table_id:
        context["table_id"] = table_id

    # If no message is provided, treat this as a session initialization request
    if not message.strip():
        # Initialize session – same logic as the removed init endpoint
        central_ai = CentralAIHandler(db)
        init_response = await central_ai.chat(
            message="initialize_session",
            session_id=session_id,
            chat_type=ChatType.DEDICATED,
            context={
                "action": "initialize_session",
                "business_id": business_id,
                "entry_point": entry_point,
            },
        )
        # Also fetch business context for the newly created session
        context_response = await central_ai.chat(
            message="get_business_context",
            session_id=session_id,
            chat_type=ChatType.DEDICATED,
            context={
                "action": "get_business_context",
                "business_id": business_id,
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            "business_id": business_id,
            "business_name": resolved_business.name,
            "welcome_message": init_response.get("message", ""),
            "entry_point": entry_point,
            "business_context": context_response.get("message", ""),
        }

    # Use Central AI with dedicated chat type for normal messages
    central_ai = CentralAIHandler(db)
    response = await central_ai.chat(
        message=message,
        session_id=session_id,
        chat_type=ChatType.DEDICATED,
        context=context,
    )
    # Fetch business context to include in the response
    context_response = await central_ai.chat(
        message="get_business_context",
        session_id=session_id,
        chat_type=ChatType.DEDICATED,
        context={
            "action": "get_business_context",
            "business_id": business_id,
        },
    )
    
    return {
        "message": response.get("message", ""),
        "session_id": session_id,
        "success": response.get("success", True),
        "chat_type": "dedicated",
        "business_id": business_id,
        "entry_point": entry_point,
        "suggested_actions": [],
        "business_context": context_response.get("message", ""),
    }


@router.post("/dashboard")
async def dashboard_chat(
    request: Dict[str, Any], 
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Dashboard management chat for business owners."""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "")
    context = request.get("context", {})
    
    # Business ID comes from authentication context
    business_id = current_business.id
    context["business_id"] = business_id

    if not message.strip():
        return {"error": "Message cannot be empty", "session_id": session_id}

    # Use Central AI with dashboard chat type
    central_ai = CentralAIHandler(db)
    response = await central_ai.chat(
        message=message,
        session_id=session_id,
        chat_type=ChatType.DASHBOARD,
        context=context
    )
    
    return {
        "message": response.get("message", ""),
        "session_id": session_id,
        "success": response.get("success", True),
        "chat_type": "dashboard",
        "business_id": business_id,
        "suggested_actions": [],
    }












@router.websocket("/ws/global/{session_id}")
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
        "chat_type": "global"
    })

    central_ai = CentralAIHandler(db)

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
                response = await central_ai.chat(
                    message=message_text,
                    session_id=session_id,
                    chat_type=ChatType.GLOBAL,
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
                    
                    await asyncio.sleep(0.02)  # 20ms delay per word
                    
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
                    "chat_type": "global",
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
        active_connections.pop(session_id, None)


@router.websocket("/ws/dedicated/{business_identifier}/{session_id}")
async def websocket_dedicated_chat(
    websocket: WebSocket, 
    business_identifier: str,
    session_id: str, 
    table_id: int = None,
    db: Session = Depends(get_db)
):
    """WebSocket for dedicated business chat with streaming."""
    await websocket.accept()
    
    # Resolve business by numeric ID or slug
    from app.models import Business
    resolved_business = None
    if business_identifier.isdigit():
        resolved_business = db.query(Business).filter(Business.id == int(business_identifier)).first()
    else:
        resolved_business = db.query(Business).filter(Business.slug == business_identifier).first()

    if not resolved_business:
        await websocket.send_json({
            "type": "error",
            "message": "Business not found"
        })
        await websocket.close()
        return
    
    business_id = resolved_business.id
    active_connections[f"{business_id}_{session_id}"] = websocket

    business_name = resolved_business.name if resolved_business else f"Business {business_id}"

    await websocket.send_json({
        "type": "connected",
        "message": f"Connected to {business_name} chat",
        "chat_type": "dedicated",
        "business_id": business_id
    })

    central_ai = CentralAIHandler(db)

    try:
        while True:
            data = await websocket.receive_json()
            message_text = data.get("message", "").strip()
            context = data.get("context", {})
            
            # Add business context
            context["business_id"] = business_id
            context["selected_business"] = business_id
            context["entry_point"] = "direct"
            if table_id:
                context["table_id"] = table_id
            
            if not message_text:
                continue

            await websocket.send_json({"type": "typing_start"})
            
            try:
                # Get AI response
                response = await central_ai.chat(
                    message=message_text,
                    session_id=session_id,
                    chat_type=ChatType.DEDICATED,
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
        active_connections.pop(f"{business_id}_{session_id}", None)


@router.websocket("/ws/dashboard/{business_id}/{session_id}")
async def websocket_dashboard_chat(
    websocket: WebSocket, 
    business_id: int,
    session_id: str, 
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """WebSocket for dashboard management chat."""
    await websocket.accept()
    active_connections[f"dashboard_{business_id}_{session_id}"] = websocket

    # Get business info
    from app.models import Business
    business = db.query(Business).filter(Business.id == business_id).first()
    business_name = business.name if business else f"Business {business_id}"

    await websocket.send_json({
        "type": "connected",
        "message": f"Connected to {business_name} management dashboard",
        "chat_type": "dashboard",
        "business_id": business_id
    })

    central_ai = CentralAIHandler(db)

    try:
        while True:
            data = await websocket.receive_json()
            message_text = data.get("message", "").strip()
            context = data.get("context", {})
            
            # Add business context
            context["business_id"] = business_id
            
            if not message_text:
                continue

            await websocket.send_json({"type": "typing_start"})
            
            try:
                # Get AI response
                response = await central_ai.chat(
                    message=message_text,
                    session_id=session_id,
                    chat_type=ChatType.DASHBOARD,
                    context=context
                )
                
                full_message = response.get("message", "")
                
                # Stream word by word (faster for dashboard - business users want efficiency)
                words = full_message.split(' ')
                streamed_text = ""
                
                for i, word in enumerate(words):
                    streamed_text += word
                    if i < len(words) - 1:
                        streamed_text += " "
                    
                    await asyncio.sleep(0.01)  # Faster for business users
                    
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
                    "chat_type": "dashboard",
                    "business_id": business_id,
                    "success": response.get("success", True)
                })
                
            except Exception as e:
                await websocket.send_json({
                    "type": "error", 
                    "message": "Management system temporarily unavailable. Please try again."
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
        active_connections.pop(f"dashboard_{business_id}_{session_id}", None)