"""
Global Chat Endpoints - Business discovery service
"""
from __future__ import annotations

import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from app.config.database import get_supabase_client
from app.core.ai.types import ChatContext as ChatType

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
    
    central_ai = CentralAIHandler(supabase)  # ✅ Pass supabase instead of db
    response = await central_ai.chat(
        message=message,
        session_id=session_id,
        chat_type=ChatType.GLOBAL,
        context=context
    )
    
    return response


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for global service"""
    return {"status": "healthy", "service": "global"}
