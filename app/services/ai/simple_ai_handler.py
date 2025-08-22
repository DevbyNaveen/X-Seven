"""
Simple AI Handler that provides chat, booking, and order handling
with minimal complexity, adapted to this codebase.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

try:
    # groq python SDK
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover - allow runtime import error handling
    Groq = None  # type: ignore

from app.models import Business, MenuItem, Message
from app.config.settings import settings


class SimpleAIHandler:
    """Lightweight AI handler for chat, bookings, and orders."""

    def __init__(self, db: Session):
        self.db = db
        self.model = settings.GROQ_MODEL or "llama-3.1-8b-instant"
        self.max_tokens = getattr(settings, "GROQ_MAX_TOKENS", 500) or 500
        self.max_history = getattr(settings, "GROQ_MAX_HISTORY", 6) or 6
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
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Handle a chat message and return AI response and metadata."""
        context = context or {}

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

        # Build quick business context list
        max_biz = getattr(settings, "GROQ_MAX_BUSINESSES", 8) or 8
        business_list = []
        for biz in businesses[:max_biz]:
            items = (
                self.db.query(MenuItem)
                .filter(
                    MenuItem.business_id == biz.id,
                    MenuItem.is_available == True,  # noqa: E712
                )
                .limit(3)
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

        prompt = (
            f"You are X-SevenAI, a helpful assistant for local businesses.\n\n"
            f"AVAILABLE BUSINESSES:\n{json.dumps(business_list, indent=2)}\n\n"
            f"CONVERSATION HISTORY:\n{chr(10).join(chat_history[-(self.max_history + 1):])}\n\n"
            f"CURRENT USER MESSAGE: {message}\n\n"
            "INSTRUCTIONS:\n"
            "- Help users find businesses, make reservations, and place orders\n"
            "- If they want food, suggest from available restaurants\n"
            "- If they want to book, ask for: name, phone, date, time, party size\n"
            "- If they want to order, show menu items and prices\n"
            "- When you have booking details, format like: BOOKING: business_id|name|phone|date|time|party_size\n"
            "- When you have order details, format like: ORDER: business_id|items|customer_name|customer_phone\n"
            "- Be natural and helpful\n\n"
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=self.max_tokens,
            )
            ai_response = response.choices[0].message.content  # type: ignore[attr-defined]

            # Check for actions
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

            await self._save_messages(selected_business_id, session_id, message, ai_response)
            return {"message": ai_response, "success": True, "session_id": session_id}
        except Exception as e:
            err = str(e)
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
