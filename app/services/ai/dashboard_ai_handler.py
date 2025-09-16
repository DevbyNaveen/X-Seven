"""
Dashboard AI Handler - Business management service
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.core.ai.base_handler import BaseAIHandler
from app.core.ai.types import RichContext, ChatContext
from app.core.ai.context_builders import build_dashboard_context, load_conversation_history
from app.services.ai.Food.category_manager import CategoryManager
from app.services.ai.Food.menu_manager import MenuManager
from app.services.ai.Food.order_manager import OrderManager
from app.services.ai.Food.inventory_manager import InventoryManager
from app.services.ai.Food.reports_manager import ReportsManager


class DashboardAIHandler(BaseAIHandler):
    """Handler for dashboard management chat"""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.logger = logging.getLogger(__name__)
        
        # Initialize dashboard managers
        self.category_manager = CategoryManager(db)
        self.menu_manager = MenuManager(db)
        self.order_manager = OrderManager(db)
        self.inventory_manager = InventoryManager(db)
        self.reports_manager = ReportsManager(db)
    
    async def process_message(
        self,
        message: str,
        session_id: str,
        business_id: int,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a dashboard chat message"""
        try:
            # Build rich context
            context = RichContext(
                chat_context=ChatContext.DASHBOARD,
                session_id=session_id,
                user_message=message,
                business_id=business_id,
                user_id=user_id
            )
            
            # Load dashboard context
            context = await build_dashboard_context(context, business_id)
            
            # Load conversation history
            context.conversation_history = await load_conversation_history(
                context, session_id, ChatContext.DASHBOARD, business_id
            )
            
            # Build prompt
            prompt = self.build_prompt(context)
            
            # Get AI response
            response = await self.get_ai_response(prompt)
            
            # Check for dashboard actions
            intent = self.extract_json_from_response(response)
            if intent and intent.get('action'):
                action_result = await self._execute_dashboard_action(business_id, intent)
                if action_result:
                    response += f"\n\n{action_result.get('message', '')}"
            
            # Save conversation
            await self.save_conversation(context, response)
            
            return {
                "message": response,
                "success": True,
                "chat_context": ChatContext.DASHBOARD.value,
                "business_id": business_id,
                "session_id": session_id
            }
            
        except Exception as e:
            self.logger.exception("Dashboard AI processing failed: %s", e)
            return {
                "message": "Management system temporarily unavailable. Please try again.",
                "success": False,
                "error": str(e)
            }
    
    def build_prompt(self, context: RichContext) -> str:
        """Build prompt for dashboard management"""
        lines = [
            f"You are X-SevenAI Dashboard Manager for {context.current_business['name']}.",
            f"Current time: {context.current_time.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]
        
        if context.current_business:
            lines.append(f"## Managing: {context.current_business['name']}")
            lines.append(f"**Category**: {context.current_business.get('category', 'General')}")
            lines.append("")
        
        if context.live_orders:
            lines.append("## Live Orders")
            for order in context.live_orders[:5]:
                lines.append(f"• Order #{order['id']}: {order['status']} - ${order['total_amount']}")
            lines.append("")
        
        if context.inventory_status.get('low_stock_count', 0) > 0:
            lines.append("## Inventory Alerts")
            lines.append(f"• {context.inventory_status['low_stock_count']} items need reordering")
            for item in context.inventory_status.get('low_stock_items', [])[:3]:
                lines.append(f"  - {item['name']}: {item['stock_quantity']} in stock")
            lines.append("")
        
        if context.business_categories:
            lines.append("## Menu Categories")
            for cat in context.business_categories:
                lines.append(f"• {cat['name']} (ID: {cat['id']})")
            lines.append("")
        
        if context.conversation_history:
            lines.append("## Recent Conversation")
            for entry in context.conversation_history[-6:]:
                lines.append(f"{entry['role']}: {entry['content']}")
            lines.append("")
        
        lines.extend([
            f"## Management Request\n{context.user_message}",
            "",
            "## Your Response",
            "You are the business management assistant. Provide actionable insights and help manage operations."
        ])
        
        return "\n".join(lines)
    
    async def _execute_dashboard_action(self, business_id: int, intent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute dashboard actions based on intent"""
        domain = intent.get('domain', '')
        
        try:
            if domain == 'category':
                return await self.category_manager.handle_category_request(business_id, intent)
            elif domain == 'menu':
                return await self.menu_manager.handle_menu_request(business_id, intent)
            elif domain == 'order':
                return await self.order_manager.handle_order_request(business_id, intent)
            elif domain == 'inventory':
                return await self.inventory_manager.handle_inventory_request(business_id, intent)
            elif domain == 'reports':
                return await self.reports_manager.handle_reports_request(business_id, intent)
        except Exception as e:
            self.logger.error("Dashboard action execution failed: %s", e)
            return {"success": False, "message": f"Action failed: {str(e)}"}
