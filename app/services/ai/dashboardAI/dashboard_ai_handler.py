# app/services/ai/dashboardAI/dashboard_ai_handler.py
"""
Dashboard AI Handler - Routes from Central AI Handler

This module handles dashboard management tasks by routing requests through the central AI handler.
It manages inventory, menu, categories, live orders, and reminders for business dashboards.
"""

from __future__ import annotations

import json
import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.models import Business, MenuItem, MenuCategory, Order, OrderStatus
from typing import TYPE_CHECKING
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# Import action managers
from app.services.ai.dashboardAI.Food.category_manager import CategoryManager
from app.services.ai.dashboardAI.Food.menu_manager import MenuManager
from app.services.ai.dashboardAI.Food.order_manager import OrderManager
from app.services.ai.dashboardAI.Food.inventory_manager import InventoryManager
from app.services.ai.dashboardAI.Food.reports_manager import ReportsManager

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
    REPORTS = "reports"


class DashboardAIHandler:
    """
    Dashboard AI Handler - Specialized handler for dashboard operations
    
    This handler provides natural language management of business dashboard features.
    It is designed to be called by the CentralAIHandler, not to create its own instance.
    """
    
    def __init__(self, db: Session):
        self.db = db
        
        # Initialize action managers
        self.category_manager = CategoryManager(db)
        self.menu_manager = MenuManager(db)
        self.order_manager = OrderManager(db)
        self.inventory_manager = InventoryManager(db)
        self.reports_manager = ReportsManager(db)
    
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
            dashboard_context = await self._build_dashboard_context(
                message=message,
                session_id=session_id,
                business_id=business_id,
                context=context or {}
            )
            
            # Generate AI response using dashboard-specific prompt
            prompt = await self._create_dashboard_prompt(dashboard_context)
            
            # Use Groq client directly for AI response
            from app.config.settings import settings
            from groq import Groq
            
            client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
            if not client:
                return {
                    "message": "AI service is not configured",
                    "success": False,
                    "error": "Groq API key not found"
                }
            
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL or "llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.7
            )
            
            cleaned_response = response.choices[0].message.content.strip()
            
            # Extract structured intent from AI response
            intent = self._extract_intent_from_response(cleaned_response)
            
            # If AI provided structured intent, execute the corresponding action
            if intent and intent.get("action"):
                action_result = await self._execute_action(business_id, intent)
                if action_result and action_result.get("message"):
                    cleaned_response += "\n\n" + action_result["message"]
            
            return {
                "message": cleaned_response,
                "success": True,
                "chat_type": "dashboard",
                "business_id": business_id
            }
            
        except Exception as e:
            logger.exception("Dashboard request failed: %s", e)
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
    ) -> Dict[str, Any]:
        """Build context with dashboard-specific data"""
        # Load conversation history
        from app.models import Message
        conversation_history = []
        if session_id:
            messages = self.db.query(Message).filter(
                Message.session_id == session_id,
                Message.chat_type == "dashboard"
            ).order_by(Message.created_at.desc()).limit(10).all()
            
            for msg in reversed(messages):
                conversation_history.append(f"User: {msg.user_message}")
                conversation_history.append(f"AI: {msg.ai_response}")
        
        # Load business data
        from app.models import Business
        business = self.db.query(Business).filter(Business.id == business_id).first()
        current_business = None
        if business:
            current_business = {
                "id": business.id,
                "name": business.name,
                "description": business.description,
                "category": business.category,
                "is_active": business.is_active
            }
        
        # Load business menu
        from app.models import MenuItem
        menu_items = self.db.query(MenuItem).filter(MenuItem.business_id == business_id).all()
        business_menu = []
        for item in menu_items:
            business_menu.append({
                "id": item.id,
                "name": item.name,
                "price": float(item.price),
                "description": item.description,
                "is_available": item.is_available
            })
        
        # Load dashboard-specific data
        dashboard_data = await self._load_dashboard_data(business_id)
        
        return {
            "chat_type": "dashboard",
            "session_id": session_id,
            "user_message": message,
            "business_id": business_id,
            "current_time": datetime.now(),
            "conversation_history": conversation_history,
            "current_business": current_business,
            "business_menu": business_menu,
            "dashboard_data": dashboard_data
        }
    
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
                    "quantity": int(item.stock_quantity or 0),
                    "unit": "units",
                    "reorder_level": int(item.min_stock_threshold or 0)
                } for item in inventory_items],
                "reminders": [{
                    "id": rem.get("id"),
                    "title": rem.get("title"),
                    "description": rem.get("description"),
                    "due_date": rem.get("due_date"),
                    "is_completed": rem.get("is_completed", False)
                } for rem in reminders]
            }
        except Exception as e:
            logger.exception("Failed loading dashboard data for business %s: %s", business_id, e)
            # Return empty data if there's an error
            return {
                "live_orders": [],
                "categories": [],
                "inventory_items": [],
                "reminders": []
            }
    
    async def _create_dashboard_prompt(self, context: Dict[str, Any]) -> str:
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

