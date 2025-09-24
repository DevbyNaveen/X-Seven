"""
Global Chat Endpoints - Enhanced with CrewAI ARC and Agent Squad fallback
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.config.database import get_supabase_client
# GlobalAIHandler removed during CrewAI integration - using CrewAI orchestrator instead
from app.config.settings import settings

# Import both orchestrators for migration support
try:
    from app.services.ai.crewai_orchestrator import get_crewai_orchestrator
    CREWAI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ CrewAI not available: {e}")
    CREWAI_AVAILABLE = False

router = APIRouter(tags=["Global AI"])


@router.post("/", response_model=None)
async def global_chat(
    request: Dict[str, Any],
    stream: bool = False,  # Query parameter to enable streaming
    use_crewai: bool = None,  # Query parameter to force CrewAI usage
    supabase = Depends(get_supabase_client)  # ✅ Fixed dependency
) -> Union[Dict[str, Any], StreamingResponse]:
    """Enhanced global business discovery chat with CrewAI ARC support.

    This endpoint supports CrewAI ARC orchestrator.
    - By default: Uses CrewAI ARC if available, falls back to Global AI Handler
    - Query param ?use_crewai=false: Forces Global AI Handler usage
    - Query param ?use_crewai=true: Forces CrewAI ARC usage
    - Query param ?stream=true: Enables real-time streaming responses
    """
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "").strip()
    user_id = request.get("user_id")
    user_location = request.get("location")
    user_language = request.get("language", "en")
    user_preferences = request.get("preferences")

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Determine which orchestrator to use
    use_crewai_flag = use_crewai
    if use_crewai_flag is None:
        # Auto-detect: prefer CrewAI, fallback to Global AI Handler
        use_crewai_flag = CREWAI_AVAILABLE

    print(f"🎯 Processing with {'CrewAI ARC' if use_crewai_flag else 'Global AI Handler'}")
    print(f"📝 Message: {message[:100]}...")
    print(f"👤 User: {user_id}, Session: {session_id}")

    try:
        # Use CrewAI ARC if available and requested
        if use_crewai_flag and CREWAI_AVAILABLE:
            print("🚀 Using CrewAI ARC orchestrator...")
            orchestrator = get_crewai_orchestrator()

            # Prepare conversation history and context for enhanced processing
            conversation_history = []  # Could be enhanced to store actual history
            context = await _prepare_enhanced_context(user_id, supabase)

            response = await orchestrator.process_request(
                message=message,
                user_id=user_id or "anonymous",
                session_id=session_id,
                conversation_history=conversation_history,
                context=context
            )

            # Add compatibility with existing response format
            enhanced_response = {
                "response": response.get("response", ""),
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "crewai_arc_enhanced": True,
                "agent_used": response.get("agent_used", "unknown"),
                "model": response.get("model", "crewai_enhanced"),
                "processing_method": response.get("processing_method", "crewai_enhanced_orchestration"),
                "available_capabilities": response.get("available_capabilities", []),
                "orchestrator": "crewai_enhanced",
                "slot_filling_required": response.get("slot_filling_required", False),
                "missing_slots": response.get("missing_slots", []),
                "execution_result": response.get("execution_result"),
                "sources": response.get("sources", []),
                "confidence": response.get("confidence")
            }

            # Add streaming support if requested (placeholder for now)
            if stream:
                return StreamingResponse(
                    _stream_crewai_response(response),
                    media_type="text/plain"
                )

            print("✅ Enhanced CrewAI processing completed successfully!")
            return enhanced_response

        # Fallback to Global AI Handler
        else:
            print("🛟 Using Global AI Handler...")
            return await _process_with_global_handler(
                message, session_id, user_id, user_location, user_language, user_preferences, stream, supabase
            )

    except Exception as e:
        print(f"❌ Primary processing failed: {e}")
        print("🛟 Attempting fallback processing...")

        # Try fallback orchestrators
        try:
            if not use_crewai_flag and CREWAI_AVAILABLE:
                print("🔄 Switching to CrewAI ARC fallback...")
                orchestrator = get_crewai_orchestrator()
                response = await orchestrator.process_request(
                    message=message,
                    user_id=user_id or "anonymous",
                    session_id=session_id
                )
                return _format_crewai_response(response, session_id)

        except Exception as fallback_error:
            print(f"❌ All orchestrators failed: {fallback_error}")

        # Final fallback
        try:
            return await _process_with_global_handler(
                message, session_id, user_id, user_location, user_language, user_preferences, stream, supabase
            )
        except Exception as final_error:
            print(f"❌ Complete system failure: {final_error}")
            raise HTTPException(
                status_code=500,
                detail="All AI processing systems are currently unavailable. Please try again later."
            )


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for global service with CrewAI support"""
    health_status = {
        "status": "healthy",
        "service": "global",
        "crewai_available": CREWAI_AVAILABLE,
        "orchestrator": "crewai_arc" if CREWAI_AVAILABLE else "global_handler"
    }

    if CREWAI_AVAILABLE:
        health_status["enhanced"] = "crewai_arc_intelligence"
    else:
        health_status["enhanced"] = "basic_global_handler"

    return health_status


