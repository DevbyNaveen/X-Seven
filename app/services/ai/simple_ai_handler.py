"""
Simple AI Handler that provides chat, booking, and order handling
with minimal complexity, adapted to this codebase.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Set

from sqlalchemy.orm import Session

try:
    # groq python SDK
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover - allow runtime import error handling
    Groq = None  # type: ignore

from app.models import Business, MenuItem, Message
from app.config.settings import settings

# Global session context store
_SESSION_CONTEXTS: Dict[str, Dict[str, Any]] = {}


class SimpleAIHandler:
    """Lightweight AI handler for chat, bookings, and orders."""

    def __init__(self, db: Session):
        self.db = db
        self.model = settings.GROQ_MODEL or "llama-3.1-8b-instant"
        # Increase default max tokens to reduce risk of truncated responses
        self.max_tokens = getattr(settings, "GROQ_MAX_TOKENS", 1200) or 1200
        self.max_history = getattr(settings, "GROQ_MAX_HISTORY", 6) or 6
        self.client = None
        if settings.GROQ_API_KEY and Groq is not None:
            try:
                self.client = Groq(api_key=settings.GROQ_API_KEY)
            except Exception:
                self.client = None
        
    def _get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get or create session context for the given session ID."""
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
        """Update session context with new information."""
        context = self._get_session_context(session_id)
        for key, value in updates.items():
            if key == "extracted_entities" and isinstance(value, (list, set)):
                # Merge sets for extracted entities
                if not isinstance(context["extracted_entities"], set):
                    context["extracted_entities"] = set()
                context["extracted_entities"].update(value)
            else:
                context[key] = value

    async def chat(
        self,
        message: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Handle a chat message and return AI response and metadata."""
        context = context or {}
        
        # Get persistent session context
        session_context = self._get_session_context(session_id)
        
        # Extract entities from the current message
        extracted_info = self._extract_customer_info(message)
        if extracted_info:
            self._update_session_context(session_id, extracted_info)

        # Resolve businesses
        businesses: List[Business] = (
            self.db.query(Business).filter(Business.is_active == True).all()  # noqa: E712
        )
        if not businesses:
            return {
                "message": "No active businesses configured yet.",
                "success": False,
                "session_id": session_id,
            }

        # Pick selected business for message saving (Message.business_id is required)
        selected_business_id = (
            context.get("selected_business")
            or context.get("business_id")
            or businesses[0].id
        )

        # Conversation history (last N messages for this session)
        history: List[Message] = (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(self.max_history)
            .all()
        )

        # Build quick business context list - prioritize relevant businesses
        max_biz = getattr(settings, "GROQ_MAX_BUSINESSES", 5) or 5  # Reduce to 5 for better focus
        business_list = []
        
        # If there's a selected business, put it first
        selected_biz = None
        if selected_business_id:
            selected_biz = next((biz for biz in businesses if biz.id == selected_business_id), None)
        
        # Add selected business first if it exists
        if selected_biz:
            items = (
                self.db.query(MenuItem)
                .filter(
                    MenuItem.business_id == selected_biz.id,
                    MenuItem.is_available == True,  # noqa: E712
                )
                .limit(5)  # Show more items for selected business
                .all()
            )
            business_list.append(
                {
                    "id": selected_biz.id,
                    "name": selected_biz.name,
                    "category": str(selected_biz.category) if selected_biz.category is not None else None,
                    "description": selected_biz.description,
                    "sample_menu": [
                        {"name": item.name, "price": float(item.base_price or 0)}
                        for item in items
                    ],
                }
            )
        
        # Add other businesses (limit to max_biz total)
        for biz in businesses:
            # Skip if we've reached the limit or if this is the selected business (already added)
            if len(business_list) >= max_biz or (selected_biz and biz.id == selected_biz.id):
                continue
                
            items = (
                self.db.query(MenuItem)
                .filter(
                    MenuItem.business_id == biz.id,
                    MenuItem.is_available == True,  # noqa: E712
                )
                .limit(2)  # Show fewer items for other businesses
                .all()
            )
            business_list.append(
                {
                    "id": biz.id,
                    "name": biz.name,
                    "category": str(biz.category) if biz.category is not None else None,
                    "description": biz.description,
                    "sample_menu": [
                        {"name": item.name, "price": float(item.base_price or 0)}
                        for item in items
                    ],
                }
            )

        # Build conversation context
        chat_history: List[str] = []
        for msg in reversed(history):
            role = "assistant" if msg.sender_type == "bot" else "user"
            chat_history.append(f"{role}: {msg.content}")
            
            # Extract customer info from previous messages if not already known
            if role == "user" and (not session_context.get("customer_name") or not session_context.get("customer_phone")):
                extracted_info = self._extract_customer_info(msg.content)
                if extracted_info:
                    self._update_session_context(session_id, extracted_info)

        # Add session context to the prompt
        customer_context = ""
        if session_context.get("customer_name"):
            customer_context += f"CUSTOMER NAME: {session_context['customer_name']}\n"
        if session_context.get("customer_phone"):
            customer_context += f"CUSTOMER PHONE: {session_context['customer_phone']}\n"
        
        prompt = (
            f"You are X-SevenAI, a natural and conversational AI assistant for local businesses.\n\n"
            f"AVAILABLE BUSINESSES:\n{json.dumps(business_list, separators=(',', ':'))}\n\n"
            f"CONVERSATION HISTORY:\n{chr(10).join(chat_history[-(self.max_history + 1):])}"
            f"\n\nCURRENT USER MESSAGE: {message}\n\n"
            f"{customer_context}\n"
            "RESPONSE GUIDELINES:\n"
            "- Respond naturally to the user's actual message - don't dump menus unless specifically asked\n"
            "- For simple greetings like 'hey', respond conversationally without over-explaining\n"
            "- Only provide business/menu information when the user shows interest or asks for it\n"
            "- Don't assume the user wants to see all menus - that's overwhelming\n"
            "- Be concise, friendly, and helpful\n"
            "- Act like a smart human assistant, not a menu-reading robot\n"
            "- Wait for specific requests before providing detailed information\n"
            "- Write in complete, well-structured sentences\n"
            "- Avoid run-on sentences - keep responses clear and segmented\n"
            "- Use proper paragraph breaks for readability\n"
            "- When making a booking, ALWAYS ask for the customer's name (mandatory) and phone number (optional) ONLY IF NOT ALREADY PROVIDED\n"
            "- If customer name is already known, use it and don't ask again\n"
            "- Only after getting customer details, format booking like: BOOKING: business_id|name|phone|date|time|party_size\n"
            "- When making an order, ALWAYS ask for the customer's name (mandatory) and phone number (optional) ONLY IF NOT ALREADY PROVIDED\n"
            "- Only after getting customer details, format order like: ORDER: business_id|items|customer_name|customer_phone\n"
            "- Include customer details in the invoice for business dashboard visibility\n\n"
            "Response:"
        )

        # Fallback if Groq is not configured
        if not self.client:
            ai_response = (
                "AI is not configured (missing GROQ_API_KEY). "
                "Please set it to enable intelligent responses."
            )
            await self._save_messages(selected_business_id, session_id, message, ai_response)
            return {"message": ai_response, "success": True, "session_id": session_id}

        try:
            # Increase timeout to 90 seconds for longer responses
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=self.max_tokens,
                timeout=90,  # 90 second timeout
            )
            ai_response = response.choices[0].message.content if response.choices[0].message.content else ""

            # Extract any new customer info from the AI response
            extracted_info = self._extract_customer_info(ai_response)
            if extracted_info:
                self._update_session_context(session_id, extracted_info)
                
            # Check for actions
            if "BOOKING:" in ai_response:
                # Use session context for booking if available
                if session_context.get("customer_name"):
                    # Replace any placeholder with actual stored customer name
                    ai_response = re.sub(r'BOOKING:\s*([^|]+)\|([^|]+)', 
                                        f'BOOKING: \1|{session_context["customer_name"]}', 
                                        ai_response)
                    
                booking_result = await self._handle_booking(ai_response)
                if booking_result:
                    # Update session context with booking info
                    self._update_session_context(session_id, {"booking_info": booking_result})
                    ai_response = ai_response.replace(
                        "BOOKING:", "✅ Booking confirmed! "
                    ) + f"\n\nConfirmation: {booking_result['confirmation']}"
            elif "ORDER:" in ai_response:
                # Use session context for order if available
                if session_context.get("customer_name"):
                    # Replace any placeholder with actual stored customer name
                    ai_response = re.sub(r'ORDER:\s*([^|]+)\|([^|]+)\|([^|]+)', 
                                        f'ORDER: \1|\2|{session_context["customer_name"]}', 
                                        ai_response)
                    
                order_result = await self._handle_order(ai_response)
                if order_result:
                    # Update session context with order info
                    self._update_session_context(session_id, {"order_info": order_result})
                    ai_response = ai_response.replace(
                        "ORDER:", "✅ Order placed! "
                    ) + f"\n\nOrder #: {order_result['order_number']}"

            # Clean up the response to remove any internal thinking
            ai_response = self._clean_response(ai_response)

            await self._save_messages(selected_business_id, session_id, message, ai_response)
            return {"message": ai_response, "success": True, "session_id": session_id}
        except Exception as e:
            err = str(e)
            print(f"AI Error for session {session_id}: {err}")
            fallback = "I'm having trouble right now. Please try again."
            await self._save_messages(selected_business_id, session_id, message, fallback)
            return {"message": fallback, "success": False, "error": err, "session_id": session_id}

    async def _handle_booking(self, ai_response: str) -> Optional[Dict[str, Any]]:
        """Parse and return a booking result from AI response."""
        try:
            # Expect: BOOKING: business_id|name|phone|date|time|party_size
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
        except Exception:
            pass
        return None

    async def _handle_order(self, ai_response: str) -> Optional[Dict[str, Any]]:
        """Parse and return an order result from AI response."""
        try:
            # Expect: ORDER: business_id|items|customer_name|customer_phone
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
        except Exception:
            pass
        return None

    async def _save_messages(
        self, business_id: int, session_id: str, user_message: str, ai_response: str
    ) -> None:
        """Persist user and AI messages for the session."""
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
            # Don't raise to avoid breaking chat flow
            self.db.rollback()
            pass

    def _extract_customer_info(self, text: str) -> Dict[str, Any]:
        """Extract customer information from text."""
        result = {}
        extracted_entities = set()
        
        # Extract name
        name_patterns = [
            r"(?:my name is|i am|i'm|this is) ([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})\b",  # My name is John Smith
            r"(?:name[:\s]+)([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})\b",  # Name: John Smith
            r"^([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})$"  # Just "John Smith" on a line by itself
        ]
        
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
                if len(name) > 2:  # Avoid single letters or very short strings
                    result["customer_name"] = name
                    extracted_entities.add("customer_name")
                    break
        
        # Extract phone number
        phone_patterns = [
            r"(?:phone|number|tel|contact)[:\s]*(\+?\d[\d\s\-\(\)]{7,}\d)\b",  # Phone: +1 555-123-4567
            r"(\+?\d{1,3}[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4})"  # +1 (555) 123-4567 or similar
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, text, re.IGNORECASE)
            if phone_match:
                phone = phone_match.group(1).strip()
                # Clean up the phone number
                phone = re.sub(r'[\s\(\)\-]+', '', phone)
                if len(phone) >= 7:  # Minimum valid phone length
                    result["customer_phone"] = phone
                    extracted_entities.add("customer_phone")
                    break
        
        if extracted_entities:
            result["extracted_entities"] = extracted_entities
            
        return result

    def _clean_response(self, text: str) -> str:
        """Clean AI response to remove internal thinking and reasoning."""
        if not text:
            return text
        
        # Remove common patterns of internal thinking
        
        # Remove XML-like thinking blocks
        text = re.sub(r'<(thinking|reasoning|internal).*?>.*?</\1>', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove fenced code blocks with thinking labels
        text = re.sub(r'```(thinking|reasoning|internal).*?```', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Split into lines and filter
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_stripped = line.strip().lower()
            
            # Skip lines that start with problematic phrases
            skip_patterns = [
                'okay, ', 'let me ', 'i need to ', 'first, ', 'next, ', 'finally, ',
                'thinking:', 'reasoning:', 'internal:', 'analysis:',
                'based on', 'looking at', 'checking', 'reviewing'
            ]
            
            if any(line_stripped.startswith(pattern) for pattern in skip_patterns):
                continue
                
            # Skip lines with step-by-step thinking
            if re.match(r'^(step\s+\d+|\d+\.|\*\*\d+\*\*)\s*', line_stripped):
                continue
                
            cleaned_lines.append(line)
        
        # Join and clean up extra whitespace
        result = '\n'.join(cleaned_lines).strip()
        
        # Remove multiple consecutive empty lines
        result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
        
        return result
