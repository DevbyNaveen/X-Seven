"""Chat endpoints for customer interactions."""
from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import uuid
import asyncio
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
from app.services.ai import ConversationHandler
from app.services.ai.language_service import LanguageService # Import the new service

logger = logging.getLogger(__name__)

router = APIRouter()

# Create an instance of the LanguageService
language_service = LanguageService()

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

        # Detect language before processing
        detected_language_result = language_service.detect_language(request.message)
        detected_language = detected_language_result.detected_language.value

        # Create universal bot with business context
        from app.services.ai.universalbot.universal_bot import UniversalBot
        universal_bot = UniversalBot(db)

        # Process message through AI-driven conversation handler
        response = await universal_bot.process_message(
            session_id=request.session_id,
            message=request.message,
            channel="chat",
            phone_number=request.context.get("phone_number") if request.context else None,
            location=request.context.get("location") if request.context else None,
            language=detected_language,
            context={
                **request.context,
                "selected_business": (
                    business_id if business_id is not None 
                    else request.context.get("selected_business")
                ),
                "last_message": request.message,
                "channel": request.channel
            } if request.context else {
                "selected_business": business_id if business_id is not None else None,
                "last_message": request.message,
                "channel": request.channel
            }
        )

        return ChatResponse(
            message=response["message"],
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


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    table_id: Optional[int] = None,
):
    """
    WebSocket endpoint for real-time chat.
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

    conversation_handler = ConversationHandler(db)

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

                # Detect language in WebSocket messages
                detected_language_result = language_service.detect_language(message_text)
                detected_language = detected_language_result.detected_language.value

                # Optionally notify client that assistant is "typing" (no chain-of-thought content)
                if stream:
                    try:
                        await websocket.send_json({"type": "typing", "status": "start"})
                    except Exception:
                        pass

                response = await conversation_handler.process_message(
                    session_id=session_id,
                    message=message_text,
                    channel="websocket",
                    context={
                        **data.get("context", {}),
                        "selected_business": business_id,
                        "table_id": table_id
                    },
                    language=detected_language
                )

                # Optionally stream the message character-by-character to the client for a typewriter effect
                final_reply: str = response.get("message", "")
                if stream and final_reply:
                    try:
                        for ch in final_reply:
                            await websocket.send_json({"type": "token", "delta": ch})
                            await asyncio.sleep(0.002)  # adjust typing speed
                    except Exception:
                        # If streaming fails midway, fall back to sending the full message below
                        pass

                final_reply = response.get("message", "") #----------------

                # Stop typing indicator when streaming was enabled
                if stream:
                    try:
                        await websocket.send_json({"type": "typing", "status": "stop"})
                    except Exception:
                        pass

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