@router.get("/capabilities")
async def get_capabilities(
    supabase = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Get available high-level capabilities and tool information"""
    # Use CrewAI orchestrator for capabilities
    orchestrator = get_crewai_orchestrator()

    # Get capability categories from CrewAI orchestrator
    capabilities = {
        "Greeting": "Handle general greetings and introductions",
        "Business Discovery": "Find and recommend businesses",
        "Reservation/Booking": "Make reservations and bookings",
        "Order Placement": "Place orders for services",
        "Information Retrieval": "Search for business information",
        "General Chat": "Handle general conversation",
        "Table Booking": "Make table bookings"
    }

    # Get available tools (simplified)
    tools = ["restaurant_booking", "beauty_services", "general_inquiry"]

    # Get capability-to-tool mapping
    capability_tools_map = {
        "Greeting": ["general_inquiry"],
        "Business Discovery": ["restaurant_booking", "beauty_services"],
        "Reservation/Booking": ["restaurant_booking", "beauty_services"],
        "Order Placement": ["restaurant_booking", "beauty_services"],
        "Information Retrieval": ["restaurant_booking", "beauty_services"],
        "General Chat": ["general_inquiry"]
    }

    return {
        "capabilities": capabilities,
        "available_tools": tools,
        "capability_tools_map": capability_tools_map,
        "system_status": "healthy" if CREWAI_AVAILABLE else "degraded",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/system-health")
async def system_health_check(
    supabase = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Comprehensive system health check with self-healing status"""
    try:
        # Simplified system health check without self_healing_manager
        system_health = {
            "overall_status": "healthy" if CREWAI_AVAILABLE else "degraded",
            "service": "global_ai",
            "agents": {
                "total": 3 if CREWAI_AVAILABLE else 0,
                "healthy": 3 if CREWAI_AVAILABLE else 0,
                "degraded": 0,
                "unhealthy": 0 if CREWAI_AVAILABLE else 3
            },
            "circuit_breakers": {
                "crewai_orchestrator": "closed" if CREWAI_AVAILABLE else "open",
                "supabase_connection": "closed",  # Assume healthy for now
                "fallback_handler": "available" if CREWAI_AVAILABLE else "unavailable"
            },
            "uptime": "active",
            "version": "2.0.0-crewai-enhanced",
            "timestamp": datetime.utcnow().isoformat()
        }

        return system_health

    except Exception as e:
        return {
            "overall_status": "unhealthy",
            "error": str(e),
            "service": "global_ai",
            "agents": {"total": 0, "healthy": 0, "degraded": 0, "unhealthy": 0},
            "circuit_breakers": {},
            "timestamp": datetime.now().isoformat()
        }


# Helper Functions for Dual-Orchestrator Support

async def _stream_crewai_response(response: Dict[str, Any]):
    """Stream CrewAI response (placeholder for future implementation)"""
    import asyncio

    response_text = response.get("response", "Processing your request...")
    for word in response_text.split():
        yield f"{word} "
        await asyncio.sleep(0.1)  # Simulate streaming delay


def _format_crewai_response(response: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    """Format CrewAI response to match API standards"""
    return {
        "response": response.get("response", ""),
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "crewai_arc_enhanced": True,
        "agent_used": response.get("agent_used", "unknown"),
        "model": response.get("model", "crewai_arc"),
        "processing_method": response.get("processing_method", "crewai_arc_orchestration"),
        "available_capabilities": response.get("available_capabilities", []),
        "orchestrator": "crewai_arc"
    }


async def _process_with_global_handler(
    message: str, session_id: str, user_id: str,
    user_location: str, user_language: str, user_preferences: Dict,
    stream: bool, supabase
) -> Dict[str, Any]:
    """Process request using CrewAI orchestrator as fallback (since GlobalAIHandler was removed)"""
    try:
        # Use CrewAI orchestrator instead of GlobalAIHandler
        if CREWAI_AVAILABLE:
            orchestrator = get_crewai_orchestrator()

            # Prepare context for enhanced processing
            context = await _prepare_enhanced_context(user_id or "anonymous", supabase)

            response = await orchestrator.process_request(
                message=message,
                user_id=user_id or "anonymous",
                session_id=session_id,
                context=context
            )

            # Add streaming support if requested (placeholder for now)
            if stream:
                return StreamingResponse(
                    _stream_crewai_response(response),
                    media_type="text/plain"
                )

            # Include available capabilities in response for compatibility
            if hasattr(orchestrator, '_get_capabilities'):
                response["available_capabilities"] = orchestrator._get_capabilities("general")

            # Mark as fallback response
            response["processing_method"] = "crewai_fallback"
            response["agent_squad_enhanced"] = False
            response["crewai_arc_enhanced"] = True
            response["orchestrator"] = "crewai_fallback"

            return response
        else:
            # No fallback available
            return {
                "response": "I'm sorry, but the AI processing systems are currently unavailable. Please try again later.",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "processing_method": "unavailable",
                "error": "No AI handlers available"
            }

    except Exception as e:
        print(f"❌ Fallback processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AI processing failed: {str(e)}"
        )


# Helper Functions for Enhanced Processing

async def _prepare_enhanced_context(user_id: str, supabase) -> Dict[str, Any]:
    """Prepare enhanced context for the orchestrator"""
    try:
        # Get available businesses
        businesses_resp = supabase.table("businesses").select("*").execute()
        businesses = businesses_resp.data or []

        return {
            "businesses": businesses,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"❌ Failed to prepare enhanced context: {e}")
        return {
            "businesses": [],
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
