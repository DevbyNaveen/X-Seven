"""Waitlist entry model for business waitlists using Supabase."""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.base import SupabaseModel


class WaitlistStatus(str, Enum):
    """Waitlist entry status enumeration."""
    WAITING = "waiting"
    NOTIFIED = "notified"
    SEATED = "seated"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class WaitlistEntry(SupabaseModel):
    """Waitlist entry model for business waitlists."""
    table_name = "waitlist_entries"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.customer_name = kwargs.get('customer_name')
        self.customer_phone = kwargs.get('customer_phone')
        self.customer_email = kwargs.get('customer_email')
        self.party_size = kwargs.get('party_size', 1)
        self.status = kwargs.get('status', WaitlistStatus.WAITING)
        self.notes = kwargs.get('notes')
        self.estimated_wait_time = kwargs.get('estimated_wait_time')
        self.position = kwargs.get('position')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
