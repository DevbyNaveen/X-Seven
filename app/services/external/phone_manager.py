"""Phone number management service."""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import random
import string
from datetime import datetime, timedelta
import logging
from app.models import Business

logger = logging.getLogger(__name__)


class PhoneManagerService:
    """Manage phone numbers across multiple providers."""

    def __init__(self, db: Session):
        self.db = db
        self.otp_store = {}  # In production, use Redis

    async def register_universal_access(self, business_id: int) -> Dict[str, Any]:
        """Register business for universal number access."""
        # Add business to universal number routing
        return {
            "status": "registered",
            "universal_number": "+1-800-X-SEVENAI",
            "message": "You can now receive orders through the universal number"
        }

    async def provision_new_number(
        self,
        business_id: int,
        country_code: str,
        area_code: Optional[str],
        provider: str
    ) -> Dict[str, Any]:
        """Auto-provision a new phone number."""
        # In production, integrate with Twilio/Vonage API
        # For demo, generate a mock number

        if provider == "twilio":
            # Would call Twilio API to search and buy number
            mock_number = f"+{country_code}-{area_code or '555'}-{random.randint(1000, 9999)}"
        else:
            mock_number = f"+{country_code}-{random.randint(1000000, 9999999)}"

        return {
            "status": "provisioned",
            "phone_number": mock_number,
            "provider": provider,
            "message": "Number successfully provisioned"
        }

    async def send_otp(self, phone_number: str) -> str:
        """Send OTP for phone verification."""
        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))

        # Store OTP with expiry (5 minutes)
        self.otp_store[phone_number] = {
            'otp': otp,
            'expires': datetime.utcnow() + timedelta(minutes=5)
        }

        # In production, send via SMS/WhatsApp
        logger.info(f"OTP for {phone_number}: {otp}")

        return otp

    async def verify_otp(self, phone_number: str, otp_code: str) -> bool:
        """Verify OTP code."""
        stored = self.otp_store.get(phone_number)

        if not stored:
            return False

        if datetime.utcnow() > stored['expires']:
            del self.otp_store[phone_number]
            return False

        if stored['otp'] == otp_code:
            del self.otp_store[phone_number]
            return True

        return False

    async def setup_whatsapp_business(self, business_id: int):
        """Setup WhatsApp Business API."""
        # In production, this would:
        # 1. Register with WhatsApp Business API
        # 2. Configure webhooks
        # 3. Set business profile
        # 4. Enable features

        logger.info(f"Setting up WhatsApp for business {business_id}")

        # Simulate API setup delay
        import asyncio
        await asyncio.sleep(2)

        return {
            "status": "connected",
            "whatsapp_id": f"wa_{business_id}",
            "features_enabled": ["messaging", "media", "interactive"]
        }

    async def complete_whatsapp_setup(
        self,
        business_id: int,
        phone_number: str
    ) -> Dict[str, Any]:
        """Complete WhatsApp Business API setup after verification."""
        # Update business with WhatsApp details
        business = self.db.query(Business).filter(
            Business.id == business_id
        ).first()

        if business:
            business.settings = business.settings or {}
            business.settings['whatsapp'] = {
                'phone_number': phone_number,
                'connected': True,
                'verified_at': datetime.utcnow().isoformat()
            }
            self.db.commit()

        return {
            "status": "complete",
            "phone_number": phone_number,
            "whatsapp_connected": True
        }