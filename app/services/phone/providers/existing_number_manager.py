"""
Manager for integrating café's existing phone numbers.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Business, PhoneNumber, NumberStatus
import random
import string
import logging

logger = logging.getLogger(__name__)


class ExistingNumberManager:
    """Manages integration of café's existing phone numbers."""

    def __init__(self, db: Session):
        self.db = db

    def setup_existing_number(
        self,
        business_id: int,
        existing_number: str,
        provider_type: str = "forwarding"
    ) -> Dict[str, Any]:
        """
        Setup café's existing number for use with X-SevenAI.

        Args:
            business_id: Business ID
            existing_number: Café's existing phone number
            provider_type: Type of integration (forwarding, sip, etc.)

        Returns:
            Setup instructions and configuration
        """

        # Generate unique extension code for this café
        extension_code = self._generate_extension_code()

        # Get forwarding number based on region
        forwarding_number = self._get_regional_forwarding_number(existing_number)

        # Create phone record
        phone_record = PhoneNumber(
            business_id=business_id,
            phone_number=existing_number,
            country_code=self._extract_country_code(existing_number),
            provider="existing",
            is_universal=False,
            is_primary=True,
            status=NumberStatus.PROVISIONING,
            capabilities={
                "voice": True,
                "sms": False,  # SMS forwarding usually not supported
                "whatsapp": False
            },
            metadata={
                "integration_type": provider_type,
                "extension_code": extension_code,
                "forwarding_to": forwarding_number,
                "setup_completed": False
            },
            activated_at=None  # Will be set when verified
        )

        self.db.add(phone_record)
        self.db.commit()

        # Generate setup instructions
        instructions = self._generate_setup_instructions(
            existing_number,
            forwarding_number,
            extension_code,
            provider_type
        )

        return {
            "phone_id": phone_record.id,
            "extension_code": extension_code,
            "forwarding_number": forwarding_number,
            "instructions": instructions,
            "verification_required": True
        }

    def verify_existing_number(
        self,
        business_id: int,
        phone_id: int,
        verification_code: str
    ) -> bool:
        """
        Verify that existing number forwarding is working.

        Args:
            business_id: Business ID
            phone_id: Phone record ID
            verification_code: Code received during test call

        Returns:
            Success status
        """

        phone_record = self.db.query(PhoneNumber).filter(
            PhoneNumber.id == phone_id,
            PhoneNumber.business_id == business_id
        ).first()

        if not phone_record:
            return False

        # Check verification code
        expected_code = phone_record.metadata.get("extension_code")

        if verification_code == expected_code:
            # Mark as active
            phone_record.status = NumberStatus.ACTIVE
            phone_record.activated_at = datetime.utcnow()
            phone_record.metadata["setup_completed"] = True

            # Update business
            business = self.db.query(Business).filter(
                Business.id == business_id
            ).first()

            if business:
                business.custom_phone_number = phone_record.phone_number

            self.db.commit()

            logger.info(f"Verified existing number {phone_record.phone_number} for business {business_id}")
            return True

        return False

    def _generate_extension_code(self) -> str:
        """Generate unique 4-digit extension code."""
        return ''.join(random.choices(string.digits, k=4))

    def _extract_country_code(self, phone_number: str) -> str:
        """Extract country code from phone number."""
        if phone_number.startswith("+371"):
            return "+371"
        elif phone_number.startswith("+372"):
            return "+372"
        elif phone_number.startswith("+370"):
            return "+370"
        else:
            return "+1"  # Default

    def _get_regional_forwarding_number(self, existing_number: str) -> str:
        """Get appropriate forwarding number based on region."""
        if existing_number.startswith("+371"):
            # Latvia - use Estonian number as receiver
            return settings.ESTONIA_RECEIVER_NUMBER or "+372 5555 0000"
        elif existing_number.startswith("+372"):
            # Estonia
            return settings.ESTONIA_RECEIVER_NUMBER or "+372 5555 0000"
        else:
            # Default
            return settings.UNIVERSAL_BOT_NUMBER or "+1 800 X-SEVENAI"

    def _generate_setup_instructions(
        self,
        existing_number: str,
        forwarding_number: str,
        extension_code: str,
        provider_type: str
    ) -> Dict[str, Any]:
        """Generate provider-specific setup instructions."""

        # Detect local provider
        provider = self._detect_provider(existing_number)

        instructions = {
            "provider": provider,
            "steps": [],
            "test_instructions": {
                "call_your_number": existing_number,
                "you_should_hear": "Welcome to X-SevenAI. Please enter your extension code.",
                "enter_code": extension_code,
                "success_message": "Setup verified! Your café is now connected."
            }
        }

        if provider == "Tele2":
            instructions["steps"] = [
                "Call Tele2 customer service: 1600",
                f"Request: 'Enable call forwarding to {forwarding_number}'",
                "They will ask for verification",
                f"Extension code (if asked): {extension_code}",
                "Forwarding will be active in 5-10 minutes"
            ]

        elif provider == "LMT":
            instructions["steps"] = [
                "Dial *21*" + forwarding_number.replace(" ", "") + "#",
                "Press call button",
                "You should see 'Forwarding activated'",
                "To disable: Dial ##21#"
            ]

        elif provider == "Bite":
            instructions["steps"] = [
                "Log into Bite self-service: mans.bite.lv",
                "Go to 'Services' → 'Call Settings'",
                f"Enable forwarding to: {forwarding_number}",
                f"Add extension: {extension_code}",
                "Save changes"
            ]

        else:
            # Generic instructions
            instructions["steps"] = [
                f"Contact your phone provider",
                f"Request call forwarding to: {forwarding_number}",
                f"Extension/Reference code: {extension_code}",
                "Test the setup using instructions below"
            ]

        return instructions

    def _detect_provider(self, phone_number: str) -> str:
        """Detect Latvian provider from number prefix."""
        # Latvian mobile prefixes
        prefixes = {
            "2": "Tele2",
            "6": "LMT",
            "7": "Bite"
        }

        if phone_number.startswith("+371"):
            # Get first digit after country code
            prefix = phone_number[4:5]
            return prefixes.get(prefix, "Unknown")

        return "Unknown"