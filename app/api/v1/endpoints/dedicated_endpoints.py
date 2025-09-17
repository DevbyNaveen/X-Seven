"""
Dedicated Chat Endpoints - Business-specific service
"""
from __future__ import annotations

import uuid
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from app.config.database import get_supabase_client
from app.core.ai.types import ChatContext as ChatType

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
        
        # Add business context
        context["business_id"] = business_id
        context["selected_business"] = business_id

        # Use Central AI with dedicated chat type
        central_ai = CentralAIHandler(supabase)  # ✅ Pass supabase instead of db
        response = await central_ai.chat(
            message=message,
            session_id=session_id,
            chat_type=ChatType.DEDICATED,
            context=context
        )
        
        return {
            "message": response.get("message", ""),
            "session_id": session_id,
            "success": response.get("success", True),
            "chat_type": "dedicated",
            "business_id": business_id,
            "suggested_actions": [],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Dedicated chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")
    
    # Handle initialization request
    if not message:
        return {
            "success": True,
            "session_id": session_id,
            "business_id": business.id,
            "business_name": business.name,
            "welcome_message": f"Welcome to {business.name}! How can I help you today?",
            "entry_point": request.get("entry_point", "direct")
        }
    
    response = await handler.process_message(
        message=message,
        session_id=session_id,
        business_id=business.id,
        user_id=request.get("user_id"),
        additional_context=request.get("context", {})
    )
    
    return response


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for dedicated service"""
    return {"status": "healthy", "service": "dedicated"}
