"""Universal Bot

Entry point for global chat across all businesses. It routes the user's request
and delegates to ConversationHandler when a business is selected or can be
inferred.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
import os
import time
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Business, MenuItem
from app.services.ai.conversation_handler import ConversationHandler


class UniversalBot:
    def __init__(self, db: Session):
        self.db = db
        self.conversation = ConversationHandler(db)
        # In-memory session store for lightweight state (ok for dev)
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        return self._sessions.setdefault(session_id, {"stage": "initial", "last_seen_ts": time.time()})

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        return dict(self._get_session(session_id))

    async def process_message(
        self,
        *,
        session_id: str,
        message: str,
        channel: str,
        language: Optional[str] = "en",
        phone_number: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = self._get_session(session_id)
        now_ts = time.time()
        # Determine staleness window (default 3 hours)
        try:
            stale_min = int(os.getenv("SESSION_STALE_MINUTES", "180"))
        except Exception:
            stale_min = 180
        is_stale = (now_ts - float(session.get("last_seen_ts", now_ts))) > (stale_min * 60)
        if is_stale:
            # Reset selection and transient history so old context doesn't leak into new chats
            session.pop("selected_business", None)
            session["history"] = []
            session["stage"] = "initial"
        session["last_seen_ts"] = now_ts
        ctx = dict(context or {})

        # If context selects a business, lock it into session
        selected_business = ctx.get("selected_business") or ctx.get("business_id")
        if selected_business:
            session["selected_business"] = selected_business
            session["stage"] = "business_selected"

        # Maintain lightweight in-memory conversation history (last 20 turns)
        history: List[Dict[str, str]] = session.setdefault("history", [])
        try:
            history.append({"role": "user", "content": message or ""})
            if len(history) > 20:
                session["history"] = history[-20:]
                history = session["history"]
        except Exception:
            # Never fail due to history issues
            session.setdefault("history", [])

        # If no business yet, try to infer from message
        if not session.get("selected_business"):
            inferred = self._infer_business_from_text(message)
            if inferred:
                session["selected_business"] = inferred
                session["stage"] = "business_selected"

        # Delegate to conversation handler
        response = await self.conversation.process_message(
            session_id=session_id,
            message=message,
            channel=channel,
            context={**ctx, **session},
            language=language,
            phone_number=phone_number,
            location=location,
        )

        # Append assistant reply to history for continuity
        try:
            bot_text = response.get("message", "")
            if bot_text:
                session["history"].append({"role": "assistant", "content": bot_text})
                if len(session["history"]) > 20:
                    session["history"] = session["history"][-20:]
        except Exception:
            pass

        return response

    # --- Helpers ---
    def _infer_business_from_text(self, text: str) -> Optional[int]:
        if not text:
            return None
        term = text.strip()
        like = f"%{term}%"
        try:
            match = (
                self.db.query(Business)
                .filter(Business.is_active == True, or_(Business.name.ilike(like), Business.description.ilike(like)))
                .order_by(Business.name.asc())
                .first()
            )
        except Exception:
            # If DB isn't ready or query fails, don't crash the chat
            return None
        if match:
            return match.id
        # Try to infer from an item name (map to its business)
        try:
            item = (
                self.db.query(MenuItem)
                .filter(MenuItem.is_available == True, or_(MenuItem.name.ilike(like), MenuItem.description.ilike(like)))
                .first()
            )
            return item.business_id if item else None
        except Exception:
            return None
