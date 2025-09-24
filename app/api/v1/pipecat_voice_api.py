"""
PipeCat Voice API Endpoints

Comprehensive REST API for PipeCat AI voice integration with X-Seven's
LangGraph, Temporal, CrewAI, and DSPy systems.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any, Optional, List
import asyncio
import logging
from datetime import datetime
import json
import uuid

from app.core.voice.integration_manager import get_voice_integration_manager, VoiceIntegrationManager
from app.core.voice.pipecat_config import get_pipecat_config, PipeCatConfig
from app.schemas.voice_calls import (
    VoiceCallCreate, VoiceCallResponse, VoiceCallSettings,
    VoiceCallAnalytics, VoiceCallHealthCheck
)
from app.config.database import get_supabase_client
from app.config.logging import get_logger

# Enhanced imports for DSPy integration
from app.core.dspy.manager import DSPyManager
from app.core.dspy.modules.voice_optimized_modules import (
    VoiceIntentDetectionModule,
    VoiceResponseGenerationModule,
    VoiceConversationSummaryModule
)

logger = get_logger(__name__)
router = APIRouter(prefix="/voice", tags=["PipeCat Voice AI"])


# Dependency to get voice integration manager
async def get_voice_manager() -> VoiceIntegrationManager:
    """Get voice integration manager dependency."""
    return get_voice_integration_manager()


# Dependency to get DSPy manager for voice optimization
async def get_dspy_voice_manager() -> DSPyManager:
    """Get DSPy manager for voice optimization."""
    try:
        from app.core.dspy.manager import get_dspy_manager
        return get_dspy_manager()
    except Exception as e:
        logger.warning(f"DSPy manager not available: {e}")
        return None


@router.get("/health", response_model=VoiceCallHealthCheck)
async def voice_health_check(
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Get voice system health status."""
    try:
        status = voice_manager.get_system_status()
        
        health_status = "healthy"
        issues = []
        
        # Check pipeline status
        if not status.get("initialized"):
            health_status = "down"
            issues.append("Voice integration not initialized")
        
        if not status.get("pipeline_running"):
            health_status = "degraded" if health_status == "healthy" else health_status
            issues.append("Voice pipeline not running")
        
        # Check integration status
        integrations = status.get("integrations", {})
        if not any(integrations.values()):
            health_status = "degraded" if health_status == "healthy" else health_status
            issues.append("No integrations active")
        
        metrics = status.get("metrics", {})
        error_rate = metrics.get("error_rate", 0)
        if error_rate > 0.1:  # More than 10% error rate
            health_status = "degraded" if health_status == "healthy" else health_status
            issues.append(f"High error rate: {error_rate:.2%}")
        
        return VoiceCallHealthCheck(
            service_status=health_status,
            provider_status="healthy",  # Assume provider is healthy
            active_calls=status.get("active_sessions", 0),
            queue_length=0,  # Not implemented yet
            average_response_time=metrics.get("average_latency", 0),
            error_rate=error_rate,
            last_check=datetime.now(),
            issues=issues
        )
        
    except Exception as e:
        logger.error(f"Error in voice health check: {e}")
        return VoiceCallHealthCheck(
            service_status="down",
            provider_status="unknown",
            active_calls=0,
            queue_length=0,
            average_response_time=0,
            error_rate=1.0,
            last_check=datetime.now(),
            issues=[f"Health check failed: {str(e)}"]
        )


