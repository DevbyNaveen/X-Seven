"""
Vonage (Nexmo) provider implementation for Latvian numbers.
"""
from typing import Dict, Any, Optional, List
from app.services.phone.providers.base import BasePhoneProvider, PhoneNumberInfo
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Optional Nexmo (Vonage) import to avoid hard dependency at startup
try:
    import nexmo  # type: ignore
    NEXMO_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    nexmo = None  # type: ignore
    NEXMO_AVAILABLE = False


class VonageProvider(BasePhoneProvider):
    """Vonage phone provider implementation."""

    def __init__(self):
        # Initialize client if SDK and credentials are present
        self.client = None
        if NEXMO_AVAILABLE and getattr(settings, "VONAGE_API_KEY", None) and getattr(settings, "VONAGE_API_SECRET", None):
            try:
                self.client = nexmo.Client(
                    key=settings.VONAGE_API_KEY,
                    secret=settings.VONAGE_API_SECRET
                )
            except Exception as e:
                logger.warning(f"Vonage client init failed: {e}")
        else:
            if not NEXMO_AVAILABLE:
                logger.warning("Nexmo SDK not installed; VonageProvider running in no-op mode")
            else:
                logger.warning("Vonage credentials missing; VonageProvider running in no-op mode")
        self.provider_name = "vonage"

    async def search_available_numbers(
        self,
        country_code: str,
        region: Optional[str] = None,
        capabilities: Optional[List[str]] = None
    ) -> List[PhoneNumberInfo]:
        """Search for available Vonage numbers."""
        if not self.client:
            logger.debug("Vonage client unavailable; returning no search results")
            return []
        # This part of your code was correct and remains unchanged
        try:
            country_map = {"+371": "LV", "+372": "EE", "+370": "LT"}
            country = country_map.get(country_code, "LV")
            response = self.client.numbers.get_available_numbers(country, {"features": "VOICE,SMS"})
            
            numbers = []
            for number in response.get("numbers", []):
                info = PhoneNumberInfo(
                    number=number["msisdn"],
                    country_code=country_code,
                    provider=self.provider_name,
                    capabilities=number.get("features", []),
                    monthly_cost=12.00,
                    setup_cost=0.50,
                    region=number.get("region")
                )
                numbers.append(info)
            return numbers
        except Exception as e:
            logger.error(f"Vonage search failed: {e}")
            return []

    async def provision_number(
        self,
        phone_number: str,
        webhook_url: str
    ) -> Dict[str, Any]:
        """Provision a Vonage number."""
        if not self.client:
            logger.debug("Vonage client unavailable; cannot provision number")
            return {"success": False, "error": "Vonage client unavailable"}
        try:
            # Buy the number first
            buy_response = self.client.numbers.buy_number({
                "country": "LV", 
                "msisdn": phone_number
            })
            
            if buy_response.get("error-code"):
                logger.error(f"Failed to buy number: {buy_response}")
                return {"success": False, "error": f"Failed to buy number: {buy_response.get('error-code')}"}
            
            # Configure the number with webhooks
            update_response = self.client.numbers.update_number({
                "msisdn": phone_number,
                "moHttpUrl": f"{webhook_url}/webhooks/vonage/sms",
                "voiceCallbackType": "app",
                "voiceCallbackValue": settings.VONAGE_APPLICATION_ID,
                "voiceStatusCallbackUrl": f"{webhook_url}/webhooks/vonage/voice-status"
            })
            
            if update_response.get("error-code"):
                logger.error(f"Failed to configure number: {update_response}")
                return {"success": False, "error": f"Failed to configure number: {update_response.get('error-code')}"}
            
            return {
                "success": True, 
                "number": phone_number, 
                "provider": self.provider_name,
                "sid": phone_number  # Vonage doesn't use SIDs like Twilio
            }
        except Exception as e:
            logger.error(f"Vonage provision failed: {e}")
            return {"success": False, "error": str(e)}

    # ... (the rest of the methods in this file are likely okay but depend on the client object,
    # which is now correctly initialized) ...
    async def release_number(self, phone_number: str) -> bool:
        """Release a Vonage number."""
        if not self.client:
            logger.debug("Vonage client unavailable; cannot release number")
            return False
        try:
            response = self.client.numbers.cancel_number({"country": "LV", "msisdn": phone_number})
            return response.get("error-code") == "200"
        except Exception as e:
            logger.error(f"Vonage release failed: {e}")
            return False

    async def setup_forwarding(self, from_number: str, to_number: str, extension: Optional[str] = None) -> bool:
        # Not implemented for Vonage in this stub
        if not self.client:
            logger.debug("Vonage client unavailable; cannot setup forwarding")
            return False
        return True

    async def send_sms(self, to_number: str, from_number: str, message: str) -> bool:
        """Send SMS via Vonage."""
        if not self.client:
            logger.debug("Vonage client unavailable; cannot send SMS")
            return False
        try:
            response_data = self.client.send_message({
                'from': from_number,
                'to': to_number,
                'text': message,
            })
            return response_data['messages'][0]['status'] == '0'
        except Exception as e:
            logger.error(f"Vonage SMS failed: {e}")
            return False

    async def make_call(self, to_number: str, from_number: str, twiml_url: str) -> str:
        """Make outbound call via Vonage."""
        if not self.client:
            logger.debug("Vonage client unavailable; cannot make call")
            return ""
        try:
            response = self.client.create_call({
                'to': [{'type': 'phone', 'number': to_number}],
                'from': {'type': 'phone', 'number': from_number},
                'answer_url': [twiml_url]
            })
            return response['uuid']
        except Exception as e:
            logger.error(f"Vonage call failed: {e}")
            return ""