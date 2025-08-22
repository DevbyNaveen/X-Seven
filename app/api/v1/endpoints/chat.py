"""Chat endpoints for customer interactions with streaming support."""
from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import asyncio
import json
from datetime import datetime, timezone
import logging
from app.config.database import SessionLocal, get_db
from app.models import Message
from app.models.table import TableStatus, Table
from app.schemas.message import (
    ChatRequest,
    ChatResponse,
    ChatSession,
    MessageResponse
)
from app.services.websocket.connection_manager import manager
from app.services.ai.modern_conversation_handler import ModernConversationHandler

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Send a message to the chat bot.
    """
    # Ensure we always have a session_id to return even on errors
    if not request.session_id:
        request.session_id = str(uuid.uuid4())
        logger.info(f"Generated new session ID: {request.session_id}")
    else:
        logger.info(f"Using existing session ID: {request.session_id}")

    try:
        business_id = None
        if request.table_id:
            try:
                table = db.query(Table).filter(Table.id == request.table_id).first()
                if table:
                    business_id = table.business_id
            except Exception:
                business_id = None

        # Use modern conversation handler with rich context
        handler = ModernConversationHandler(db)
        
        response = await handler.process_message(
            session_id=request.session_id,
            message=request.message,
            channel="chat",
            phone_number=request.context.get("phone_number") if request.context else None,
            location=request.context.get("location") if request.context else None,
            context={
                **request.context,
                "selected_business": (
                    business_id if business_id is not None 
                    else request.context.get("selected_business")
                ),
                "channel": request.channel
            } if request.context else {
                "selected_business": business_id if business_id is not None else None,
                "channel": request.channel
            }
        )
        
        clean_message = response["message"]

        return ChatResponse(
            message=clean_message,
            session_id=request.session_id,
            suggested_actions=response.get("suggested_actions", []),
            metadata=response.get("metadata", {})
        )
    except Exception as e:
        logger.exception("Error in /api/v1/chat/message: %s", e)
        return ChatResponse(
            message="Sorry, something went wrong. Please try again shortly.",
            session_id=request.session_id,
            suggested_actions=[],
            metadata={"error": "internal_error"}
        )


@router.post("/stream")
async def stream_message(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Stream a response with typewriter effect for better UX.
    Returns Server-Sent Events (SSE) format.
    """
    # Ensure we always have a session_id
    if not request.session_id:
        request.session_id = str(uuid.uuid4())

    async def generate_stream():
        try:
            business_id = None
            if request.table_id:
                try:
                    table = db.query(Table).filter(Table.id == request.table_id).first()
                    if table:
                        business_id = table.business_id
                except Exception:
                    business_id = None

            # Use modern conversation handler for streaming
            handler = ModernConversationHandler(db)

            # Get streaming delay from request or use default
            delay_ms = request.context.get("typing_delay_ms", 50) if request.context else 50

            # Stream the response
            async for chunk in handler.stream_response(
                session_id=request.session_id,
                message=request.message,
                channel="http_stream",
                context={
                    **request.context,
                    "selected_business": (
                        business_id if business_id is not None 
                        else request.context.get("selected_business")
                    ),
                    "channel": request.channel
                } if request.context else {
                    "selected_business": business_id if business_id is not None else None,
                    "channel": request.channel
                },
                delay_ms=delay_ms
            ):
                # Format as Server-Sent Event
                yield f"data: {json.dumps(chunk)}\n\n"

        except Exception as e:
            logger.exception("Error in streaming: %s", e)
            error_chunk = {
                "type": "error",
                "data": {"message": "Sorry, something went wrong. Please try again shortly."}
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    table_id: Optional[int] = None,
):
    """
    WebSocket endpoint for real-time chat with streaming support.
    """
    await manager.connect(websocket, session_id)

    # Create DB session only after accepting the WebSocket to avoid blocking handshake
    db = SessionLocal()
    business_id = None
    table = None
    if table_id:
        table = db.query(Table).filter(Table.id == table_id).first()
        if table:
            business_id = table.business_id
            table.status = TableStatus.OCCUPIED
            db.commit()

    conversation_handler = ModernConversationHandler(db)

    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to X-SevenAI chat",
            "session_id": session_id
        })

        while True:
            try:
                data = await websocket.receive_json()
                message_text = data.get("message", "")
                stream: bool = bool(data.get("stream", False))
                typing_delay_ms: int = data.get("typing_delay_ms", 50)

                context = {
                    **data.get("context", {}),
                    "selected_business": business_id,
                    "table_id": table_id
                }

                if stream:
                    # Stream response character by character
                    try:
                        await websocket.send_json({"type": "typing_start"})
                        
                        async for chunk in conversation_handler.stream_response(
                            session_id=session_id,
                            message=message_text,
                            channel="websocket_stream",
                            context=context,
                            delay_ms=typing_delay_ms
                        ):
                            if chunk["type"] == "chunk":
                                # Send character-by-character updates
                                await websocket.send_json({
                                    "type": "typing_chunk",
                                    "character": chunk["data"]["character"],
                                    "position": chunk["data"]["position"],
                                    "partial_message": chunk["data"]["partial_message"]
                                })
                            elif chunk["type"] == "actions":
                                # Send actions when complete
                                await websocket.send_json({
                                    "type": "suggested_actions",
                                    "data": chunk["data"]
                                })
                            elif chunk["type"] == "metadata":
                                # Send metadata
                                await websocket.send_json({
                                    "type": "metadata",
                                    "data": chunk["data"]
                                })
                            elif chunk["type"] == "complete":
                                # Send completion signal
                                await websocket.send_json({
                                    "type": "typing_complete",
                                    "message": chunk["data"]["message"],
                                    "suggested_actions": chunk["data"]["suggested_actions"],
                                    "metadata": chunk["data"]["metadata"]
                                })
                                break
                                
                    except Exception as stream_error:
                        logger.exception("Streaming error: %s", stream_error)
                        await websocket.send_json({
                            "type": "error",
                            "message": "Streaming failed, falling back to regular response"
                        })
                        # Fall back to regular response
                        stream = False

                if not stream:
                    # Regular non-streaming response
                    response = await conversation_handler.process_message(
                        session_id=session_id,
                        message=message_text,
                        channel="websocket",
                        context=context
                    )

                    # Send only the final message
                    final_reply: str = response.get("message", "")
                    
                    await websocket.send_json({
                        "type": "message",
                        "message": final_reply,
                        "suggested_actions": response.get("suggested_actions", []),
                        "metadata": response.get("metadata", {})
                    })

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected: %s", session_id)
                break
            except RuntimeError as e:
                # Starlette raises RuntimeError after a disconnect if receive() is called again
                if "disconnect" in str(e).lower():
                    logger.info("WebSocket receive after disconnect for session %s; stopping loop", session_id)
                    break
                logger.exception("WebSocket runtime error: %s", e)
                try:
                    await websocket.send_json({"type": "error", "message": "Internal error. Please try again."})
                except Exception:
                    pass
            except Exception as e:
                logger.exception("Error handling WebSocket message: %s", e)
                try:
                    await websocket.send_json({"type": "error", "message": "Internal error. Please try again."})
                except Exception:
                    pass
    except WebSocketDisconnect:
        logger.info("WebSocketDisconnect caught for session %s", session_id)
    finally:
        # Always cleanup connection and table status
        manager.disconnect(session_id)
        if table_id and table:
            table.status = TableStatus.AVAILABLE
            db.commit()
        try:
            db.close()
        except Exception:
            pass


@router.get("/session/{session_id}", response_model=ChatSession)
async def get_session_info(
    session_id: str,
    db: Session = Depends(get_db)
) -> Any:
    """Get chat session information."""
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at).all()

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    first_message = messages[0]
    last_message = messages[-1]

    # Timezone-safe status calculation
    now_utc = datetime.now(timezone.utc)
    last_ts = last_message.created_at
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    else:
        last_ts = last_ts.astimezone(timezone.utc)

    return ChatSession(
        session_id=session_id,
        business_id=first_message.business_id,
        table_id=None,
        created_at=first_message.created_at,
        last_message_at=last_message.created_at,
        message_count=len(messages),
        status="active" if (now_utc - last_ts).total_seconds() < 3600 else "expired"
    )


@router.get("/session/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
) -> Any:
    """Get messages for a chat session."""
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at).limit(limit).offset(offset).all()

    return messages