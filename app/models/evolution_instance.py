"""Evolution API instance model for multi-tenant WhatsApp and phone management."""
import enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.models.base import SupabaseModel


class InstanceStatus(str, enum.Enum):
    """Evolution API instance status."""
    CREATING = "creating"
    ACTIVE = "active"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class WhatsAppStatus(str, enum.Enum):
    """WhatsApp connection status."""
    DISABLED = "disabled"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    QR_CODE = "qr_code"
    ERROR = "error"


class MessageType(str, enum.Enum):
    """Message types supported by Evolution API."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    TEMPLATE = "template"


class EvolutionInstance(SupabaseModel):
    """
    Evolution API instance model for business-specific WhatsApp and phone management.
    Each business gets their own Evolution instance for isolated communication.
    """
    table_name = "evolution_instances"
    
    # Business relationship
    business_id: int
    
    # Instance configuration
    instance_name: str  # Unique identifier for the Evolution API instance
    instance_token: Optional[str] = None  # API token for this instance
    
    # Phone number configuration
    phone_number: Optional[str] = None
    phone_country_code: Optional[str] = None
    phone_provider: Optional[str] = None  # twilio, vonage, etc.
    phone_sid: Optional[str] = None  # Provider-specific ID
    
    # Instance status
    status: str = InstanceStatus.CREATING
    last_seen: Optional[datetime] = None
    
    # WhatsApp configuration
    whatsapp_enabled: bool = False
    whatsapp_status: str = WhatsAppStatus.DISABLED
    whatsapp_qr_code: Optional[str] = None
    whatsapp_profile: Dict[str, Any] = {}
    whatsapp_business_profile: Dict[str, Any] = {}
    
    # Evolution API configuration
    evolution_config: Dict[str, Any] = {}
    webhook_url: Optional[str] = None
    
    # Usage tracking
    messages_sent: int = 0
    messages_received: int = 0
    calls_handled: int = 0
    last_activity: Optional[datetime] = None
    
    # Billing and limits
    monthly_cost: float = 0.0
    usage_limits: Dict[str, Any] = {}
    current_usage: Dict[str, Any] = {}
    
    # Error tracking
    last_error: Optional[str] = None
    error_count: int = 0
    
    def __repr__(self):
        return f"<EvolutionInstance {self.instance_name} ({self.status}) - Business {self.business_id}>"
    
    def is_active(self) -> bool:
        """Check if instance is active and ready to use."""
        return self.status == InstanceStatus.ACTIVE
    
    def is_whatsapp_connected(self) -> bool:
        """Check if WhatsApp is connected and ready."""
        return (
            self.whatsapp_enabled and 
            self.whatsapp_status == WhatsAppStatus.CONNECTED
        )
    
    def get_webhook_url(self, base_url: str) -> str:
        """Generate webhook URL for this instance."""
        return f"{base_url}/api/v1/evolution/webhook/{self.instance_name}"
    
    def update_usage(self, message_type: str = "sent", count: int = 1):
        """Update usage statistics."""
        if message_type == "sent":
            self.messages_sent += count
        elif message_type == "received":
            self.messages_received += count
        elif message_type == "call":
            self.calls_handled += count
        
        self.last_activity = datetime.utcnow()
    
    def is_within_limits(self) -> bool:
        """Check if instance is within usage limits."""
        limits = self.usage_limits
        usage = self.current_usage
        
        for limit_type, limit_value in limits.items():
            if limit_value != -1:  # -1 means unlimited
                current = usage.get(limit_type, 0)
                if current >= limit_value:
                    return False
        
        return True
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for frontend display."""
        return {
            "instance_name": self.instance_name,
            "status": self.status,
            "phone_number": self.phone_number,
            "whatsapp_enabled": self.whatsapp_enabled,
            "whatsapp_status": self.whatsapp_status,
            "whatsapp_qr_code": self.whatsapp_qr_code,
            "last_seen": self.last_seen,
            "last_activity": self.last_activity,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "calls_handled": self.calls_handled,
            "monthly_cost": self.monthly_cost,
            "is_active": self.is_active(),
            "is_whatsapp_connected": self.is_whatsapp_connected(),
            "last_error": self.last_error
        }


class EvolutionMessage(SupabaseModel):
    """
    Evolution API message model for tracking all messages sent/received.
    """
    table_name = "evolution_messages"
    
    # Instance relationship
    evolution_instance_id: int
    business_id: int
    
    # Message identification
    message_id: str  # Evolution API message ID
    whatsapp_message_id: Optional[str] = None  # WhatsApp message ID
    
    # Message content
    message_type: str = MessageType.TEXT
    content: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    
    # Participants
    from_number: str
    to_number: str
    contact_name: Optional[str] = None
    
    # Message status
    direction: str  # "inbound" or "outbound"
    status: str = "pending"  # pending, sent, delivered, read, failed
    
    # Timestamps
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    # AI processing
    ai_processed: bool = False
    ai_response_generated: bool = False
    ai_response_content: Optional[str] = None
    ai_processing_time: Optional[float] = None
    
    # Context and metadata
    conversation_context: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    
    def __repr__(self):
        return f"<EvolutionMessage {self.message_id} ({self.direction}) - {self.message_type}>"
    
    def is_inbound(self) -> bool:
        """Check if message is inbound (from customer)."""
        return self.direction == "inbound"
    
    def is_outbound(self) -> bool:
        """Check if message is outbound (to customer)."""
        return self.direction == "outbound"
    
    def needs_ai_response(self) -> bool:
        """Check if message needs AI processing."""
        return (
            self.is_inbound() and 
            not self.ai_processed and 
            self.message_type == MessageType.TEXT
        )
    
    def mark_ai_processed(self, response_content: Optional[str] = None, processing_time: Optional[float] = None):
        """Mark message as processed by AI."""
        self.ai_processed = True
        if response_content:
            self.ai_response_generated = True
            self.ai_response_content = response_content
        if processing_time:
            self.ai_processing_time = processing_time


class EvolutionWebhookEvent(SupabaseModel):
    """
    Evolution API webhook event model for tracking all webhook events.
    """
    table_name = "evolution_webhook_events"
    
    # Instance relationship
    evolution_instance_id: Optional[int] = None
    instance_name: str
    
    # Event details
    event_type: str  # message, status, connection, etc.
    event_data: Dict[str, Any] = {}
    
    # Processing status
    processed: bool = False
    processed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    
    # Raw webhook data
    raw_payload: Dict[str, Any] = {}
    headers: Dict[str, str] = {}
    
    def __repr__(self):
        return f"<EvolutionWebhookEvent {self.event_type} - {self.instance_name}>"
    
    def mark_processed(self, error: Optional[str] = None):
        """Mark webhook event as processed."""
        self.processed = True
        self.processed_at = datetime.utcnow()
        if error:
            self.processing_error = error
