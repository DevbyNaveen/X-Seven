"""
Global AI Handler - Business discovery service
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from app.core.ai.base_handler import BaseAIHandler
from app.core.ai.types import RichContext, ChatContext
from app.core.ai.context_builders import build_global_context, load_conversation_history


class GlobalAIHandler(BaseAIHandler):
    """Handler for global business discovery chat"""
    
    def __init__(self, supabase):
        super().__init__(supabase)
        self.logger = logging.getLogger(__name__)
        self.supabase = supabase
    
    async def process_message(
        self,
        message: str,
        session_id: str,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a global chat message"""
        try:
            # Build rich context
            context = RichContext(
                chat_context=ChatContext.GLOBAL,
                session_id=session_id,
                user_message=message,
                user_id=user_id,
                db=self.supabase  # Pass supabase client to context
            )
            
            # Load global context
            context = await build_global_context(context)
            
            # Load conversation history
            context.conversation_history = await load_conversation_history(
                context, session_id, ChatContext.GLOBAL
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
                "chat_context": ChatContext.GLOBAL.value,
                "session_id": session_id
            }
            
        except Exception as e:
            self.logger.exception("Global AI processing failed: %s", e)
            return {
                "message": "I'm having trouble processing your request. Please try again.",
                "success": False,
                "error": str(e)
            }
    
    def build_prompt(self, context: RichContext) -> str:
        """Build prompt for global business discovery"""
        # Debug: log how many businesses were found
        self.logger.info(f"Building prompt with {len(context.all_businesses)} businesses")
        
        lines = [
            "You are X-SevenAI, a helpful business discovery assistant.",
            f"Current time: {context.current_time.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]
        
        if context.all_businesses:
            lines.append(f"## Available Businesses ({len(context.all_businesses)} found)")
            for business in context.all_businesses[:15]:
                menu_desc = ", ".join([f"{item['name']} (${item['price']})" 
                                     for item in business.get('sample_menu', [])[:2]])
                lines.append(f"• **{business['name']}** - {business.get('description', 'Business services')} | {menu_desc or 'Various services'}")
            lines.append("")
        else:
            lines.append("## Available Business Categories")
            lines.extend([
                "1. **Restaurants** - Fine dining, casual, fast food",
                "2. **Retail** - Department stores, boutiques, electronics",
                "3. **Services** - Salons, gyms, medical offices",
                "4. **Entertainment** - Theaters, venues, arcades",
                "5. **Education** - Schools, courses, tutoring",
                "",
                "*Note: No specific businesses found in database. Please check if businesses are added.*"
            ])
        
        if context.conversation_history:
            lines.append("## Recent Conversation")
            for entry in context.conversation_history[-6:]:
                lines.append(f"{entry['role']}: {entry['content']}")
            lines.append("")
        
        lines.extend([
            f"## User Request\n{context.user_message}",
            "",
            "## Your Response",
            "Respond naturally and helpfully about available businesses, services, and help with reservations or orders."
        ])
        
        return "\n".join(lines)
