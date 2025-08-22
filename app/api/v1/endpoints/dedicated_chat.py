"""Dedicated chat endpoints for cafe-specific interactions."""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone
import logging
from app.config.database import SessionLocal, get_db
from app.models import Message, Business, Table
from app.models.table import TableStatus
from app.schemas.message import (
    ChatRequest,
    ChatResponse,
    ChatSession,
    MessageResponse
)
from app.services.websocket.connection_manager import manager
from app.services.ai import ConversationHandler
from app.services.ai.language_service import LanguageService

logger = logging.getLogger(__name__)

router = APIRouter()

# Create an instance of the LanguageService

language_service = LanguageService()

@router.post("/message/{business_id}", response_model=ChatResponse)
async def send_dedicated_message(
    business_id: int,
    request: ChatRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Send a message to a specific cafe's chat bot.
    This is for dedicated cafe interactions (QR code, website, dedicated WhatsApp/voice).
    """
    if not request.session_id:
        request.session_id = str(uuid.uuid4())
        logger.info(f"Generated new session ID: {request.session_id}")
    else:
        logger.info(f"Using existing session ID: {request.session_id}")

    # Verify business exists and is active
    business = db.query(Business).filter(
        Business.id == business_id,
        Business.is_active == True
    ).first()
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cafe not found or inactive"
        )

    # Detect language
    detected_language_result = language_service.detect_language(request.message)
    detected_language = detected_language_result.detected_language.value

    # Create universal bot with business context
    from app.services.ai.universalbot.universal_bot import UniversalBot
    universal_bot = UniversalBot(db)

    # Process message through AI-driven conversation handler with business context
    response = await universal_bot.process_message(
        session_id=request.session_id,
        message=request.message,
        channel="dedicated_chat",
        phone_number=request.context.get("phone_number") if request.context else None,
        location=request.context.get("location") if request.context else None,
        language=detected_language,
        context={
            **request.context,
            "business_id": business_id,
            "business_name": business.name,
            "channel": "dedicated_chat",
            "selected_business": business_id,
            "last_message": request.message
        } if request.context else {
            "business_id": business_id,
            "business_name": business.name,
            "channel": "dedicated_chat",
            "selected_business": business_id,
            "last_message": request.message
        }
    )

    return ChatResponse(
        message=response["message"],
        session_id=request.session_id,
        suggested_actions=response.get("suggested_actions", []),
        metadata={
            **response.get("metadata", {}),
            "business_id": business_id,
            "business_name": business.name
        }
    )

@router.websocket("/ws/{business_id}/{session_id}")
async def dedicated_websocket_endpoint(
    websocket: WebSocket,
    business_id: int,
    session_id: str,
    table_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time dedicated cafe chat.
    """
    await manager.connect(websocket, session_id)

    # Verify business exists
    business = db.query(Business).filter(
        Business.id == business_id,
        Business.is_active == True
    ).first()
    
    if not business:
        await websocket.send_json({
            "type": "error",
            "message": "Cafe not found or inactive"
        })
        await websocket.close()
        return

    # Update table status if table_id provided
    table = None
    if table_id:
        table = db.query(Table).filter(
            Table.id == table_id,
            Table.business_id == business_id
        ).first()
        if table:
            table.status = TableStatus.OCCUPIED
            db.commit()

    conversation_handler = ConversationHandler(db)

    try:
        await websocket.send_json({
            "type": "connected",
            "message": f"Connected to {business.name} chat",
            "session_id": session_id,
            "business_id": business_id,
            "business_name": business.name
        })

        while True:
            try:
                data = await websocket.receive_json()
                message_text = data.get("message", "")

                # Detect language
                detected_language_result = language_service.detect_language(message_text)
                detected_language = detected_language_result.detected_language.value

                response = await conversation_handler.process_message(
                    session_id=session_id,
                    message=message_text,
                    channel="dedicated_websocket",
                    context={
                        **data.get("context", {}),
                        "business_id": business_id,
                        "business_name": business.name,
                        "selected_business": business_id,
                        "table_id": table_id
                    },
                    language=detected_language
                )

                await websocket.send_json({
                    "type": "message",
                    "message": response["message"],
                    "suggested_actions": response.get("suggested_actions", []),
                    "metadata": {
                        **response.get("metadata", {}),
                        "business_id": business_id,
                        "business_name": business.name
                    }
                })
            except Exception as e:
                logger.exception("Error handling dedicated WebSocket message: %s", e)
                try:
                    await websocket.send_json({"type": "error", "message": "Internal error. Please try again."})
                except Exception:
                    pass

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        if table_id and table:
            table.status = TableStatus.AVAILABLE
            db.commit()

@router.get("/session/{business_id}/{session_id}", response_model=ChatSession)
async def get_dedicated_session_info(
    business_id: int,
    session_id: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Get session information for a specific cafe.
    """
    # Verify business exists
    business = db.query(Business).filter(
        Business.id == business_id,
        Business.is_active == True
    ).first()
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cafe not found or inactive"
        )

    # Collect messages for this session and business
    messages = db.query(Message).filter(
        Message.session_id == session_id,
        Message.business_id == business_id,
    ).order_by(Message.created_at).all()

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    first_message = messages[0]
    last_message = messages[-1]
    # Ensure timezone-aware calculation
    now_utc = datetime.now(timezone.utc)
    last_ts = last_message.created_at
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    else:
        last_ts = last_ts.astimezone(timezone.utc)
    status_str = "active" if (now_utc - last_ts).total_seconds() < 3600 else "expired"

    return ChatSession(
        session_id=session_id,
        business_id=business_id,
        table_id=None,
        created_at=first_message.created_at,
        last_message_at=last_message.created_at,
        message_count=len(messages),
        status=status_str,
    )

@router.get("/business/{business_id}/info")
async def get_business_info(
    business_id: int,
    db: Session = Depends(get_db)
) -> Any:
    """
    Get business information for dedicated chat.
    """
    business = db.query(Business).filter(
        Business.id == business_id,
        Business.is_active == True
    ).first()
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cafe not found or inactive"
        )
    
    return {
        "id": business.id,
        "name": business.name,
        "description": business.description,
        "contact_info": business.contact_info,
        "settings": business.settings,
        "branding_config": business.branding_config
    }
