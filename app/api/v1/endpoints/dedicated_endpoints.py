"""
Dedicated Chat Endpoints - Business-specific service
"""
from __future__ import annotations

import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.services.ai.dedicated_ai_handler import DedicatedAIHandler
from app.models import Business

router = APIRouter(tags=["Dedicated AI"])


@router.post("/{business_identifier}")
async def dedicated_chat(
    business_identifier: str,
    request: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Process a dedicated business chat message"""
    session_id = request.get("session_id") or str(uuid.uuid4())
    message = request.get("message", "").strip()
    
    # Resolve business by ID or slug
    business = None
    if business_identifier.isdigit():
        business = db.query(Business).filter(Business.id == int(business_identifier)).first()
    else:
        business = db.query(Business).filter(Business.slug == business_identifier).first()
    
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
    handler = DedicatedAIHandler(db)
    
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
