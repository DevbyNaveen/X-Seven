"""
Global Chat Endpoints - Business discovery service
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from app.config.database import get_supabase_client
from app.services.ai.global_ai import GlobalAIHandler
from app.config.settings import settings

router = APIRouter(tags=["Global AI"])


@router.post("/")
async def global_chat(
    request: Dict[str, Any],
    supabase = Depends(get_supabase_client)  # ✅ Fixed dependency
) -> Dict[str, Any]:
    """Process a global business discovery chat message."""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "").strip()
    context = request.get("context", {})
    
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    handler = GlobalAIHandler(supabase, groq_api_key=settings.GROQ_API_KEY)
    response = await handler.chat(
        message=message,
        session_id=session_id
    )
    
    return response


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for global service"""
    return {"status": "healthy", "service": "global"}


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
