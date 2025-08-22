"""Twilio service for SMS and voice calls."""
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TwilioService:
    """Basic Twilio service for SMS and voice functionality."""
    
    def __init__(self):
        self.is_configured = False
        logger.info("TwilioService initialized (basic mode)")
    
    async def send_sms(
        self,
        to_number: str,
        message: str,
        from_number: Optional[str] = None
    ) -> bool:
        """Send SMS message."""
        logger.info(f"SMS would be sent to {to_number}: {message[:50]}...")
        return True  # Mock success
    
    async def make_voice_call(
        self,
        to_number: str,
        twiml_url: str,
        from_number: Optional[str] = None
    ) -> Optional[str]:
        """Make voice call."""
        logger.info(f"Voice call would be made to {to_number}")
        return "mock_call_sid"  # Mock call SID
    
    async def send_whatsapp_message(
        self,
        to_number: str,
        message: str,
        from_number: Optional[str] = None
    ) -> bool:
        """Send WhatsApp message."""
        logger.info(f"WhatsApp message would be sent to {to_number}: {message[:50]}...")
        return True  # Mock success
