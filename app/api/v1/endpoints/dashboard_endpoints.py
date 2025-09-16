"""
Dashboard Chat Endpoints - Business management service
"""
from __future__ import annotations

import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business
from app.services.ai.dashboard_ai_handler import DashboardAIHandler

router = APIRouter(tags=["Dashboard AI"])


@router.post("/")
async def dashboard_chat(
    request: Dict[str, Any],
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Process a dashboard management chat message"""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "").strip()
    
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    handler = DashboardAIHandler(db)
    response = await handler.process_message(
        message=message,
        session_id=session_id,
        business_id=current_business.id,
        user_id=request.get("user_id"),
        additional_context=request.get("context", {})
    )
    
    return response


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for dashboard service"""
    return {"status": "healthy", "service": "dashboard"}
