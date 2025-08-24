# app/services/ai/central_ai_handler.py
"""
Enhanced Central AI Handler - The single brain for all chat types
Handles: Global Chat, Dedicated Chat, and Dashboard Chat
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from enum import Enum

from sqlalchemy.orm import Session

try:
    from groq import Groq  # type: ignore
except Exception:
    Groq = None  # type: ignore

from app.models import Business, MenuItem, Message, Order, Table
from app.config.settings import settings

# Session context store (in production, use Redis)
_SESSION_CONTEXTS: Dict[str, Dict[str, Any]] = {}


class ChatType(str, Enum):
    """Types of chat interactions."""
    GLOBAL = "global"           # Discovery across all businesses
    DEDICATED = "dedicated"     # Customer chat for specific business
    DASHBOARD = "dashboard"     # Business owner/staff management


class CentralAIHandler:
    """
    Central AI Handler - Single brain for all chat interactions.
    
    Features:
    - Handles all three chat types with context switching
    - Maintains conversation memory across sessions  
    - Integrates with business operations (orders, bookings, inventory)
    - Supports voice, text, and dashboard interactions
    """

    def __init__(self, db: Session):
        self.db = db
        self.model = settings.GROQ_MODEL or "llama-3.1-8b-instant"
        self.max_tokens = getattr(settings, "GROQ_MAX_TOKENS", 1200) or 1200
        self.max_history = getattr(settings, "GROQ_MAX_HISTORY", 6) or 6
        
        # Initialize Groq client
        self.client = None
        if settings.GROQ_API_KEY and Groq is not None:
            try:
                self.client = Groq(api_key=settings.GROQ_API_KEY)
            except Exception:
                self.client = None

    async def chat(
        self,
        message: str,
        session_id: str,
        chat_type: ChatType = ChatType.GLOBAL,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main chat method - routes to appropriate handler based on chat type.
        
        Args:
            message: User's message
            session_id: Session identifier
            chat_type: Type of chat (global, dedicated, dashboard)
            context: Additional context (business_id, user_role, etc.)
            
        Returns:
            Response with message and metadata
        """
        context = context or {}
        
        # Route to appropriate handler based on chat type
        if chat_type == ChatType.GLOBAL:
            return await self._handle_global_chat(message, session_id, context)
        elif chat_type == ChatType.DEDICATED:
            return await self._handle_dedicated_chat(message, session_id, context)
        elif chat_type == ChatType.DASHBOARD:
            return await self._handle_dashboard_chat(message, session_id, context)
        else:
            return {"message": "Invalid chat type", "success": False}

    async def _handle_global_chat(
        self, 
        message: str, 
        session_id: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle global discovery chat across all businesses."""
        
        # Get all active businesses
        businesses = self.db.query(Business).filter(Business.is_active == True).all()
        
        if not businesses:
            return {
                "message": "No businesses are currently available.",
                "success": True,
                "chat_type": "global"
            }
        
        # Build business context (limit for performance)
        max_biz = 8
        business_list = []
        
        for biz in businesses[:max_biz]:
            # Get sample menu items
            items = (
                self.db.query(MenuItem)
                .filter(MenuItem.business_id == biz.id, MenuItem.is_available == True)
                .limit(3)
                .all()
            )
            
            business_list.append({
                "id": biz.id,
                "name": biz.name,
                "category": str(biz.category) if biz.category else None,
                "description": biz.description,
                "sample_menu": [
                    {"name": item.name, "price": float(item.base_price or 0)}
                    for item in items
                ]
            })
        
        # Build conversation history
        history = self._get_conversation_history(session_id)
        session_context = self._get_session_context(session_id)
        
        # Extract customer info
        extracted_info = self._extract_customer_info(message)
        if extracted_info:
            self._update_session_context(session_id, extracted_info)
            session_context = self._get_session_context(session_id)
        
        # Create global discovery prompt
        prompt = f"""You are X-SevenAI, helping users discover and interact with local businesses.

AVAILABLE BUSINESSES:
{json.dumps(business_list, separators=(',', ':'))}

CONVERSATION HISTORY:
{chr(10).join(history[-self.max_history:])}

CURRENT USER MESSAGE: {message}

{self._get_customer_context_text(session_context)}

GLOBAL DISCOVERY GUIDELINES:
- Help users find businesses that match their needs
- Provide recommendations based on cuisine, location, or preferences  
- When user shows interest in a specific business, provide more details
- For orders/bookings, guide them to contact the business directly
- Be conversational and helpful, not robotic
- Ask clarifying questions if needed
- Don't overwhelm with all business info unless requested

Response:"""

        return await self._generate_ai_response(
            prompt, session_id, message, ChatType.GLOBAL, context
        )

    async def _handle_dedicated_chat(
        self, 
        message: str, 
        session_id: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle dedicated chat for a specific business."""
        
        business_id = context.get("business_id") or context.get("selected_business")
        if not business_id:
            return {"message": "Business not specified for dedicated chat", "success": False}
        
        # Get specific business
        business = self.db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return {"message": "Business not found", "success": False}
        
        # Get full menu for this business
        menu_items = (
            self.db.query(MenuItem)
            .filter(MenuItem.business_id == business_id, MenuItem.is_available == True)
            .limit(15)  # More items for dedicated chat
            .all()
        )
        
        # Get table info if applicable
        table_info = ""
        table_id = context.get("table_id")
        if table_id:
            table = self.db.query(Table).filter(Table.id == table_id).first()
            if table:
                table_info = f"TABLE: {table.table_number}\n"
        
        # Build business context
        business_context = {
            "id": business.id,
            "name": business.name,
            "category": str(business.category) if business.category else None,
            "description": business.description,
            "menu": [
                {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.base_price or 0)
                }
                for item in menu_items
            ]
        }
        
        # Get conversation history and session context
        history = self._get_conversation_history(session_id)
        session_context = self._get_session_context(session_id)
        
        # Extract customer info
        extracted_info = self._extract_customer_info(message)
        if extracted_info:
            self._update_session_context(session_id, extracted_info)
            session_context = self._get_session_context(session_id)
        
        # Create dedicated business prompt
        prompt = f"""You are X-SevenAI assistant for {business.name}.

BUSINESS DETAILS:
{json.dumps(business_context, separators=(',', ':'))}

{table_info}CONVERSATION HISTORY:
{chr(10).join(history[-self.max_history:])}

CURRENT USER MESSAGE: {message}

{self._get_customer_context_text(session_context)}

DEDICATED BUSINESS GUIDELINES:
- You represent {business.name} specifically
- Help customers with menu questions, orders, and bookings
- Provide detailed information about menu items and prices
- For orders: collect items, quantities, and customer details (name required, phone optional)
- For bookings: collect date, time, party size, and customer details
- After getting customer details, format orders as: ORDER: {business_id}|items|customer_name|customer_phone
- After getting customer details, format bookings as: BOOKING: {business_id}|name|phone|date|time|party_size
- Be friendly and knowledgeable about {business.name}
- Upsell appropriately but not aggressively

Response:"""

        return await self._generate_ai_response(
            prompt, session_id, message, ChatType.DEDICATED, context, business_id
        )

    async def _handle_dashboard_chat(
        self, 
        message: str, 
        session_id: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle dashboard management chat for business owners/staff."""
        
        business_id = context.get("business_id")
        if not business_id:
            return {"message": "Business access required for dashboard", "success": False}
        
        # Get business details
        business = self.db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return {"message": "Business not found", "success": False}
        
        # Get business data for management
        menu_items = self.db.query(MenuItem).filter(MenuItem.business_id == business_id).all()
        recent_orders = (
            self.db.query(Order)
            .filter(Order.business_id == business_id)
            .order_by(Order.created_at.desc())
            .limit(10)
            .all()
        )
        
        # Build management context
        management_context = {
            "business": {
                "id": business.id,
                "name": business.name,
                "status": "active" if business.is_active else "inactive"
            },
            "menu_stats": {
                "total_items": len(menu_items),
                "available_items": len([item for item in menu_items if item.is_available]),
                "low_stock_items": len([item for item in menu_items if getattr(item, 'stock_quantity', 0) <= getattr(item, 'min_stock_threshold', 5)])
            },
            "order_stats": {
                "recent_orders": len(recent_orders),
                "pending_orders": len([order for order in recent_orders if order.status.value == "pending"])
            }
        }
        
        # Get conversation history
        history = self._get_conversation_history(session_id)
        
        # Create dashboard management prompt
        prompt = f"""You are the AI management assistant for {business.name}.

BUSINESS MANAGEMENT CONTEXT:
{json.dumps(management_context, separators=(',', ':'))}

CONVERSATION HISTORY:
{chr(10).join(history[-self.max_history:])}

CURRENT MANAGEMENT REQUEST: {message}

DASHBOARD ASSISTANT GUIDELINES:
- You help manage {business.name} operations
- Provide insights on inventory, orders, staff, and analytics
- Answer questions about business performance and status
- Suggest improvements and optimizations
- Help with menu management, pricing, and operations
- For inventory alerts: "INVENTORY_ALERT: item_name|current_stock|threshold"
- For order updates: "ORDER_UPDATE: order_id|new_status|notes"
- Be professional, data-driven, and actionable
- Focus on business efficiency and growth

AVAILABLE MANAGEMENT FUNCTIONS:
- Check inventory status and alerts
- Review order status and analytics  
- Monitor business performance metrics
- Manage menu items and pricing
- Staff scheduling and task management
- Customer analytics and feedback

Response:"""

        return await self._generate_ai_response(
            prompt, session_id, message, ChatType.DASHBOARD, context, business_id
        )

    async def _generate_ai_response(
        self,
        prompt: str,
        session_id: str,
        message: str,
        chat_type: ChatType,
        context: Dict[str, Any],
        business_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate AI response using Groq."""
        
        if not self.client:
            fallback_msg = "AI is not configured. Please set GROQ_API_KEY to enable intelligent responses."
            await self._save_messages(business_id or 0, session_id, message, fallback_msg)
            return {"message": fallback_msg, "success": True, "chat_type": chat_type.value}
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=self.max_tokens,
                timeout=90,
            )
            
            ai_response = response.choices[0].message.content if response.choices[0].message.content else ""
            
            # Handle special actions based on chat type
            if chat_type == ChatType.DEDICATED:
                ai_response = await self._handle_dedicated_actions(ai_response, session_id, business_id)
            elif chat_type == ChatType.DASHBOARD:
                ai_response = await self._handle_dashboard_actions(ai_response, business_id)
            
            # Clean response
            ai_response = self._clean_response(ai_response)
            
            # Save conversation
            await self._save_messages(business_id or 0, session_id, message, ai_response)
            
            return {
                "message": ai_response,
                "success": True,
                "chat_type": chat_type.value,
                "session_id": session_id
            }
            
        except Exception as e:
            error_msg = "I'm having trouble right now. Please try again."
            await self._save_messages(business_id or 0, session_id, message, error_msg)
            return {
                "message": error_msg,
                "success": False,
                "error": str(e),
                "chat_type": chat_type.value
            }

    async def _handle_dedicated_actions(self, ai_response: str, session_id: str, business_id: Optional[int]) -> str:
        """Handle booking and order actions for dedicated chat."""
        
        if "BOOKING:" in ai_response:
            booking_result = await self._handle_booking(ai_response)
            if booking_result:
                ai_response = ai_response.replace(
                    "BOOKING:", "✅ Booking confirmed! "
                ) + f"\n\nConfirmation: {booking_result['confirmation']}"
        
        elif "ORDER:" in ai_response:
            order_result = await self._handle_order(ai_response)
            if order_result:
                ai_response = ai_response.replace(
                    "ORDER:", "✅ Order placed! "
                ) + f"\n\nOrder #: {order_result['order_number']}"
        
        return ai_response

    async def _handle_dashboard_actions(self, ai_response: str, business_id: Optional[int]) -> str:
        """Handle management actions for dashboard chat."""
        
        if "INVENTORY_ALERT:" in ai_response:
            # Handle inventory alerts
            try:
                alert_line = [l for l in ai_response.split("\n") if "INVENTORY_ALERT:" in l][0]
                # Process inventory alert
                ai_response = ai_response.replace("INVENTORY_ALERT:", "📦 Inventory Alert: ")
            except:
                pass
        
        elif "ORDER_UPDATE:" in ai_response:
            # Handle order status updates  
            try:
                update_line = [l for l in ai_response.split("\n") if "ORDER_UPDATE:" in l][0]
                # Process order update
                ai_response = ai_response.replace("ORDER_UPDATE:", "📋 Order Updated: ")
            except:
                pass
        
        return ai_response

    # ... (Include all the helper methods from your original SimpleAIHandler)
    
    def _get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get or create session context."""
        if session_id not in _SESSION_CONTEXTS:
            _SESSION_CONTEXTS[session_id] = {
                "customer_name": None,
                "customer_phone": None,
                "booking_info": {},
                "order_info": {},
                "extracted_entities": set(),
            }
        return _SESSION_CONTEXTS[session_id]
    
    def _update_session_context(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Update session context."""
        context = self._get_session_context(session_id)
        for key, value in updates.items():
            if key == "extracted_entities" and isinstance(value, (list, set)):
                if not isinstance(context["extracted_entities"], set):
                    context["extracted_entities"] = set()
                context["extracted_entities"].update(value)
            else:
                context[key] = value
    
    def _get_conversation_history(self, session_id: str) -> List[str]:
        """Get conversation history for session."""
        history = (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(self.max_history)
            .all()
        )
        
        chat_history = []
        for msg in reversed(history):
            role = "assistant" if msg.sender_type == "bot" else "user"
            chat_history.append(f"{role}: {msg.content}")
        
        return chat_history
    
    def _get_customer_context_text(self, session_context: Dict[str, Any]) -> str:
        """Format customer context for prompt."""
        context_text = ""
        if session_context.get("customer_name"):
            context_text += f"CUSTOMER NAME: {session_context['customer_name']}\n"
        if session_context.get("customer_phone"):
            context_text += f"CUSTOMER PHONE: {session_context['customer_phone']}\n"
        return context_text
    
    def _extract_customer_info(self, text: str) -> Dict[str, Any]:
        """Extract customer information from text."""
        result = {}
        extracted_entities = set()
        
        # Extract name patterns
        name_patterns = [
            r"(?:my name is|i am|i'm|this is) ([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})\b",
            r"(?:name[:\s]+)([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})\b",
        ]
        
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
                if len(name) > 2:
                    result["customer_name"] = name
                    extracted_entities.add("customer_name")
                    break
        
        # Extract phone patterns
        phone_patterns = [
            r"(?:phone|number|tel|contact)[:\s]*(\+?\d[\d\s\-\(\)]{7,}\d)\b",
            r"(\+?\d{1,3}[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4})"
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, text, re.IGNORECASE)
            if phone_match:
                phone = phone_match.group(1).strip()
                phone = re.sub(r'[\s\(\)\-]+', '', phone)
                if len(phone) >= 7:
                    result["customer_phone"] = phone
                    extracted_entities.add("customer_phone")
                    break
        
        if extracted_entities:
            result["extracted_entities"] = extracted_entities
        
        return result
    
    async def _handle_booking(self, ai_response: str) -> Optional[Dict[str, Any]]:
        """Handle booking creation."""
        try:
            booking_line = [l for l in ai_response.split("\n") if "BOOKING:" in l][0]
            parts = booking_line.replace("BOOKING:", "").strip().split("|")
            
            if len(parts) >= 6:
                business_id, name, phone, date, time, party_size = parts[:6]
                booking_id = f"BK-{business_id}-{int(datetime.now().timestamp())}"
                confirmation = f"CONF-{booking_id[-6:]}"
                
                return {
                    "booking_id": booking_id,
                    "confirmation": confirmation,
                    "business_id": business_id,
                    "customer_name": name,
                    "customer_phone": phone,
                    "date": date,
                    "time": time,
                    "party_size": party_size,
                }
        except:
            pass
        return None
    
    async def _handle_order(self, ai_response: str) -> Optional[Dict[str, Any]]:
        """Handle order creation."""
        try:
            order_line = [l for l in ai_response.split("\n") if "ORDER:" in l][0]
            parts = order_line.replace("ORDER:", "").strip().split("|")
            
            if len(parts) >= 4:
                business_id, items, customer_name, customer_phone = parts[:4]
                order_id = f"ORD-{business_id}-{int(datetime.now().timestamp())}"
                order_number = f"#{order_id[-6:]}"
                
                return {
                    "order_id": order_id,
                    "order_number": order_number,
                    "business_id": business_id,
                    "items": items,
                    "customer_name": customer_name,
                    "customer_phone": customer_phone,
                }
        except:
            pass
        return None
    
    def _clean_response(self, text: str) -> str:
        """Clean AI response to remove internal thinking."""
        if not text:
            return text
        
        # Remove XML-like thinking blocks
        text = re.sub(r'<(thinking|reasoning|internal).*?>.*?</\1>', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove common internal thinking patterns
        lines = text.split('\n')
        cleaned_lines = []
        
        skip_patterns = [
            'okay, ', 'let me ', 'i need to ', 'first, ', 'next, ', 'finally, ',
            'thinking:', 'reasoning:', 'internal:', 'analysis:',
            'based on', 'looking at', 'checking', 'reviewing'
        ]
        
        for line in lines:
            line_stripped = line.strip().lower()
            if any(line_stripped.startswith(pattern) for pattern in skip_patterns):
                continue
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines).strip()
        result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
        
        return result
    
    async def _save_messages(
        self, business_id: int, session_id: str, user_message: str, ai_response: str
    ) -> None:
        """Save conversation messages."""
        try:
            user_msg = Message(
                business_id=business_id,
                session_id=session_id,
                sender_type="customer",
                content=user_message,
                message_type="text",
                ai_model_used=self.model,
            )
            self.db.add(user_msg)
            
            ai_msg = Message(
                business_id=business_id,
                session_id=session_id,
                sender_type="bot",
                content=ai_response,
                message_type="text",
                ai_model_used=self.model,
            )
            self.db.add(ai_msg)
            
            self.db.commit()
        except Exception:
            self.db.rollback()