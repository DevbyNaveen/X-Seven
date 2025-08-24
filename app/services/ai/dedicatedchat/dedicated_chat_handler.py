"""
Dedicated Chat Handler - Business Context Aware Chat
Handles dedicated chats with business context awareness from entry points
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.services.ai.centralAI.central_ai_handler import CentralAIHandler, ChatType


class DedicatedChatHandler:
    """
    Dedicated Chat Handler - Specialized entry point for business-specific chats.
    
    This handler extends the CentralAIHandler functionality specifically for 
    dedicated business chats where the business context is known from the entry point.
    
    Features:
    - Business context awareness from entry point (direct business chat, QR code, etc.)
    - Session management with business context
    - Entry point tracking for analytics
    """
    
    def __init__(self, db: Session):
        self.central_ai = CentralAIHandler(db)
        self.db = db
    
    async def handle_dedicated_chat(
        self,
        message: str,
        session_id: str,
        business_id: int,
        entry_point: str = "direct",  # direct, qr_code, business_link, etc.
        table_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle dedicated chat requests for a specific business.
        
        Args:
            message: User's message
            session_id: Session identifier
            business_id: Business identifier (known from entry point)
            entry_point: How the user accessed the chat (qr_code, direct, business_link, etc.)
            table_id: Optional table identifier for restaurant use cases
            context: Additional context information
            
        Returns:
            Dict containing the AI response and metadata
        """
        # Prepare context with business information
        chat_context = context or {}
        chat_context["business_id"] = business_id
        chat_context["entry_point"] = entry_point
        chat_context["table_id"] = table_id
        
        # Track entry point for analytics
        chat_context["entry_point_metadata"] = {
            "type": entry_point,
            "business_id": business_id,
            "table_id": table_id,
            "timestamp": "current_time"  # Would be actual timestamp in implementation
        }
        
        return await self.central_ai.chat(
            message=message,
            session_id=session_id,
            chat_type=ChatType.DEDICATED,
            context=chat_context
        )
    
    async def initialize_business_session(
        self,
        business_id: int,
        session_id: str,
        entry_point: str = "direct"
    ) -> Dict[str, Any]:
        """
        Initialize a new business chat session with welcome context.
        
        Args:
            business_id: Business identifier
            session_id: Session identifier
            entry_point: How the user accessed the chat
            
        Returns:
            Dict containing session initialization data
        """
        # Get business information
        from app.models import Business
        business = self.db.query(Business).filter(Business.id == business_id).first()
        
        if not business:
            return {
                "success": False,
                "error": "Business not found",
                "session_id": session_id
            }
        
        # Create welcome context
        welcome_context = {
            "business_id": business_id,
            "business_name": business.name,
            "business_category": business.category,
            "entry_point": entry_point,
            "session_initialized": True
        }
        
        return {
            "success": True,
            "session_id": session_id,
            "business_info": {
                "id": business.id,
                "name": business.name,
                "category": business.category,
                "description": business.description
            },
            "entry_point": entry_point,
            "context": welcome_context
        }
    
    async def get_business_context_summary(
        self,
        business_id: int,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get a summary of the business context for the chat.
        
        Args:
            business_id: Business identifier
            session_id: Session identifier
            
        Returns:
            Dict containing business context information
        """
        from app.models import Business, MenuItem
        
        # Get business information
        business = self.db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return {"error": "Business not found"}
        
        # Get sample menu items
        menu_items = self.db.query(MenuItem).filter(
            MenuItem.business_id == business_id,
            MenuItem.is_available == True
        ).limit(5).all()
        
        return {
            "business": {
                "id": business.id,
                "name": business.name,
                "category": business.category,
                "description": business.description,
                "is_active": business.is_active
            },
            "sample_menu": [
                {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.base_price or 0)
                } for item in menu_items
            ],
            "session_id": session_id
        }
    
    def track_entry_point_analytics(
        self,
        business_id: int,
        entry_point: str,
        session_id: str
    ) -> None:
        """
        Track entry point analytics for business chat access.
        
        Args:
            business_id: Business identifier
            entry_point: Entry point type (qr_code, direct, business_link, etc.)
            session_id: Session identifier
        """
        # In a real implementation, this would log to analytics
        # For now, we'll just print for demonstration
        print(f"Entry point analytics: {entry_point} for business {business_id} (session: {session_id})")
