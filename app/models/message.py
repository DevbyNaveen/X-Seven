"""Message model for chat messages using Supabase."""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.base import SupabaseModel


class MessageType(str, Enum):
    """Message type enumeration."""
    CUSTOMER = "customer"
    AI = "ai"
    STAFF = "staff"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """Message status enumeration."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class Message(SupabaseModel):
    """Message model for chat conversations."""
    table_name = "messages"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.customer_session_id = kwargs.get('customer_session_id')
        self.order_id = kwargs.get('order_id')
        self.sender_type = kwargs.get('sender_type')
        self.sender_id = kwargs.get('sender_id')
        self.content = kwargs.get('content')
        self.message_type = kwargs.get('message_type', MessageType.CUSTOMER)
        self.status = kwargs.get('status', MessageStatus.SENT)
        self.is_ai_generated = kwargs.get('is_ai_generated', False)
        self.ai_confidence = kwargs.get('ai_confidence')
        self.metadata = kwargs.get('metadata', {})
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
