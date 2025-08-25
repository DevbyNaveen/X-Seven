"""
Dashboard AI Handler - Routes from Central AI Handler

This module handles dashboard management tasks by routing requests through the central AI handler.
It manages inventory, menu, categories, live orders, and reminders for business dashboards.
"""

from __future__ import annotations

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.models import Business, MenuItem, MenuCategory, Order, OrderStatus
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ai.centralAI.central_ai_handler import CentralAIHandler, ChatType, UnifiedContext


class DashboardFeature(str, Enum):
    """Dashboard features that can be managed"""
    INVENTORY = "inventory"
    MENU = "menu"
    CATEGORIES = "categories"
    LIVE_ORDERS = "live_orders"
    REMINDERS = "reminders"
    ANALYTICS = "analytics"
    STAFF = "staff"
    CUSTOMERS = "customers"


class DashboardAIHandler:
    """
    Dashboard AI Handler - Routes from Central AI Handler
    
    This handler works with the central AI to provide natural language management
    of business dashboard features without hardcoding specific actions.
    """
    
    def __init__(self, db: Session, central_ai = None):
        self.db = db
        if central_ai is None:
            from app.services.ai.centralAI.central_ai_handler import CentralAIHandler
            self.central_ai = CentralAIHandler(db)
        else:
            self.central_ai = central_ai
    
    async def handle_dashboard_request(
        self,
        message: str,
        session_id: str,
        business_id: int,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle dashboard management requests through natural language processing.
        
        Args:
            message: User's natural language request
            session_id: Session identifier
            business_id: Business identifier
            context: Additional context
            
        Returns:
            Dict containing AI response and action information
        """
        try:
            # Build context with dashboard-specific data
            unified_context = await self._build_dashboard_context(
                message=message,
                session_id=session_id,
                business_id=business_id,
                context=context or {}
            )
            
            # Generate AI response using central AI
            prompt = await self._create_dashboard_prompt(unified_context)
            ai_response = await self.central_ai._get_ai_response(prompt)
            final_response = await self.central_ai._clean_response(ai_response)
            
            # Save conversation
            await self.central_ai._save_conversation(unified_context, final_response)
            
            return {
                "message": final_response,
                "success": True,
                # Avoid importing ChatType at runtime to prevent circular import; return string literal
                "chat_type": "dashboard",
                "business_id": business_id
            }
            
        except Exception as e:
            return {
                "message": "I'm having trouble processing your dashboard request. Please try again.",
                "success": False,
                "error": str(e)
            }
    
    async def _build_dashboard_context(
        self,
        message: str,
        session_id: str,
        business_id: int,
        context: Dict[str, Any]
    ) -> UnifiedContext:
        """Build context with dashboard-specific data"""
        # Lazy import to avoid circular import at module load time
        from app.services.ai.centralAI.central_ai_handler import UnifiedContext, ChatType
        unified_context = UnifiedContext(
            chat_type=ChatType.DASHBOARD,
            session_id=session_id,
            user_message=message,
            business_id=business_id,
            current_time=datetime.now()
        )
        
        # Load conversation history
        unified_context.conversation_history = await self.central_ai._load_history(
            session_id=session_id,
            chat_type=ChatType.DASHBOARD,
            business_id=business_id
        )
        
        # Load business data
        unified_context.current_business = await self.central_ai._load_business(business_id)
        unified_context.business_menu = await self.central_ai._load_menu(business_id)
        
        # Load dashboard-specific data
        unified_context.dashboard_data = await self._load_dashboard_data(business_id)
        
        return unified_context
    
    async def _load_dashboard_data(self, business_id: int) -> Dict[str, Any]:
        """Load dashboard-specific data for context"""
        try:
            # Load live orders
            live_orders = self.db.query(Order).filter(
                Order.business_id == business_id,
                Order.status.in_([OrderStatus.PENDING, OrderStatus.PREPARING, OrderStatus.READY])
            ).order_by(Order.created_at.desc()).limit(10).all()
            
            # Load categories
            categories = self.db.query(MenuCategory).filter(
                MenuCategory.business_id == business_id
            ).all()
            
            # Build inventory from MenuItem stock fields (no separate InventoryItem model)
            inventory_items = self.db.query(MenuItem).filter(
                MenuItem.business_id == business_id
            ).all()

            # Reminders model not present; return empty list for now
            reminders = []

            return {
                "live_orders": [{
                    "id": order.id,
                    # Use id as order number (no explicit order_number field)
                    "order_number": order.id,
                    "status": getattr(order.status, "value", str(order.status) if order.status else None),
                    "total_amount": float(order.total_amount or 0),
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "customer_name": order.customer_name
                } for order in live_orders],
                "categories": [{
                    "id": cat.id,
                    "name": cat.name,
                    "description": cat.description
                } for cat in categories],
                "inventory_items": [{
                    "id": item.id,
                    "name": item.name,
                    # Map from MenuItem fields
                    "quantity": int(item.stock_quantity or 0),
                    "unit": "units",
                    "reorder_level": int(item.min_stock_threshold or 0)
                } for item in inventory_items],
                "reminders": [{
                    "id": rem.get("id"),
                    "title": rem.get("title"),
                    "description": rem.get("description"),
                    "due_date": rem.get("due_date"),
                    "is_completed": rem.get(False)
                } for rem in reminders]
            }
        except Exception as e:
            # Return empty data if there's an error
            return {
                "live_orders": [],
                "categories": [],
                "inventory_items": [],
                "reminders": []
            }
    
    async def _create_dashboard_prompt(self, context: UnifiedContext) -> str:
        """Create dashboard-specific prompt for AI"""
        base = f"""You are X-SevenAI Dashboard Manager, an intelligent business management assistant.
Current time: {context.current_time.strftime('%Y-%m-%d %H:%M')}

"""
        
        if context.current_business:
            base += f"## Managing Business: {context.current_business['name']}\n"
            base += f"**Category**: {context.current_business.get('category', 'General')}\n"
            base += f"**Description**: {context.current_business.get('description', 'Business services')}\n\n"
        
        # Add dashboard data context
        if hasattr(context, 'dashboard_data') and context.dashboard_data:
            dashboard_data = context.dashboard_data
            
            # Add live orders
            if dashboard_data.get('live_orders'):
                base += "## Live Orders\n"
                for order in dashboard_data['live_orders'][:5]:  # Limit to 5
                    base += f"- Order #{order['order_number']}: {order['status']} - ${order['total_amount']} ({order.get('customer_name', 'Customer')})\n"
                base += "\n"
            
            # Add inventory items that need attention
            low_stock_items = [item for item in dashboard_data.get('inventory_items', []) 
                             if item['quantity'] <= item['reorder_level']]
            if low_stock_items:
                base += "## Low Stock Alerts\n"
                for item in low_stock_items[:5]:  # Limit to 5
                    base += f"- {item['name']}: {item['quantity']} {item['unit']} (Reorder at {item['reorder_level']})\n"
                base += "\n"
            
            # Add upcoming reminders
            upcoming_reminders = [rem for rem in dashboard_data.get('reminders', []) 
                                if not rem['is_completed']]
            if upcoming_reminders:
                base += "## Upcoming Reminders\n"
                for rem in upcoming_reminders[:5]:  # Limit to 5
                    status = "(Due)" if rem['due_date'] else ""
                    base += f"- {rem['title']}: {rem['description']} {status}\n"
                base += "\n"
        
        # Add conversation history
        if context.conversation_history:
            base += "## Recent Conversation\n"
            for entry in context.conversation_history[-8:]:  # Limit to 8 entries
                base += f"- {entry}\n"
            base += "\n"
        
        base += f"## User Request\n{context.user_message}\n\n"
        base += """## Your Response
You are assisting the business owner/manager with dashboard management tasks. Respond naturally and helpfully:

1. For inventory requests:
   - Help manage stock levels
   - Suggest reorder quantities
   - Identify low stock items
   - Track usage patterns

2. For menu requests:
   - Help manage menu items
   - Suggest pricing changes
   - Update availability
   - Organize categories

3. For order requests:
   - Provide order status updates
   - Help with order modifications
   - Track order history
   - Handle customer inquiries

4. For reminder requests:
   - Set new reminders
   - Update existing reminders
   - Mark reminders as complete
   - Provide reminder summaries

5. For analytics requests:
   - Provide business insights
   - Show performance metrics
   - Suggest improvements
   - Compare time periods

Response Guidelines:
- Be concise and action-oriented
- Use bullet points when listing steps
- If specific data is needed, ask for it clearly
- Focus on business management tasks
- Provide actionable recommendations
- Use markdown formatting for clarity

Example responses:
- \"Here's the current status of your live orders...\"
- \"I've identified 3 low-stock items that need attention...\"
- \"Based on your sales data, I recommend...\"
- \"I can help you update that menu item. What changes would you like to make?\"
"""
        
        return base
