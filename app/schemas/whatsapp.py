"""WhatsApp specific schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class WhatsAppMessage(BaseModel):
    """WhatsApp message structure."""
    from_number: str
    to_number: str
    message_text: str
    message_type: str = "text"  # text, image, audio, document
    media_url: Optional[str] = None
    context: Optional[Dict[str, Any]] = {}


class WhatsAppWebhook(BaseModel):
    """WhatsApp webhook payload."""
    entry: List[Dict[str, Any]]

    def get_message(self) -> Optional[WhatsAppMessage]:
        """Extract message from webhook payload."""
        try:
            changes = self.entry[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                messages = value.get("messages", [])
                if messages:
                    msg = messages[0]
                    return WhatsAppMessage(
                        from_number=msg.get("from"),
                        to_number=value.get("metadata", {}).get("display_phone_number"),
                        message_text=msg.get("text", {}).get("body", ""),
                        message_type=msg.get("type", "text")
                    )
        except (IndexError, KeyError):
            pass
        return None


class WhatsAppButton(BaseModel):
    """Interactive button for WhatsApp."""
    id: str
    title: str


class WhatsAppListItem(BaseModel):
    """List item for WhatsApp interactive messages."""
    id: str
    title: str
    description: Optional[str] = None


class WhatsAppInteractiveMessage(BaseModel):
    """Interactive WhatsApp message with buttons or lists."""
    type: str = "button"  # button or list
    header: Optional[str] = None
    body: str
    footer: Optional[str] = None
    buttons: Optional[List[WhatsAppButton]] = None
    list_items: Optional[List[WhatsAppListItem]] = None


class WhatsAppResponse(BaseModel):
    """WhatsApp response."""
    success: bool
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime