"""
Endpoint factory for standardized request handling across all AI services
"""
from __future__ import annotations

import uuid
from typing import Dict, Any, Callable, Optional
from functools import wraps

from fastapi import Depends, HTTPException

from app.config.database import get_supabase_client


def create_ai_endpoint(handler_class, chat_context: str, auth_func: Optional[Callable] = None):
    """
    Factory function to create standardized AI endpoints
    
    Args:
        handler_class: The AI handler class to use
        chat_context: The chat context type
        auth_func: Optional authentication function
    """
    async def endpoint(request: Dict[str, Any], supabase = Depends(get_supabase_client)):
        # Authentication if provided
        if auth_func:
            business = await auth_func(request, supabase)
            business_id = business.id if business else None
        else:
            business_id = None
        
        # Extract common parameters
        session_id = request.get("session_id") or str(uuid.uuid4())
        message = request.get("message", "").strip()
        user_id = request.get("user_id")
        additional_context = request.get("context", {})
        
        # Validate message
        if not message and chat_context != "dedicated":
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Initialize handler
        handler = handler_class(supabase)
        
        # Prepare handler arguments
        handler_kwargs = {
            "message": message,
            "session_id": session_id,
            "user_id": user_id,
            "additional_context": additional_context
        }
        
        # Add business_id for dedicated and dashboard contexts
        if business_id and chat_context in ["dedicated", "dashboard"]:
            handler_kwargs["business_id"] = business_id
        
        # Process message
        return await handler.process_message(**handler_kwargs)
    
    return endpoint
