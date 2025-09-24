"""
Base provider interface for phone services.
All providers must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PhoneNumberInfo:
    """Information about an available phone number."""
    number: str
    country_code: str
    provider: str
    capabilities: List[str]  # ['voice', 'sms', 'whatsapp']
    monthly_cost: float
    setup_cost: float
    region: Optional[str] = None


class BasePhoneProvider(ABC):
    """Abstract base class for phone providers."""

    @abstractmethod
    async def search_available_numbers(
        self,
        country_code: str,
        region: Optional[str] = None,
        capabilities: Optional[List[str]] = None
    ) -> List[PhoneNumberInfo]:
        """Search for available phone numbers."""
        pass

    @abstractmethod
    async def provision_number(
        self,
        phone_number: str,
        webhook_url: str
    ) -> Dict[str, Any]:
        """Provision a phone number."""
        pass

    @abstractmethod
    async def release_number(self, phone_number: str) -> bool:
        """Release a phone number."""
        pass

    @abstractmethod
    async def setup_forwarding(
        self,
        from_number: str,
        to_number: str,
        extension: Optional[str] = None
    ) -> bool:
        """Setup call forwarding."""
        pass

    @abstractmethod
    async def send_sms(
        self,
        to_number: str,
        from_number: str,
        message: str
    ) -> bool:
        """Send SMS message."""
        pass

    @abstractmethod
    async def make_call(
        self,
        to_number: str,
        from_number: str,
        twiml_url: str
    ) -> str:
        """Initiate outbound call."""
        pass