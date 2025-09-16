# app/services/ai/simple_central_ai_handler.py
"""
Simple Central AI Handler - Let AI understand and act naturally
"""
from __future__ import annotations

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import re
import logging

from sqlalchemy.orm import Session
from groq import Groq

from app.models import Business, MenuItem, Message, Order, OrderStatus
from app.config.settings import settings
# Import DashboardAIHandler only when needed to avoid circular imports


class ChatType(str, Enum):
    GLOBAL = "global"
    DEDICATED = "dedicated"
    DASHBOARD = "dashboard"


@dataclass
class UnifiedContext:
    chat_type: ChatType
    session_id: str
    user_message: str
    business_id: Optional[int] = None
    all_businesses: List[Dict] = None
    current_business: Optional[Dict] = None
    business_menu: List[Dict] = None
    conversation_history: List[str] = None
    current_time: datetime = None
    dashboard_context: Optional[Dict[str, Any]] = None


class CentralAIHandler:
    """
    Simple AI Handler - Let AI understand and respond naturally
    """

    def __init__(self, db: Session):
        self.db = db
        self.client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        self.model = settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        self.logger = logging.getLogger(__name__)
        # Dashboard function definitions
        self.dashboard_functions = [
            {
                "name": "update_menu_item",
                "description": "Update details of a menu item including price, description, or availability",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer", "description": "ID of the menu item to update"},
                        "name": {"type": "string", "description": "New name for the menu item"},
                        "price": {"type": "number", "description": "New price for the menu item"},
                        "description": {"type": "string", "description": "New description for the menu item"},
                        "is_available": {"type": "boolean", "description": "Whether the item is available"}
                    }
                }
            },
            {
                "name": "check_inventory",
                "description": "Check current inventory levels and identify low stock items",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string", "description": "Optional name of specific item to check"}
                    }
                }
            },
            {
                "name": "get_live_orders",
                "description": "Get current live orders with their status",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Optional filter by order status"}
                    }
                }
            },
            {
                "name": "update_order_status",
                "description": "Update the status of an order",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "integer", "description": "ID of the order to update"},
                        "status": {"type": "string", "description": "New status for the order"}
                    }
                }
            },
            {
                "name": "get_table_occupancy",
                "description": "Get current table occupancy status",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_id": {"type": "integer", "description": "Optional ID of specific table to check"}
                    }
                }
            },
            {
                "name": "add_menu_category",
                "description": "Add a new menu category",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the new category"},
                        "description": {"type": "string", "description": "Description of the category"}
                    }
                }
            },
            {
                "name": "generate_sales_report",
                "description": "Generate a sales report for a specific period",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date for the report (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "End date for the report (YYYY-MM-DD)"}
                    }
                }
            }
        ]

    async def chat(
        self,
        message: str,
        session_id: str,
        chat_type: ChatType = ChatType.GLOBAL,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main chat method - Let AI work naturally
        """
        try:
            # For DASHBOARD chat type, delegate to DashboardAIHandler
            if chat_type == ChatType.DASHBOARD:
                business_id = context.get("business_id") if context else None
                if business_id:
                    # Import DashboardAIHandler only when needed
                    from app.services.ai.dashboardAI.dashboard_ai_handler import DashboardAIHandler
                    
                    # Create DashboardAIHandler instance (no circular dependency)
                    dashboard_handler = DashboardAIHandler(self.db)
                    
                    # Delegate to DashboardAIHandler
                    return await dashboard_handler.handle_dashboard_request(
                        message=message,
                        session_id=session_id,
                        business_id=business_id,
                        context=context
                    )
                else:
                    return {
                        "message": "Business ID is required for dashboard operations",
                        "success": False,
                        "error": "Missing business_id"
                    }
            
            # For other chat types, use the existing implementation
            # Build context with real data
            unified_context = await self._build_context(
                message=message,
                session_id=session_id,
                chat_type=chat_type,
                business_id=context.get("business_id") if context else None
            )
            
            # Generate AI response
            prompt = await self._create_simple_prompt(unified_context)
            ai_response = await self._get_ai_response(prompt)
            final_response = await self._clean_response(ai_response)
            
            # Save conversation
            await self._save_conversation(unified_context, final_response)
            
            return {
                "message": final_response,
                "success": True,
                "chat_type": chat_type.value
            }
            
        except Exception as e:
            return {
                "message": "I'm having trouble right now. Please try again in a moment.",
                "success": False,
                "error": str(e)
            }

    async def _build_context(
        self,
        message: str,
        session_id: str,
        chat_type: ChatType,
        business_id: Optional[int]
    ) -> UnifiedContext:
        """Build context with real data"""
        context = UnifiedContext(
            chat_type=chat_type,
            session_id=session_id,
            user_message=message,
            current_time=datetime.now(),
            business_id=business_id
        )
        
        # Load conversation history (isolate by chat type and business)
        context.conversation_history = await self._load_history(
            session_id=session_id,
            chat_type=chat_type,
            business_id=business_id,
        )
        
        # Load business data
        if chat_type == ChatType.GLOBAL:
            context.all_businesses = await self._load_businesses()
        elif chat_type in (ChatType.DEDICATED, ChatType.DASHBOARD) and business_id:
            context.current_business = await self._load_business(business_id)
            context.business_menu = await self._load_menu(business_id)
            # For dashboard chat, also load dashboard context
            if chat_type == ChatType.DASHBOARD:
                context.dashboard_context = await self._build_dashboard_context(business_id)
        
        return context

    async def _create_simple_prompt(self, context: UnifiedContext) -> str:
        """Create simple prompt - let AI understand naturally"""
        base = f"""You are X-SevenAI, a helpful business assistant.
Current time: {context.current_time.strftime('%Y-%m-%d %H:%M')}

"""
        
        if context.chat_type == ChatType.GLOBAL:
            return self._create_global_simple_prompt(base, context)
        elif context.chat_type == ChatType.DEDICATED:
            return self._create_dedicated_simple_prompt(base, context)
        elif context.chat_type == ChatType.DASHBOARD:
            return self._create_dashboard_simple_prompt(base, context)
        
        return base + f"User: {context.user_message}\nAssistant:"

    def _create_global_simple_prompt(self, base: str, context: UnifiedContext) -> str:
        """Simple global prompt"""
        lines = [base.strip()]
        
        # Add real business data
        if context.all_businesses:
            lines.append("## Available Businesses")
            business_list = []
            for b in context.all_businesses[:15]:
                menu_items = []
                if b.get('sample_menu'):
                    for item in b['sample_menu'][:2]:
                        menu_items.append(f"{item['name']} (${item['price']})")
                menu_str = ", ".join(menu_items) if menu_items else "Various services"
                business_list.append(f"• **{b['name']}**: {b.get('description', 'Business services')} | {menu_str}")
            lines.append("\n".join(business_list))
        
        # Add conversation history
        if context.conversation_history:
            lines.append("\n## Conversation")
            for entry in context.conversation_history[-12:]:
                lines.append(f"- {entry}")
        
        lines.append(f"\n## User Request\n{context.user_message}")
        lines.append("\n## Your Response")
        lines.append("Respond naturally and helpfully:")
        lines.append("- Use **bold** for business names")
        lines.append("- Use bullet points for lists")
        lines.append("- Be conversational and friendly")
        lines.append("- ONLY mention businesses from the list above")
        lines.append("- Let the user guide the conversation")
        lines.append("- Handle reservations, orders, and invoices naturally")
        lines.append("- No need to mention switching or routing")
        
        return "\n".join(lines)

    async def _create_dashboard_simple_prompt(self, base: str, context: UnifiedContext) -> str:
        """Simple dashboard prompt for business owners/managers"""
        lines = [base.strip()]
        
        if context.current_business:
            lines.append(f"## Managing: {context.current_business['name']}")
            lines.append(f"**Category**: {context.current_business.get('category', 'General')}")
        
        # Add business context if available
        if context.dashboard_context:
            dashboard_data = context.dashboard_context
            
            # Add live orders context
            if dashboard_data.get('live_orders'):
                lines.append("\n## Live Orders")
                for order in dashboard_data['live_orders'][:5]:  # Limit to 5
                    lines.append(f"- Order #{order['id']}: {order['status']} - ${order['total_amount']}")
            
            # Add inventory context
            inventory_status = dashboard_data.get('inventory_status', {})
            if inventory_status.get('low_stock_count', 0) > 0:
                lines.append("\n## Inventory Alerts")
                lines.append(f"- {inventory_status['low_stock_count']} items need reordering")
                for item in inventory_status.get('low_stock_items', [])[:3]:
                    lines.append(f"  • {item['name']}: {item['stock_quantity']} in stock (min: {item['min_stock_threshold']})")
        
        lines.append("\n## Conversation (recent)")
        if context.conversation_history:
            for entry in context.conversation_history[-12:]:
                lines.append(f"- {entry}")
        
        lines.append(f"\n## Request\n{context.user_message}")
        lines.append("\n## Your Response")
        lines.append("You are assisting the business owner with management tasks:")
        lines.append("- Be concise and action-oriented")
        lines.append("- Use bullet points when listing steps")
        lines.append("- If data is needed, ask for it clearly")
        
        # Add available functions
        lines.append("\n## Available Functions")
        lines.append("You can perform these business operations:")
        for func in self.dashboard_functions:
            lines.append(f"- {func['name']}: {func['description']}")
        
        return "\n".join(lines)

    def _create_dedicated_simple_prompt(self, base: str, context: UnifiedContext) -> str:
        """Simple dedicated prompt"""
        lines = [base.strip()]
        
        # Add business context
        if context.current_business:
            lines.append(f"## Business: {context.current_business['name']}")
            lines.append(f"**Category**: {context.current_business.get('category', 'General')}")
            lines.append(f"**About**: {context.current_business.get('description', 'Business services')}")
        
        # Add menu
        if context.business_menu:
            lines.append("\n## Services")
            menu_items = []
            for item in context.business_menu[:12]:
                menu_items.append(f"• **{item['name']}** - ${item['price']} ({item.get('description', 'Service')})")
            lines.append("\n".join(menu_items))
        
        # Add conversation history
        if context.conversation_history:
            lines.append("\n## Conversation")
            for entry in context.conversation_history[-12:]:
                lines.append(f"- {entry}")
        
        lines.append(f"\n## Customer Message\n{context.user_message}")
        lines.append("\n## Your Response")
        lines.append("You represent this business. Respond naturally:")
        lines.append("- Be helpful about services and bookings")
        lines.append("- Use friendly, professional tone")
        lines.append("- Use **bold** for key terms")
        lines.append("- Handle reservations, orders, and invoices naturally")
        lines.append("- Collect customer information conversationally")
        lines.append("- No need to mention switching or routing")
        
        return "\n".join(lines)

    async def _load_history(self, session_id: str, chat_type: ChatType, business_id: Optional[int]) -> List[str]:
        """Load conversation history, scoped appropriately to avoid cross-contamination"""
        query = self.db.query(Message).filter(Message.session_id == session_id)
        # For global chats, only include messages without business context
        if chat_type == ChatType.GLOBAL:
            query = query.filter(Message.business_id.is_(None))
        # For dedicated/dashboard chats, restrict to the specific business
        elif chat_type in (ChatType.DEDICATED, ChatType.DASHBOARD):
            if business_id is not None:
                query = query.filter(Message.business_id == business_id)
            else:
                # No business specified -> return empty history for safety
                return []
        messages = (
            query.order_by(Message.created_at.desc()).limit(50).all()
        )
        history = []
        for msg in reversed(messages):
            sender = "User" if msg.sender_type == "customer" else "Assistant"
            history.append(f"{sender}: {msg.content}")
        return history

    async def _load_businesses(self) -> List[Dict]:
        """Load active businesses"""
        businesses = self.db.query(Business).filter(Business.is_active == True).limit(20).all()
        
        return [{
            "id": biz.id,
            "name": biz.name,
            "category": biz.category,
            "description": biz.description,
            "sample_menu": [
                {
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.base_price or 0)
                } for item in self.db.query(MenuItem).filter(
                    MenuItem.business_id == biz.id,
                    MenuItem.is_available == True
                ).limit(3).all()
            ]
        } for biz in businesses]

    async def _load_business(self, business_id: int) -> Optional[Dict]:
        """Load specific business"""
        business = self.db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return None
        return {
            "id": business.id,
            "name": business.name,
            "category": business.category,
            "description": business.description,
            "is_active": business.is_active
        }

    async def _load_menu(self, business_id: int) -> List[Dict]:
        """Load business menu"""
        menu_items = self.db.query(MenuItem).filter(
            MenuItem.business_id == business_id,
            MenuItem.is_available == True
        ).all()
        
        return [{
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "price": float(item.base_price or 0),
            "category": item.category_id,
            "available": item.is_available
        } for item in menu_items]

    async def _build_dashboard_context(self, business_id: int) -> Dict[str, Any]:
        """Build dashboard context with business data for enhanced AI understanding"""
        try:
            # Load live orders
            live_orders_response = self.db.table("orders").select("*").eq("business_id", business_id).in_("status", ["PENDING", "PREPARING", "READY"]).order("created_at", desc=True).limit(10).execute()
            live_orders = live_orders_response.data if live_orders_response.data else []
            
            # Load menu items for inventory context
            menu_items_response = self.db.table("menu_items").select("*").eq("business_id", business_id).execute()
            menu_items = menu_items_response.data if menu_items_response.data else []
            
            # Build inventory context
            inventory_items = [{
                "id": item['id'],
                "name": item['name'],
                "stock_quantity": int(item.get('stock_quantity', 0) or 0),
                "min_stock_threshold": int(item.get('min_stock_threshold', 0) or 0),
                "needs_reorder": int(item.get('stock_quantity', 0) or 0) <= int(item.get('min_stock_threshold', 0) or 0)
            } for item in menu_items]
            
            # Identify low stock items
            low_stock_items = [item for item in inventory_items if item["needs_reorder"]]
            
            # Build order context
            order_context = [{
                "id": order['id'],
                "status": order.get('status'),
                "total_amount": float(order.get('total_amount', 0) or 0),
                "customer_name": order.get('customer_name'),
                "items_count": len(order.get('items', [])) if 'items' in order else 0,
                "created_at": order.get('created_at'),
                "estimated_ready_time": order.get('estimated_ready_time')
            } for order in live_orders]
            
            return {
                "live_orders": order_context,
                "inventory_status": {
                    "total_items": len(inventory_items),
                    "low_stock_items": low_stock_items,
                    "low_stock_count": len(low_stock_items)
                },
                "business_id": business_id
            }
        except Exception as e:
            self.logger.exception("Failed to build dashboard context for business %s: %s", business_id, e)
            return {
                "live_orders": [],
                "inventory_status": {
                    "total_items": 0,
                    "low_stock_items": [],
                    "low_stock_count": 0
                },
                "business_id": business_id
            }

    async def _get_ai_response(self, prompt: str) -> str:
        """Get AI response"""
        if not self.client:
            return "AI service unavailable. Please try again later."
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": """You are X-SevenAI, a helpful business assistant.
Let the conversation flow naturally.
Use proper spacing and punctuation.
Use markdown formatting for clarity.
Handle reservations, orders, and invoices naturally.
Let the user guide the conversation.
No need to mention switching or routing - just respond naturally."""},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.exception("AI response generation failed: %s", e)
            return "I'm having trouble processing your request. Please try again."

    async def _process_dashboard_request(
        self,
        message: str,
        business_id: int,
        dashboard_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process dashboard request and detect if AI wants to call a function"""
        prompt = f"""You are X-SevenAI Dashboard Manager, an intelligent business management assistant.

Current Business Context:
- Business ID: {business_id}

Live Orders:
{chr(10).join([f'- Order #{order["id"]}: {order["status"]} - ${order["total_amount"]}' for order in dashboard_context.get('live_orders', [])[:5]])}

Inventory Status:
- Total items: {dashboard_context.get('inventory_status', {}).get('total_items', 0)}
- Low stock items: {dashboard_context.get('inventory_status', {}).get('low_stock_count', 0)}

User Request: {message}

Available Functions:
{chr(10).join([f'- {func["name"]}: {func["description"]}' for func in self.dashboard_functions])}

If you need to perform a business operation, respond ONLY with a JSON object in this format:
{{"function_call": {{"name": "function_name", "arguments": {{"param1": "value1"}}}}}}

Otherwise, respond naturally to the user."""
        
        try:
            ai_response = await self._get_ai_response(prompt)
            return ai_response
        except Exception as e:
            return f"Error generating response: {str(e)}"

    async def _clean_response(self, text: str) -> str:
        """Clean response formatting"""
        if not text:
            return text
            
        # Fix common formatting issues
        fixes = [
            (r"It'snicetomeetyou", "It's nice to meet you"),
            (r"Itseemslikeyou're", "It seems like you're"),
            (r"You'relookingfor", "You're looking for"),
            (r"HowcanIassistyou", "How can I assist you"),
            (r"I'mheretohelp", "I'm here to help"),
            (r'([.!?])([A-Z])', r'\1 \2'),
            (r'•(\w)', r'• \1'),
        ]
        
        for pattern, replacement in fixes:
            text = re.sub(pattern, replacement, text)
        
        return re.sub(r' +', ' ', text).strip()

    async def _save_conversation(self, context: UnifiedContext, response: str):
        """Save conversation"""
        try:
            self.db.add(Message(
                session_id=context.session_id,
                sender_type="customer",
                content=context.user_message,
                message_type="text",
                business_id=context.business_id
            ))
            
            self.db.add(Message(
                session_id=context.session_id,
                sender_type="bot",
                content=response,
                message_type="text",
                business_id=context.business_id,
                ai_model_used=self.model
            ))
            
            self.db.commit()
        except Exception as e:
            self.logger.exception("Failed to save conversation for session %s: %s", context.session_id, e)
            self.db.rollback()