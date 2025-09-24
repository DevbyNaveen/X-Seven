"""
Dedicated Chat Endpoints - Business-specific service
"""
from __future__ import annotations

import uuid
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from app.config.database import get_supabase_client
from app.services.ai.crewai_orchestrator import get_crewai_orchestrator

router = APIRouter(tags=["Dedicated AI"])


@router.post("/{business_identifier}")
async def dedicated_chat(
    business_identifier: str,
    request: Dict[str, Any],
    supabase = Depends(get_supabase_client)  # ✅ Fixed dependency
) -> Dict[str, Any]:
    """Dedicated chat for a specific business."""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "")
    context = request.get("context", {})

    if not message.strip():
        return {"error": "Message cannot be empty", "session_id": session_id}

    try:
        # ✅ FIXED: Proper Supabase query instead of SQLAlchemy
        if business_identifier.isdigit():
            # Search by ID
            business_response = supabase.table('businesses').select('*').eq('id', int(business_identifier)).execute()
        else:
            # Search by slug
            business_response = supabase.table('businesses').select('*').eq('slug', business_identifier).execute()
        
        if not business_response.data:
            raise HTTPException(status_code=404, detail="Business not found")
        
        business = business_response.data[0]
        business_id = business['id']
        business_category = business.get('category', 'general')
        
        # Add business context
        context["business_id"] = business_id
        context["selected_business"] = business_id
        context["business_data"] = business

        # Use CrewAI orchestrator with business category for specialized agent selection
        orchestrator = get_crewai_orchestrator()
        response = await orchestrator.process_request(
            message=message,
            user_id=request.get("user_id") or "anonymous",
            session_id=session_id,
            context=context,
            business_category=business_category  # This triggers the correct specialized agent
        )
        
        return {
            "message": response.get("response", ""),
            "session_id": session_id,
            "success": True,
            "chat_type": "dedicated",
            "business_id": business_id,
            "business_category": business_category,
            "agent_used": response.get("agent_used", "unknown"),
            "processing_method": response.get("processing_method", "crewai_dedicated"),
            "suggested_actions": [],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Dedicated chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for dedicated service"""
    return {"status": "healthy", "service": "dedicated"}