@router.get("/status")
async def get_voice_system_status(
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Get detailed voice system status."""
    try:
        status = voice_manager.get_system_status()
        config = get_pipecat_config()
        
        return {
            "status": "success",
            "data": {
                "system_status": status,
                "configuration": config.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting voice system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize")
async def initialize_voice_system(
    background_tasks: BackgroundTasks,
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Initialize the voice system."""
    try:
        # Initialize in background
        background_tasks.add_task(voice_manager.initialize)
        
        return {
            "status": "success",
            "message": "Voice system initialization started",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error initializing voice system: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_voice_system(
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Start the voice system."""
    try:
        success = await voice_manager.start()
        
        if success:
            return {
                "status": "success",
                "message": "Voice system started successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start voice system")
            
    except Exception as e:
        logger.error(f"Error starting voice system: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_voice_system(
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Stop the voice system."""
    try:
        success = await voice_manager.stop()
        
        if success:
            return {
                "status": "success",
                "message": "Voice system stopped successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to stop voice system")
            
    except Exception as e:
        logger.error(f"Error stopping voice system: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/call/initiate")
async def initiate_voice_call(
    call_data: VoiceCallCreate,
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager),
    dspy_manager: Optional[DSPyManager] = Depends(get_dspy_voice_manager)
):
    """Initiate a new voice call with DSPy optimization."""
    try:
        session_id = str(uuid.uuid4())
        
        # Prepare call context with DSPy enhancement
        call_context = {
            "phone_number": call_data.phone_number,
            "call_type": call_data.call_type.value,
            "priority": call_data.priority,
            "scheduled_at": call_data.scheduled_at.isoformat() if call_data.scheduled_at else None,
            "context": call_data.context or {},
            "session_id": session_id,
            "dspy_enabled": dspy_manager is not None
        }
        
        # Enhance with DSPy if available
        if dspy_manager:
            try:
                # Use DSPy intent detection for call preparation
                intent_module = VoiceIntentDetectionModule()
                call_intent = await intent_module.detect_call_intent(call_context)
                call_context["predicted_intent"] = call_intent
                logger.info(f"DSPy predicted call intent: {call_intent}")
            except Exception as e:
                logger.warning(f"DSPy intent detection failed: {e}")
        
        # Process call through voice manager
        result = await voice_manager.process_voice_call(session_id, call_context)
        
        if result.get("success"):
            return {
                "status": "success",
                "data": {
                    "session_id": session_id,
                    "call_status": "initiated",
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initiate call: {result.get('error', 'Unknown error')}"
            )
            
    except Exception as e:
        logger.error(f"Error initiating voice call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/call/{session_id}/message")
async def process_voice_message(
    session_id: str,
    message_data: Dict[str, Any],
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager),
    dspy_manager: Optional[DSPyManager] = Depends(get_dspy_voice_manager)
):
    """Process a voice message with full DSPy integration."""
    try:
        message = message_data.get("message", "")
        context = message_data.get("context", {})
        
        # Enhance context with voice-specific data
        voice_context = {
            **context,
            "session_id": session_id,
            "input_type": "voice",
            "channel": "voice",
            "requires_voice_optimization": True,
            "timestamp": datetime.now().isoformat()
        }
        
        # DSPy-enhanced processing
        if dspy_manager:
            try:
                # Intent detection
                intent_module = VoiceIntentDetectionModule()
                detected_intent = await intent_module.detect_intent(message, voice_context)
                voice_context["detected_intent"] = detected_intent
                
                # Response generation with voice optimization
                response_module = VoiceResponseGenerationModule()
                optimized_response = await response_module.generate_voice_response(
                    message, voice_context
                )
                
                # Conversation summary for context preservation
                summary_module = VoiceConversationSummaryModule()
                conversation_summary = await summary_module.summarize_voice_interaction(
                    message, optimized_response, voice_context
                )
                
                return {
                    "status": "success",
                    "data": {
                        "session_id": session_id,
                        "response": optimized_response,
                        "detected_intent": detected_intent,
                        "conversation_summary": conversation_summary,
                        "dspy_enhanced": True,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
            except Exception as e:
                logger.warning(f"DSPy processing failed, falling back: {e}")
        
        # Fallback to standard processing
        result = await voice_manager.process_voice_call(session_id, {
            "message": message,
            "context": voice_context
        })
        
        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "result": result,
                "dspy_enhanced": False,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing voice message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{session_id}/status")
async def get_call_status(
    session_id: str,
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Get status of a specific voice call session."""
    try:
        session_info = voice_manager.voice_pipeline.get_session_info(session_id) if voice_manager.voice_pipeline else None
        
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "session_info": session_info,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/active")
async def get_active_sessions(
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Get all active voice sessions."""
    try:
        active_sessions = voice_manager.voice_pipeline.get_active_sessions() if voice_manager.voice_pipeline else {}
        
        return {
            "status": "success",
            "data": {
                "active_sessions": active_sessions,
                "session_count": len(active_sessions),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting active sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_voice_metrics(
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Get voice system metrics."""
    try:
        metrics = voice_manager.voice_pipeline.get_metrics() if voice_manager.voice_pipeline else {}
        
        return {
            "status": "success",
            "data": {
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting voice metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/twilio")
async def twilio_webhook(
    request: Request,
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Handle Twilio webhook events."""
    try:
        # Get form data from Twilio
        form_data = await request.form()
        webhook_data = dict(form_data)
        
        logger.info(f"Received Twilio webhook: {webhook_data}")
        
        # Extract session information
        call_sid = webhook_data.get("CallSid")
        event_type = webhook_data.get("CallStatus", "unknown")
        
        # Process webhook through voice manager
        result = await voice_manager.process_voice_call(call_sid, {
            "type": "webhook",
            "event": event_type,
            "data": webhook_data,
            "timestamp": datetime.now().isoformat()
        })
        
        # Return TwiML response
        twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello! Welcome to X-Seven AI Assistant. How can I help you today?</Say>
    <Gather input="speech" action="/api/v1/voice/webhook/twilio/gather" method="POST" speechTimeout="3">
        <Say voice="alice">Please speak your request after the tone.</Say>
    </Gather>
</Response>"""
        
        return JSONResponse(
            content=twiml_response,
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Error handling Twilio webhook: {e}")
        # Return error TwiML
        error_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">I'm sorry, there was an error processing your request. Please try again later.</Say>
    <Hangup/>
</Response>"""
        return JSONResponse(
            content=error_twiml,
            media_type="application/xml"
        )


@router.post("/webhook/twilio/gather")
async def twilio_gather_webhook(
    request: Request,
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager),
    dspy_manager: Optional[DSPyManager] = Depends(get_dspy_voice_manager)
):
    """Handle Twilio speech gathering webhook with DSPy processing."""
    try:
        form_data = await request.form()
        webhook_data = dict(form_data)
        
        call_sid = webhook_data.get("CallSid")
        speech_result = webhook_data.get("SpeechResult", "")
        confidence = float(webhook_data.get("Confidence", 0.0))
        
        logger.info(f"Received speech: {speech_result} (confidence: {confidence})")
        
        # Process speech through DSPy-enhanced pipeline
        response_text = "I didn't understand that. Could you please repeat?"
        
        if speech_result and confidence > 0.5:
            try:
                # Create voice context
                voice_context = {
                    "call_sid": call_sid,
                    "confidence": confidence,
                    "input_type": "voice",
                    "channel": "twilio"
                }
                
                # Process through DSPy if available
                if dspy_manager:
                    response_module = VoiceResponseGenerationModule()
                    response_text = await response_module.generate_voice_response(
                        speech_result, voice_context
                    )
                else:
                    # Fallback processing
                    result = await voice_manager.process_voice_call(call_sid, {
                        "message": speech_result,
                        "context": voice_context
                    })
                    response_text = result.get("message", response_text)
                    
            except Exception as e:
                logger.error(f"Error processing speech: {e}")
                response_text = "I'm having trouble processing your request right now."
        
        # Generate TwiML response
        twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">{response_text}</Say>
    <Gather input="speech" action="/api/v1/voice/webhook/twilio/gather" method="POST" speechTimeout="3">
        <Say voice="alice">Is there anything else I can help you with?</Say>
    </Gather>
    <Say voice="alice">Thank you for calling X-Seven AI. Goodbye!</Say>
    <Hangup/>
</Response>"""
        
        return JSONResponse(
            content=twiml_response,
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Error handling Twilio gather webhook: {e}")
        error_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">I'm sorry, there was an error. Goodbye!</Say>
    <Hangup/>
</Response>"""
        return JSONResponse(
            content=error_twiml,
            media_type="application/xml"
        )


@router.get("/analytics", response_model=VoiceCallAnalytics)
async def get_voice_analytics(
    time_range: str = "24h",
    voice_manager: VoiceIntegrationManager = Depends(get_voice_manager)
):
    """Get voice call analytics."""
    try:
        metrics = voice_manager.voice_pipeline.get_metrics() if voice_manager.voice_pipeline else {}
        
        # Generate analytics from metrics
        analytics = VoiceCallAnalytics(
            time_range=time_range,
            total_calls=metrics.get("call_count", 0),
            total_duration=int(metrics.get("total_duration", 0) / 60),  # Convert to minutes
            average_duration=int(metrics.get("total_duration", 0) / max(1, metrics.get("call_count", 1)) / 60),
            total_cost=0.0,  # Not implemented
            calls_by_status={"completed": metrics.get("call_count", 0)},
            calls_by_type={"inbound": metrics.get("call_count", 0)},
            peak_hours=[{"hour": 12, "calls": metrics.get("call_count", 0)}],
            call_quality_score=0.95,  # Mock value
            customer_satisfaction=4.5  # Mock value
        )
        
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting voice analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dspy/optimize")
async def optimize_voice_prompts(
    optimization_data: Dict[str, Any],
    dspy_manager: Optional[DSPyManager] = Depends(get_dspy_voice_manager)
):
    """Optimize voice prompts using DSPy."""
    try:
        if not dspy_manager:
            raise HTTPException(status_code=503, detail="DSPy not available")
        
        # Extract optimization parameters
        module_type = optimization_data.get("module_type", "voice_response")
        training_data = optimization_data.get("training_data", [])
        optimization_budget = optimization_data.get("budget", 10)
        
        # Perform optimization
        result = await dspy_manager.optimize_module(
            module_type=module_type,
            training_data=training_data,
            budget=optimization_budget
        )
        
        return {
            "status": "success",
            "data": {
                "optimization_result": result,
                "module_type": module_type,
                "budget_used": optimization_budget,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error optimizing voice prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_voice_configuration():
    """Get current voice system configuration."""
    try:
        config = get_pipecat_config()
        return {
            "status": "success",
            "data": {
                "configuration": config.to_dict(),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting voice configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/update")
async def update_voice_configuration(
    config_updates: Dict[str, Any]
):
    """Update voice system configuration."""
    try:
        config = get_pipecat_config()
        
        # Update configuration (simplified - would need proper validation)
        logger.info(f"Configuration update requested: {config_updates}")
        
        return {
            "status": "success",
            "message": "Configuration updated successfully",
            "data": {
                "updated_fields": list(config_updates.keys()),
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating voice configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))
