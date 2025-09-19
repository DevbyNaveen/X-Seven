"""
Global Chat Endpoints - Business discovery service
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.config.database import get_supabase_client
from app.services.ai.global_ai import GlobalAIHandler
from app.config.settings import settings

router = APIRouter(tags=["Global AI"])


@router.post("/", response_model=None)
async def global_chat(
    request: Dict[str, Any],
    stream: bool = False,  # Query parameter to enable streaming
    supabase = Depends(get_supabase_client)  # ✅ Fixed dependency
) -> Union[Dict[str, Any], StreamingResponse]:
    """Process a global business discovery chat message with capability-based routing.

    Use ?stream=true for real-time streaming responses like ChatGPT.
    """
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "").strip()
    user_id = request.get("user_id")
    user_location = request.get("location")
    user_language = request.get("language", "en")
    user_preferences = request.get("preferences")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Initialize cache on first request (startup optimization)
    await GlobalAIHandler.initialize_cache(supabase)
    
    handler = GlobalAIHandler(supabase, groq_api_key=settings.GROQ_API_KEY)

    # Return streaming response if requested
    if stream:
        return StreamingResponse(
            handler.chat_stream(
                message=message,
                session_id=session_id,
                user_id=user_id,
                user_location=user_location,
                user_language=user_language,
                user_preferences=user_preferences
            ),
            media_type="text/plain"
        )

    # Return regular JSON response with capability information
    response = await handler.chat(
        message=message,
        session_id=session_id,
        user_id=user_id,
        user_location=user_location,
        user_language=user_language,
        user_preferences=user_preferences
    )

    # Include available capabilities in response
    if hasattr(handler, 'get_capability_categories'):
        response["available_capabilities"] = list(handler.get_capability_categories().keys())

    return response


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for global service"""
    return {"status": "healthy", "service": "global"}


@router.get("/capabilities")
async def get_capabilities(
    supabase = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Get available high-level capabilities and tool information"""
    handler = GlobalAIHandler(supabase, groq_api_key=settings.GROQ_API_KEY)
    
    # Get capability categories
    capabilities = handler.get_capability_categories()
    
    # Get available tools
    tools = list(handler.available_tools.keys())
    
    # Get capability-to-tool mapping
    capability_tools_map = {
        "Greeting": ["None - Direct response"],
        "Casual conversation": ["retrieve_memory_context"],
        "Business discovery": ["search_business_information"],
        "Information retrieval": ["search_business_sections", "search_business_information"],
        "Reservation/booking": ["understand_user_intent", "collect_required_info", "execute_business_action"],
        "Order placement": ["understand_user_intent", "collect_required_info", "execute_business_action"],
        "Cancellation/modification": ["understand_user_intent", "execute_business_action"],
        "Answer FAQs": ["search_business_information", "retrieve_memory_context"]
    }
    
    return {
        "capabilities": capabilities,
        "available_tools": tools,
        "capability_tools_map": capability_tools_map,
        "system_status": "healthy" if len(tools) >= 5 else "degraded",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/system-health")
async def system_health_check(
    supabase = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Comprehensive system health check with self-healing status"""
    try:
        from app.services.ai.global_ai import self_healing_manager
        
        # Get system health from self-healing manager
        system_health = self_healing_manager.get_system_health()
        
        # Add additional system information
        system_health["service"] = "global_ai"
        system_health["uptime"] = "active"  # Could be enhanced with actual uptime tracking
        system_health["version"] = "2.0.0-self-healing"
        
        # Determine overall status
        if system_health["overall_status"] == "healthy":
            status_code = 200
        elif system_health["overall_status"] == "degraded":
            status_code = 200  # Still operational but degraded
        else:
            status_code = 503  # Service unavailable
            
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