First, extract the user's intent in JSON format:
{
  "domain": "category|menu|order|inventory|reports",
  "action": "add_category|list_categories|update_category|delete_category|add_item|list_menu|update_item|delete_item|list_orders|view_order|update_order_status|cancel_order|list_inventory|update_stock|low_stock_report|get_daily_summary|get_weekly_performance|get_monthly_comprehensive|get_sales_report|get_customer_insights|get_financial_report|get_operational_report|get_growth_analysis|generate_custom_report|export_business_data|schedule_report|get_report_templates|generate_report_from_template",
  "data": {
    // Action-specific parameters
  }
}

Then, respond naturally to the user, confirming the action or asking for clarification.

Response Guidelines:
1. For category requests:
   - add_category: Create new menu category
   - list_categories: Show all categories
   - update_category: Modify existing category
   - delete_category: Remove category (only if empty)

2. For menu requests:
   - add_item: Add new menu item
   - list_menu: Show all menu items
   - update_item: Modify existing menu item
   - delete_item: Remove menu item

3. For order requests:
   - list_orders: Show recent orders (can filter by status)
   - view_order: Show details of specific order
   - update_order_status: Change order status
   - cancel_order: Cancel an order

4. For inventory requests:
   - list_inventory: Show all inventory items
   - update_stock: Update stock levels or reorder points
   - low_stock_report: Show items needing reorder

5. For reports requests:
   - get_daily_summary: Generate daily business summary
   - get_weekly_performance: Generate weekly performance report
   - get_monthly_comprehensive: Generate comprehensive monthly report
   - get_sales_report: Generate sales report for different periods
   - get_customer_insights: Generate customer behavior analysis
   - get_financial_report: Generate financial performance report
   - get_operational_report: Generate operational efficiency metrics
   - get_growth_analysis: Generate business growth analysis
   - generate_custom_report: Generate custom report with specific parameters
   - export_business_data: Export business data in specified format
   - schedule_report: Schedule recurring reports
   - get_report_templates: Get available report templates
   - generate_report_from_template: Generate report from predefined template

