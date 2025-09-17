"""
Dedicated AI Handler - Business-specific chat service
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.core.ai.base_handler import BaseAIHandler
from app.core.ai.types import RichContext, ChatContext
from app.core.ai.context_builders import build_dedicated_context, load_conversation_history


class DedicatedAIHandler(BaseAIHandler):
    """Handler for dedicated business chat"""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.logger = logging.getLogger(__name__)
    
    async def process_message(
        self,
        message: str,
        session_id: str,
        business_id: int,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a dedicated chat message"""
        try:
            # Build rich context
            context = RichContext(
                chat_context=ChatContext.DEDICATED,
                session_id=session_id,
                user_message=message,
                business_id=business_id,
                user_id=user_id
            )
            
            # Load dedicated context
            context = await build_dedicated_context(context, business_id)
            
            # Load conversation history
            context.conversation_history = await load_conversation_history(
                context, session_id, ChatContext.DEDICATED, business_id
            )
            
            # Build prompt
            prompt = self.build_prompt(context)
            
            # Get AI response
            response = await self.get_ai_response(prompt)
            
            # Save conversation
            await self.save_conversation(context, response)
            
            return {
                "message": response,
                "success": True,
                "chat_context": ChatContext.DEDICATED.value,
                "business_id": business_id,
                "session_id": session_id
            }
            
        except Exception as e:
            self.logger.exception("Dedicated AI processing failed: %s", e)
            return {
                "message": "I'm having trouble processing your request. Please try again.",
                "success": False,
                "error": str(e)
            }
    
    def build_prompt(self, context: RichContext) -> str:
        """Build prompt for dedicated business chat"""
        lines = [
            f"You are the AI assistant for {context.current_business['name']}.",
            f"Current time: {context.current_time.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]
        
        if context.current_business:
            lines.append(f"## Business: {context.current_business['name']}")
            lines.append(f"**Category**: {context.current_business.get('category', 'General')}")
            lines.append(f"**Description**: {context.current_business.get('description', 'Business services')}")
            lines.append("")
        
        if context.business_menu:
            lines.append("## Available Services")
            for item in context.business_menu[:12]:
                lines.append(f"• **{item['name']}** - ${item['price']} ({item.get('description', 'Service')})")
            lines.append("")
        
        if context.conversation_history:
            lines.append("## Recent Conversation")
            for entry in context.conversation_history[-6:]:
                lines.append(f"{entry['role']}: {entry['content']}")
            lines.append("")
        
        lines.extend([
            f"## Customer Message\n{context.user_message}",
            "",
            "## Your Response",
            "You represent this business. Be helpful, professional, and assist with bookings, orders, and inquiries."
        ])
        
        return "\n".join(lines)
