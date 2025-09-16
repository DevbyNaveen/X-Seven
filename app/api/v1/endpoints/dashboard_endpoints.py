"""
Dashboard Chat Endpoints - Business management service
"""
from __future__ import annotations

import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from app.config.database import get_supabase_client
from app.core.ai.types import ChatContext as ChatType

router = APIRouter(tags=["Dashboard AI"])


@router.post("/")
async def dashboard_chat(
    request: Dict[str, Any],
    supabase = Depends(get_supabase_client)  # ✅ Fixed dependency
) -> Dict[str, Any]:
    """Process a dashboard management chat message."""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "").strip()
    context = request.get("context", {})
    
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Get business_id from context or request
    business_id = context.get("business_id") or request.get("business_id")
    if not business_id:
        raise HTTPException(status_code=400, detail="Business ID required")
    
    central_ai = CentralAIHandler(supabase)  # ✅ Pass supabase instead of db
    context["business_id"] = business_id
    response = await central_ai.chat(
        message=message,
        session_id=session_id,
        chat_type=ChatType.DASHBOARD,
        context=context
    )
    
    return response


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for dashboard service"""
    return {"status": "healthy", "service": "dashboard"}
