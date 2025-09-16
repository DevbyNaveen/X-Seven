"""
Global Chat Endpoints - Business discovery service
"""
from __future__ import annotations

import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.services.ai.global_ai_handler import GlobalAIHandler

router = APIRouter(tags=["Global AI"])


@router.post("/")
async def global_chat(
    request: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Process a global business discovery chat message"""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "").strip()
    
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    handler = GlobalAIHandler(db)
    response = await handler.process_message(
        message=message,
        session_id=session_id,
        user_id=request.get("user_id"),
        additional_context=request.get("context", {})
    )
    
    return response


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for global service"""
    return {"status": "healthy", "service": "global"}
