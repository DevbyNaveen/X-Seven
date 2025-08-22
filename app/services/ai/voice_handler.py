"""
VoiceHandler: minimal voice conversation handler.

Purpose:
- Provide a lightweight adapter for voice interactions that delegates
  to the existing UniversalBot conversation pipeline.
- Keep dependencies minimal; no direct TTS/STT here. Upstream providers
  (e.g., Twilio) handle audio I/O, we receive text via webhooks.

This stub is sufficient to satisfy imports in voice endpoints and can
be expanded later with streaming TTS/STT and barge-in support.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class VoiceHandler:
    """Simple voice handler that delegates text processing to UniversalBot."""

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db

    async def process(self,
                      session_id: str,
                      message: str,
                      *,
                      language: str = "en",
                      context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a voice-transcribed text message and return bot response.

        Parameters:
        - session_id: Conversation session identifier
        - message: Transcribed user text
        - language: ISO language code (default 'en')
        - context: Optional extra metadata (phone number, business, etc.)

        Returns a dict compatible with ChatResponse expectations:
        {"message": str, "suggested_actions": list, "metadata": dict}
        """
        context = context or {}

        # If no DB is available (e.g., used as a pure helper), return a default.
        if self.db is None:
            logger.debug("VoiceHandler called without DB; returning default echo response.")
            return {
                "message": message or "Hello! How can I help you today?",
                "suggested_actions": [],
                "metadata": {"channel": "voice", "language": language}
            }

        # Delegate to UniversalBot for full AI pipeline handling.
        from app.services.ai.universalbot.universal_bot import UniversalBot

        bot = UniversalBot(self.db)
        response = await bot.process_message(
            session_id=session_id,
            message=message,
            channel="voice",
            language=language,
            context=context,
        )
        # Ensure keys exist
        return {
            "message": response.get("message", ""),
            "suggested_actions": response.get("suggested_actions", []),
            "metadata": {**response.get("metadata", {}), "channel": "voice", "language": language},
        }
