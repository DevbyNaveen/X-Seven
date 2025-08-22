"""Voice call system endpoints."""
from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User, Order, Message
from app.services.ai.voice_handler import VoiceHandler
from app.services.external.twilio_service import TwilioService
from app.schemas.voice_calls import (
    VoiceCallCreate,
    VoiceCallResponse,
    VoiceCallStatus,
    VoiceCallHistory,
    VoiceCallAnalytics,
    VoiceCallSettings
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/initiate", response_model=VoiceCallResponse)
async def initiate_voice_call(
    call_data: VoiceCallCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Initiate a voice call to a customer.
    """
    voice_handler = VoiceHandler(db)
    twilio_service = TwilioService(db)
    
    try:
        # Validate business has voice capabilities
        if not business.phone_features.get("voice_enabled", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voice calls not enabled for this business"
            )
        
        # Check usage limits
        current_usage = business.phone_usage.get("voice_minutes_used", 0)
        plan_limits = {
            "basic": 500,
            "pro": 2000,
            "enterprise": 10000
        }
        limit = plan_limits.get(business.subscription_plan.value, 500)
        
        if current_usage >= limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voice minutes limit exceeded"
            )
        
        # Initiate call
        call_result = await twilio_service.initiate_voice_call(
            to_number=call_data.phone_number,
            from_number=business.custom_phone_number or business.phone_config,
            business_id=business.id,
            call_type=call_data.call_type,
            context=call_data.context
        )
        
        return VoiceCallResponse(
            id=call_result["call_sid"],
            status=VoiceCallStatus.INITIATING,
            from_number=call_result["from_number"],
            to_number=call_result["to_number"],
            duration=0,
            created_at=datetime.utcnow(),
            business_id=business.id,
            call_type=call_data.call_type,
            cost=0.0
        )
        
    except Exception as e:
        logger.error(f"Error initiating voice call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error initiating voice call: {str(e)}"
        )


@router.get("/active", response_model=List[VoiceCallResponse])
async def get_active_calls(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get currently active voice calls.
    """
    twilio_service = TwilioService(db)
    
    try:
        active_calls = await twilio_service.get_active_calls(
            business_id=business.id
        )
        
        return [
            VoiceCallResponse(
                id=call["call_sid"],
                status=VoiceCallStatus(call["status"]),
                from_number=call["from_number"],
                to_number=call["to_number"],
                duration=call.get("duration", 0),
                created_at=datetime.fromisoformat(call["created_at"]),
                business_id=business.id,
                call_type=call.get("call_type", "outbound"),
                cost=call.get("cost", 0.0)
            )
            for call in active_calls
        ]
        
    except Exception as e:
        logger.error(f"Error getting active calls: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting active calls: {str(e)}"
        )


@router.get("/history", response_model=List[VoiceCallHistory])
async def get_call_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[VoiceCallStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get voice call history.
    """
    twilio_service = TwilioService(db)
    
    try:
        calls = await twilio_service.get_call_history(
            business_id=business.id,
            status=status.value if status else None,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )
        
        return [
            VoiceCallHistory(
                id=call["call_sid"],
                status=VoiceCallStatus(call["status"]),
                from_number=call["from_number"],
                to_number=call["to_number"],
                duration=call.get("duration", 0),
                created_at=datetime.fromisoformat(call["created_at"]),
                ended_at=datetime.fromisoformat(call["ended_at"]) if call.get("ended_at") else None,
                business_id=business.id,
                call_type=call.get("call_type", "outbound"),
                cost=call.get("cost", 0.0),
                recording_url=call.get("recording_url"),
                transcription=call.get("transcription")
            )
            for call in calls
        ]
        
    except Exception as e:
        logger.error(f"Error getting call history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting call history: {str(e)}"
        )


@router.get("/{call_id}", response_model=VoiceCallResponse)
async def get_call_details(
    call_id: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get detailed information about a specific call.
    """
    twilio_service = TwilioService(db)
    
    try:
        call_details = await twilio_service.get_call_details(call_id)
        
        if not call_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        return VoiceCallResponse(
            id=call_details["call_sid"],
            status=VoiceCallStatus(call_details["status"]),
            from_number=call_details["from_number"],
            to_number=call_details["to_number"],
            duration=call_details.get("duration", 0),
            created_at=datetime.fromisoformat(call_details["created_at"]),
            business_id=business.id,
            call_type=call_details.get("call_type", "outbound"),
            cost=call_details.get("cost", 0.0),
            recording_url=call_details.get("recording_url"),
            transcription=call_details.get("transcription")
        )
        
    except Exception as e:
        logger.error(f"Error getting call details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting call details: {str(e)}"
        )


@router.post("/{call_id}/end")
async def end_call(
    call_id: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    End an active voice call.
    """
    twilio_service = TwilioService(db)
    
    try:
        result = await twilio_service.end_call(call_id)
        
        return {
            "success": True,
            "message": "Call ended successfully",
            "call_id": call_id,
            "duration": result.get("duration", 0)
        }
        
    except Exception as e:
        logger.error(f"Error ending call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ending call: {str(e)}"
        )


@router.post("/{call_id}/transfer")
async def transfer_call(
    call_id: str,
    transfer_to: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Transfer a call to a human agent or another number.
    """
    twilio_service = TwilioService(db)
    
    try:
        result = await twilio_service.transfer_call(
            call_id=call_id,
            transfer_to=transfer_to
        )
        
        return {
            "success": True,
            "message": "Call transferred successfully",
            "call_id": call_id,
            "transferred_to": transfer_to
        }
        
    except Exception as e:
        logger.error(f"Error transferring call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error transferring call: {str(e)}"
        )


@router.get("/analytics", response_model=VoiceCallAnalytics)
async def get_voice_call_analytics(
    time_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get voice call analytics and insights.
    """
    # Calculate date range
    end_date = datetime.utcnow()
    if time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    elif time_range == "90d":
        start_date = end_date - timedelta(days=90)
    else:  # 1y
        start_date = end_date - timedelta(days=365)
    
    twilio_service = TwilioService(db)
    
    try:
        analytics = await twilio_service.get_call_analytics(
            business_id=business.id,
            start_date=start_date,
            end_date=end_date
        )
        
        return VoiceCallAnalytics(
            time_range=time_range,
            total_calls=analytics.get("total_calls", 0),
            total_duration=analytics.get("total_duration", 0),
            average_duration=analytics.get("average_duration", 0),
            total_cost=analytics.get("total_cost", 0.0),
            calls_by_status=analytics.get("calls_by_status", {}),
            calls_by_type=analytics.get("calls_by_type", {}),
            peak_hours=analytics.get("peak_hours", []),
            call_quality_score=analytics.get("call_quality_score", 0.0),
            customer_satisfaction=analytics.get("customer_satisfaction", 0.0)
        )
        
    except Exception as e:
        logger.error(f"Error getting call analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting call analytics: {str(e)}"
        )


@router.get("/settings", response_model=VoiceCallSettings)
async def get_voice_call_settings(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get voice call settings for the business.
    """
    settings = business.phone_features.get("voice_settings", {})
    
    return VoiceCallSettings(
        voice_enabled=settings.get("voice_enabled", True),
        ai_voice_enabled=settings.get("ai_voice_enabled", True),
        human_transfer_enabled=settings.get("human_transfer_enabled", True),
        business_hours_only=settings.get("business_hours_only", False),
        business_hours_start=settings.get("business_hours_start", "09:00"),
        business_hours_end=settings.get("business_hours_end", "17:00"),
        timezone=settings.get("timezone", "UTC"),
        voice_personality=settings.get("voice_personality", "friendly"),
        language=settings.get("language", "en"),
        greeting_message=settings.get("greeting_message", "Welcome to {business_name}"),
        transfer_message=settings.get("transfer_message", "Transferring you to a human agent"),
        recording_enabled=settings.get("recording_enabled", True),
        transcription_enabled=settings.get("transcription_enabled", True)
    )


@router.put("/settings", response_model=VoiceCallSettings)
async def update_voice_call_settings(
    settings: VoiceCallSettings,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update voice call settings for the business.
    """
    if not business.phone_features:
        business.phone_features = {}
    
    business.phone_features["voice_settings"] = settings.dict()
    db.commit()
    
    return settings


@router.post("/test")
async def test_voice_call(
    phone_number: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Test voice call functionality.
    """
    voice_handler = VoiceHandler(db)
    twilio_service = TwilioService(db)
    
    try:
        # Initiate test call
        call_result = await twilio_service.initiate_test_call(
            to_number=phone_number,
            from_number=business.custom_phone_number or business.phone_config,
            business_id=business.id
        )
        
        return {
            "success": True,
            "message": "Test call initiated successfully",
            "call_id": call_result["call_sid"],
            "estimated_duration": "30 seconds"
        }
        
    except Exception as e:
        logger.error(f"Error initiating test call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error initiating test call: {str(e)}"
        )


@router.websocket("/ws/{call_id}")
async def voice_call_websocket(
    websocket: WebSocket,
    call_id: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time voice call updates.
    """
    await websocket.accept()
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to voice call system",
            "call_id": call_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and send call updates
        while True:
            data = await websocket.receive_text()
            
            # Process incoming data (e.g., voice commands)
            # This would integrate with the voice handler
            
            # Send response
            await websocket.send_json({
                "type": "response",
                "message": "Voice command processed",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except WebSocketDisconnect:
        logger.info(f"Voice call WebSocket disconnected for call {call_id}")


@router.get("/recordings/{call_id}")
async def get_call_recording(
    call_id: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get call recording URL and metadata.
    """
    twilio_service = TwilioService(db)
    
    try:
        recording = await twilio_service.get_call_recording(call_id)
        
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )
        
        return {
            "call_id": call_id,
            "recording_url": recording["url"],
            "duration": recording["duration"],
            "file_size": recording["file_size"],
            "format": recording["format"],
            "created_at": recording["created_at"]
        }
        
    except Exception as e:
        logger.error(f"Error getting call recording: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting call recording: {str(e)}"
        )


@router.get("/transcriptions/{call_id}")
async def get_call_transcription(
    call_id: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get call transcription and analysis.
    """
    twilio_service = TwilioService(db)
    
    try:
        transcription = await twilio_service.get_call_transcription(call_id)
        
        if not transcription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcription not found"
            )
        
        return {
            "call_id": call_id,
            "transcription": transcription["text"],
            "confidence": transcription["confidence"],
            "language": transcription["language"],
            "segments": transcription.get("segments", []),
            "sentiment": transcription.get("sentiment", "neutral"),
            "keywords": transcription.get("keywords", [])
        }
        
    except Exception as e:
        logger.error(f"Error getting call transcription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting call transcription: {str(e)}"
        )