Examples:
- To add a category: {"domain": "category", "action": "add_category", "data": {"name": "Appetizers", "description": "Starters and small plates"}}
- To add a menu item: {"domain": "menu", "action": "add_item", "data": {"name": "Caesar Salad", "price": 8.99, "description": "Fresh romaine with parmesan", "category_name": "Salads"}}
- To update stock: {"domain": "inventory", "action": "update_stock", "data": {"item_name": "Tomatoes", "quantity": 50, "reorder_level": 20}}
- To list orders: {"domain": "order", "action": "list_orders", "data": {"status": "pending"}}
- To get daily summary: {"domain": "reports", "action": "get_daily_summary", "data": {}}
- To get weekly performance: {"domain": "reports", "action": "get_weekly_performance", "data": {}}
- To get monthly report: {"domain": "reports", "action": "get_monthly_comprehensive", "data": {"months": 1}}
- To get sales report: {"domain": "reports", "action": "get_sales_report", "data": {"period": "weekly"}}
- To get customer insights: {"domain": "reports", "action": "get_customer_insights", "data": {}}
- To get financial report: {"domain": "reports", "action": "get_financial_report", "data": {}}
- To get operational report: {"domain": "reports", "action": "get_operational_report", "data": {}}
- To get growth analysis: {"domain": "reports", "action": "get_growth_analysis", "data": {"months": 6}}
- To generate custom report: {"domain": "reports", "action": "generate_custom_report", "data": {"report_type": "custom", "start_date": "2023-01-01", "end_date": "2023-01-31", "format": "pdf"}}
- To export data: {"domain": "reports", "action": "export_business_data", "data": {"data_type": "orders", "start_date": "2023-01-01", "end_date": "2023-01-31", "format": "csv"}}
- To schedule report: {"domain": "reports", "action": "schedule_report", "data": {"report_type": "daily_summary", "frequency": "daily", "format": "pdf", "email": "manager@business.com"}}
- To get templates: {"domain": "reports", "action": "get_report_templates", "data": {}}
- To generate from template: {"domain": "reports", "action": "generate_report_from_template", "data": {"template_id": "daily_summary", "start_date": "2023-01-01", "end_date": "2023-01-31", "format": "pdf"}}

Response Format:
1. First provide the JSON intent block
2. Then provide a natural language response to the user

Example response:
{
  "domain": "category",
  "action": "add_category",
  "data": {
    "name": "Desserts",
    "description": "Sweet treats and desserts"
  }
}
I'll add the 'Desserts' category to your menu right away.
"""
        
        return base

    def _extract_intent_from_response(self, response: str) -> Dict[str, Any]:
        """Extract structured intent from AI response"""
        # 1) Prefer fenced JSON blocks (```json { ... } ``` or ``` { ... } ```)
        try:
            fenced_blocks = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", response, flags=re.IGNORECASE)
            for block in fenced_blocks:
                try:
                    intent = json.loads(block)
                    if isinstance(intent, dict) and intent.get("action"):
                        return intent
                except Exception:
                    continue
        except Exception:
            pass

        # 2) Fallback: scan for the first balanced JSON object and try to parse it
        def find_balanced_json(text: str) -> Optional[str]:
            start = text.find("{")
            while start != -1:
                depth = 0
                in_str = False
                esc = False
                for i in range(start, len(text)):
                    ch = text[i]
                    if in_str:
                        if esc:
                            esc = False
                        elif ch == "\\":
                            esc = True
                        elif ch == '"':
                            in_str = False
                    else:
                        if ch == '"':
                            in_str = True
                        elif ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if depth == 0:
                                return text[start:i+1]
                start = text.find("{", start + 1)
            return None

        candidate = find_balanced_json(response)
        if candidate:
            try:
                intent = json.loads(candidate)
                if isinstance(intent, dict) and intent.get("action"):
                    return intent
            except Exception:
                pass
        return {}

    async def _execute_action(self, business_id: int, intent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute the action based on extracted intent"""
        domain = intent.get("domain", "")
        action = intent.get("action", "")
        
        try:
            if domain == "category":
                return await self.category_manager.handle_category_request(business_id, intent)
            elif domain == "menu":
                return await self.menu_manager.handle_menu_request(business_id, intent)
            elif domain == "order":
                return await self.order_manager.handle_order_request(business_id, intent)
            elif domain == "inventory":
                return await self.inventory_manager.handle_inventory_request(business_id, intent)
            elif domain == "reports":
                return await self.reports_manager.handle_reports_request(business_id, intent)
            else:
                return None
        except Exception as e:
            logger.exception("Error executing dashboard action: %s", e)
            return {
                "success": False,
                "message": f"Error executing action: {str(e)}"
            }