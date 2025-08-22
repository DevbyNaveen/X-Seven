"""AI Conversation Handler

Coordinates intent detection, DB lookups, retrieval, and LLM (with graceful
fallback) to produce helpful, markdown-formatted chat responses.

This module is written to be self-contained and resilient:
- Works without API keys (falls back to heuristic responses)
- Uses DB search first; vector/RAG can be added later or enabled when ready
- Persists messages only when a concrete business_id is available
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import json
from dataclasses import dataclass
import re
import os
import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Business, MenuItem, Message
from app.config.settings import settings


# -------- Helpers --------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _md_list(items: List[str]) -> str:
    return "\n".join([f"- {it}" for it in items])


@dataclass
class AIResult:
    text: str
    model_used: Optional[str] = None


class ConversationHandler:
    """High-level orchestrator for a single message turn."""

    def __init__(self, db: Session):
        self.db = db

    # -------- Public API --------
    async def process_message(
        self,
        *,
        session_id: str,
        message: str,
        channel: str = "chat",
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = "en",
        phone_number: Optional[str] = None,
        location: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a user message and return a structured response.

        Returns: {"message": str, "suggested_actions": List[Dict], "metadata": Dict}
        """
        started = _now_ms()
        ctx = context or {}
        selected_business_id: Optional[int] = ctx.get("selected_business") or ctx.get("business_id")
        user_text = (message or "").strip()

        # Optional heuristic intent just for metadata; reply will be LLM-generated
        intent = self._detect_intent(user_text)

        # Build candidates if business not fixed
        candidates: List[Tuple[Business, float]] = []
        if not selected_business_id and user_text:
            candidates = self._find_candidate_businesses(user_text)

        # LLM-first conversational response
        reply, actions, meta = self._ai_generate_response(
            session_id=session_id,
            user_text=user_text,
            selected_business_id=selected_business_id,
            candidates=candidates,
            language=language or "en",
            ctx_history=ctx.get("history"),
        )

        # Persist messages only when business is known (schema requires business_id)
        model_used = meta.get("ai_model_used")
        if selected_business_id:
            try:
                self._save_messages(
                    session_id=session_id,
                    business_id=selected_business_id,
                    user_text=user_text,
                    bot_text=reply,
                    intent=intent,
                    model_used=model_used,
                    duration_ms=_now_ms() - started,
                )
            except Exception:
                # Don't block chat on persistence failure
                pass

        return {
            "message": reply,
            "suggested_actions": actions,
            "metadata": {
                **meta,
                "intent": intent,
                "language": language,
                "business_id": selected_business_id,
            },
        }

    # -------- Intent + Flows --------
    def _detect_intent(self, text: str) -> str:
        t = text.lower()
        # Very fast keyword heuristics
        if any(w in t for w in ["menu", "eat", "food", "drink", "order", "burger", "pizza", "coffee"]):
            if "order" in t or "buy" in t:
                return "order_inquiry"
            return "menu_inquiry"
        if any(w in t for w in ["book", "reserve", "reservation", "appointment", "schedule"]):
            return "reservation_inquiry"
        if any(w in t for w in ["service", "services", "what do you have", "what do u have", "offer"]):
            return "list_services"
        if any(w in t for w in ["category", "categories", "businesses"]):
            return "list_categories"
        if any(w in t for w in ["help", "hi", "hello", "start"]):
            return "greeting"
        return "general"

    def _handle_global_flow(
        self,
        user_text: str,
        intent: str,
        candidates: List[Tuple[Business, float]],
        language: Optional[str],
    ) -> Tuple[str, List[Dict[str, str]], Dict[str, Any]]:
        # Deprecated in LLM-first mode; kept for compatibility if needed elsewhere.
        actions: List[Dict[str, str]] = []
        meta: Dict[str, Any] = {"stage": "global", "deprecated": True}
        return user_text or "How can I help you today?", actions, meta

    def _handle_business_flow(
        self,
        business_id: int,
        user_text: str,
        intent: str,
        language: Optional[str],
    ) -> Tuple[str, List[Dict[str, str]], Dict[str, Any]]:
        actions: List[Dict[str, str]] = []
        meta: Dict[str, Any] = {"stage": "business"}

        business = self.db.query(Business).filter(Business.id == business_id).first()
        if not business:
            return (
                "I couldn't find that business. You can ask me to search for another.",
                actions,
                meta,
            )

        # Deprecated in LLM-first mode; kept for compatibility if needed elsewhere.
        llm = self._call_llm(
            prompt=self._build_llm_prompt(business, user_text),
            language=language or "en",
        )
        return llm.text, actions, {**meta, "ai_model_used": llm.model_used, "deprecated": True}

    # -------- DB helpers --------
    def _find_candidate_businesses(self, text: str) -> List[Tuple[Business, float]]:
        # Simple fuzzy search across name/description
        term = text.strip()
        if not term:
            return []
        like = f"%{term}%"
        try:
            matches = self.db.query(Business).filter(
                Business.is_active == True,
                or_(Business.name.ilike(like), Business.description.ilike(like)),
            ).limit(10).all()
            return [(m, 1.0) for m in matches]
        except Exception:
            # If DB isn't ready, don't crash the chat
            return []

    def _search_menu_items(
        self, text: str, *, business_id: Optional[int], limit: int = 5
    ) -> List[MenuItem]:
        if not text:
            return []
        tokens = [t for t in re.split(r"\W+", text.lower()) if t]
        if not tokens:
            return []
        ors = []
        for tok in set(tokens):
            like = f"%{tok}%"
            ors.append(MenuItem.name.ilike(like))
            ors.append(MenuItem.description.ilike(like))
        q = self.db.query(MenuItem).filter(MenuItem.is_available == True, or_(*ors))
        if business_id:
            q = q.filter(MenuItem.business_id == business_id)
        return q.limit(limit).all()

    def _save_messages(
        self,
        *,
        session_id: str,
        business_id: int,
        user_text: str,
        bot_text: str,
        intent: str,
        model_used: Optional[str],
        duration_ms: int,
    ) -> None:
        # User message
        user_msg = Message(
            session_id=session_id,
            business_id=business_id,
            sender_type="customer",
            content=user_text,
            message_type="text",
            intent_detected=intent,
            ai_model_used=None,
            response_time_ms=None,
            extra_data={},
        )
        self.db.add(user_msg)

        # Bot message
        bot_msg = Message(
            session_id=session_id,
            business_id=business_id,
            sender_type="bot",
            content=bot_text,
            message_type="text",
            intent_detected=intent,
            ai_model_used=model_used,
            response_time_ms=duration_ms,
            extra_data={},
        )
        self.db.add(bot_msg)

        self.db.commit()

    # -------- LLM-first prompt building and parsing --------
    def _ai_generate_response(
        self,
        *,
        session_id: str,
        user_text: str,
        selected_business_id: Optional[int],
        candidates: List[Tuple[Business, float]],
        language: str,
        ctx_history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, List[Dict[str, str]], Dict[str, Any]]:
        # Build lightweight context
        biz: Optional[Business] = None
        if selected_business_id:
            try:
                biz = self.db.query(Business).filter(Business.id == selected_business_id).first()
            except Exception:
                # If DB isn't ready or query fails, proceed without business context
                biz = None

        # Conversation history
        # Prefer in-memory session history from context when available; otherwise fall back to DB (last 10)
        history: List[Dict[str, str]] = []
        if ctx_history and isinstance(ctx_history, list):
            # Keep last 20 from session memory
            try:
                history = [
                    {"role": (h.get("role") or "user"), "content": h.get("content") or ""}
                    for h in ctx_history[-20:]
                    if isinstance(h, dict)
                ]
            except Exception:
                history = []
        if not history:
            try:
                # Limit by recent time window to avoid pulling in yesterday's chat
                max_age_min = int(os.getenv("CHAT_HISTORY_MAX_AGE_MINUTES", "180"))  # default 3 hours
                cutoff_dt = datetime.utcnow() - timedelta(minutes=max_age_min)
                q = self.db.query(Message).filter(
                    Message.session_id == session_id,
                    Message.created_at >= cutoff_dt,
                )
                if selected_business_id:
                    q = q.filter(Message.business_id == selected_business_id)
                q = q.order_by(Message.created_at.desc()).limit(10)
                rows = list(reversed(q.all()))
                for r in rows:
                    role = "assistant" if r.sender_type == "bot" else "user"
                    history.append({"role": role, "content": r.content or ""})
            except Exception:
                pass

        # Candidate businesses context
        cand_ctx = [
            {"id": b.id, "name": b.name, "description": b.description}
            for (b, _score) in candidates[:5]
        ]

        # Relevant items context (limit for token budget)
        items_ctx: List[Dict[str, Any]] = []
        try:
            if selected_business_id:
                items = self._search_menu_items(user_text, business_id=selected_business_id, limit=8)
                if not items:
                    items = (
                        self.db.query(MenuItem)
                        .filter(MenuItem.business_id == selected_business_id, MenuItem.is_available == True)
                        .order_by(MenuItem.display_order)
                        .limit(8)
                        .all()
                    )
            else:
                items = self._search_menu_items(user_text, business_id=None, limit=6)
            for it in items:
                items_ctx.append({
                    "id": it.id,
                    "name": it.name,
                    "price": float(it.base_price) if it.base_price is not None else None,
                    "business_id": it.business_id,
                })
        except Exception:
            pass

        # Build prompt
        prompt = self._build_conversational_prompt(
            language=language,
            user_text=user_text,
            history=history,
            business=biz,
            candidates=cand_ctx,
            items=items_ctx,
        )

        llm = self._call_llm(prompt=prompt, language=language)
        text, actions = self._parse_llm_output(llm.text)

        # Deterministic fallbacks and sensible defaults
        # 1) Always provide default quick actions if the model didn't include any
        if selected_business_id:
            default_actions: List[Dict[str, str]] = [
                {"id": "view-menu", "title": "View Menu"},
                {"id": "start-order", "title": "Start Order"},
                {"id": "make-reservation", "title": "Make Reservation"},
            ]
        else:
            default_actions = [
                {"id": "choose-business", "title": "Choose a Business"},
                {"id": "view-menu", "title": "View Menu"},
            ]
        if not actions:
            actions = default_actions

        # 2) If LLM failed or returned empty, synthesize a helpful message from DB context
        if (not text) or text.lower().startswith("llm error"):
            lines: List[str] = []
            # Show available items for the selected business
            if selected_business_id and items_ctx:
                lines.append("Here are some items available now:")
                for it in items_ctx[:5]:
                    price_val = it.get("price")
                    price = f" - ${price_val:.2f}" if isinstance(price_val, (int, float)) else ""
                    lines.append(f"- {it['name']}{price}")
                text = "\n".join(lines) or "How can I help you today?"
            elif cand_ctx:
                lines.append("I can help with these businesses:")
                for c in cand_ctx[:5]:
                    lines.append(f"- {c['name']}")
                text = "\n".join(lines) + "\n\nPlease tell me which one you'd like."
            else:
                text = "How can I help you today?"

        meta: Dict[str, Any] = {"ai_model_used": llm.model_used, "stage": "llm_first"}
        return text, actions, meta

    def _build_conversational_prompt(
        self,
        *,
        language: str,
        user_text: str,
        history: List[Dict[str, str]],
        business: Optional[Business],
        candidates: List[Dict[str, Any]],
        items: List[Dict[str, Any]],
    ) -> str:
        ctx: Dict[str, Any] = {
            "language": language,
            "business": (
                {"id": business.id, "name": business.name, "description": business.description}
                if business
                else None
            ),
            "candidates": candidates,
            "items": items,
            "history": history,
        }
        instructions = (
            "You are X-SevenAI, a friendly, intelligent assistant for Business Automation.\n"
            "- Always reply in the user's language: " + language + ".\n"
            "- Be warm, concise, and proactive. Use a brief greeting when appropriate.\n"
            "- Use Markdown formatting (headings, bold, bullet lists) for readability.\n"
            "- Do NOT include any internal reasoning, chain-of-thought, system messages, debug logs, or analysis steps.\n"
            "  Do NOT output lines like 'Thinking:', 'Reasoning:', 'Analysis:', 'Debug:', 'Internal:'. Provide only the final helpful answer.\n"
            "- Maintain context and memory using the provided history (recent user/assistant turns).\n"
            "- Ask targeted clarifying questions if information is missing.\n"
            "- If no business is selected, recommend one from candidates and ask to confirm.\n"
            "- For orders or bookings, confirm details before finalizing (items, time, quantity).\n"
            "- End with next-step suggestions when helpful.\n\n"
            "If you want to expose quick actions, add an 'ACTIONS' section at the end with lines like:\n"
            "ACTIONS:\n- View Menu | view-menu\n- Start Order | start-order\n- Make Reservation | make-reservation\n"
            "Only include ACTIONS when clearly beneficial."
        )
        return (
            instructions
            + "\n\nContext JSON:\n"
            + json.dumps(ctx, ensure_ascii=False)
            + f"\n\nUser: {user_text}\nAssistant:"
        )

    def _parse_llm_output(self, text: str) -> Tuple[str, List[Dict[str, str]]]:
        actions: List[Dict[str, str]] = []
        if not text:
            return "", actions

        body = text.replace("\r\n", "\n")
        # Remove any explicit chain-of-thought or internal leakage before parsing actions
        body = self._clean_ai_output(body)

        # Find the ACTIONS header case-insensitively with optional spaces
        m = re.search(r"\n\s*actions\s*:\s*\n", body, flags=re.IGNORECASE)
        if not m:
            return body.strip(), actions

        main = body[: m.start()].strip()
        tail = body[m.end() :]

        # Collect lines belonging to the ACTIONS block
        lines: List[str] = []
        for line in tail.splitlines():
            # Stop if another SECTION HEADER appears (e.g., NEXT:, NOTES:)
            if re.match(r"^\s*[A-Z][A-Z _-]{2,}:\s*$", line):
                break
            # Ignore code-fence markers
            if re.match(r"^\s*```", line):
                continue
            # Keep the line (even if blank, we'll filter later)
            lines.append(line)

        # Normalize and parse potential action lines
        for raw in lines:
            s = raw.strip()
            if not s:
                continue
            # Strip common bullet/numbering prefixes
            s = s.lstrip(" -*•\t")
            s = re.sub(r"^\d+[\.)]\s*", "", s)

            if "|" in s:
                title, action_id = [x.strip() for x in s.split("|", 1)]
                if title and action_id:
                    actions.append({"id": action_id, "title": title})

        return main, actions

    def _strip_thinking(self, s: str) -> str:
        """Backward-compatible basic cleaner (kept for compatibility)."""
        lines: List[str] = []
        for line in s.splitlines():
            if re.match(r"^\s*(thinking|reasoning|analysis|chain[- ]?of[- ]?thoughts?)\s*:\s*", line, flags=re.IGNORECASE):
                continue
            lines.append(line)
        return "\n".join(lines)

    def _clean_ai_output(self, s: str) -> str:
        """Stricter cleaner that removes internal reasoning/debug/metadata lines and blocks.

        - Drops lines starting with Thinking:/Reasoning:/Analysis:/Debug:/Internal:
        - Removes simple XML-like tags (e.g., <thinking>...</thinking>)
        - Removes fenced code blocks explicitly labeled as thinking/analysis
        Returns trimmed text.
        """
        text = s
        # Remove XML-like blocks such as <thinking>...</thinking>
        try:
            text = re.sub(r"<\s*(thinking|analysis|internal)[^>]*>.*?<\s*/\s*\1\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
        except Exception:
            pass
        # Remove fenced blocks labeled with thinking/analysis
        try:
            text = re.sub(r"```(?:\s*(thinking|analysis|chain[- ]?of[- ]?thought))\b[\s\S]*?```", "", text, flags=re.IGNORECASE)
        except Exception:
            pass
        # Line-level filters
        cleaned_lines: List[str] = []
        for line in text.splitlines():
            if re.match(r"^\s*(thinking|reasoning|analysis|debug|internal)\s*:\s*", line, flags=re.IGNORECASE):
                continue
            # Also drop obvious tool/log prefixes
            if re.match(r"^\s*(tool|log|metadata)\s*:\s*", line, flags=re.IGNORECASE):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    # -------- LLM integration (Groq-first) --------
    def _build_llm_prompt(self, business: Business, user_text: str) -> str:
        details = [
            f"Business: {business.name}",
            f"Description: {business.description or 'N/A'}",
        ]
        return (
            "You are a helpful assistant for a local business. Answer clearly in markdown.\n"
            "Focus on being concise, actionable, and polite. Make conversation\n\n" + "\n".join(details) +
            f"\n\nUser: {user_text}\nAssistant:"
        )

    def _call_llm(self, *, prompt: str, language: str) -> AIResult:
        # Groq-only per product direction; surface a clear message if key missing
        # Prefer value from settings (loaded from .env), fallback to environment
        groq_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        if not groq_key:
            return AIResult(
                text=(
                    "Groq LLM is not configured. Set GROQ_API_KEY in your environment to enable conversational AI."
                ),
                model_used=None,
            )
        # Select model (configurable via settings.GROQ_MODEL or env GROQ_MODEL)
        # Use a widely-available default and prepare fallbacks if the configured model isn't available.
        configured_model = getattr(settings, "GROQ_MODEL", None) or os.getenv("GROQ_MODEL")
        default_model = "qwen/qwen3-32b"
        fallback_models = [
            default_model,
            #"qwen-2.5-32b",
            "mixtral-8x7b-32768",
        ]
        # Start with the configured model (if any), then try fallbacks
        model_try_order = []
        if configured_model:
            model_try_order.append(configured_model)
        for m in fallback_models:
            if m not in model_try_order:
                model_try_order.append(m)
        try:
            # Prefer httpx if available; fall back to urllib to avoid SDK version issues
            try:
                import httpx  # type: ignore

                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                }
                last_err: Optional[Exception] = None
                with httpx.Client(timeout=15.0) as client:
                    for model_name in model_try_order:
                        payload = {
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": "Reply in markdown. Be friendly, natural and concise."},
                                {"role": "user", "content": prompt},
                            ],
                            "temperature": 0.4,
                        }
                        try:
                            resp = client.post(url, headers=headers, json=payload)
                            resp.raise_for_status()
                            data = resp.json()
                            text = data["choices"][0]["message"]["content"]
                            return AIResult(text=text, model_used=f"groq:{model_name}")
                        except httpx.HTTPStatusError as he:  # type: ignore
                            # Model not found or not available typically returns 404 from OpenAI-compatible APIs
                            if he.response is not None and he.response.status_code in (400, 404):
                                # Try next fallback
                                last_err = he
                                continue
                            last_err = he
                            break
                        except Exception as e:
                            last_err = e
                            break
                # If we reach here, all attempts failed
                raise last_err or RuntimeError("Failed to complete request to Groq API")
            except ModuleNotFoundError:
                import json as _json
                from urllib.request import Request, urlopen  # type: ignore

                url = "https://api.groq.com/openai/v1/chat/completions"
                last_err: Optional[Exception] = None
                for model_name in model_try_order:
                    payload = _json.dumps({
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": "Reply in markdown. Be friendly, natural and concise."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.4,
                    }).encode("utf-8")
                    req = Request(url, data=payload, headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                    })
                    try:
                        with urlopen(req, timeout=15) as resp:  # nosec - trusted API endpoint
                            data = _json.loads(resp.read().decode("utf-8"))
                        text = data["choices"][0]["message"]["content"]
                        return AIResult(text=text, model_used=f"groq:{model_name}")
                    except Exception as e:
                        last_err = e
                        continue
                raise last_err or RuntimeError("Failed to complete request to Groq API")
        except Exception as e:
            return AIResult(text=f"LLM error: {e}", model_used=f"groq:{model_name}")
