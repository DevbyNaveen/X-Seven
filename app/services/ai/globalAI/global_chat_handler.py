# app/services/ai/global_chat_handler.py
"""
Global Chat Handler - Entry Point for Global Chat Functionality
Based on CentralAIHandler but specialized for global business discovery
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.services.ai.centralAI.central_ai_handler import CentralAIHandler, ChatType
from app.services.ai.centralAI.rag_search import RAGSearch


class GlobalChatHandler:
    """
    Global Chat Handler - Specialized entry point for global business discovery.
    """
    
    def __init__(self, db: Session):
        self.central_ai = CentralAIHandler(db)
        self.db = db
        self.rag_search = RAGSearch(db)
    
    async def handle_global_chat(
        self,
        message: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle global chat requests for business discovery.
        """
        result = await self.central_ai.chat(
            message=message,
            session_id=session_id,
            chat_type=ChatType.GLOBAL,
            context=context or {}
        )
        
        # Handle routing responses
        if result.get("route_to"):
            return result  # Return routing instruction
            
        return result
    
    async def get_business_recommendations(
        self,
        user_preferences: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get personalized business recommendations.
        """
        recommendation_prompt = (
            f"Based on user preferences: {user_preferences}, "
            "please provide personalized business recommendations."
        )
        
        return await self.central_ai.chat(
            message=recommendation_prompt,
            session_id=session_id,
            chat_type=ChatType.GLOBAL,
            context={"recommendation_request": True}
        )
    
    async def search_businesses(
        self,
        query: str,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses using RAG-based search.
        """
        try:
            results = self.rag_search.search_businesses(query, filters or {})
            return results
        except Exception as e:
            # Log error and return empty list
            print(f"Search error: {e}")
            return []
    
    async def get_popular_businesses(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get popular businesses using RAG search.
        """
        try:
            # Use RAG to get popular businesses
            results = self.rag_search.search_businesses("", {"limit": limit})
            return results[:limit] if results else []
        except Exception as e:
            print(f"Popular businesses error: {e}")
            return []