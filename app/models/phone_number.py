"""Phone number model for Supabase operations."""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.base import SupabaseModel


class NumberStatus(str, Enum):
    """Phone number status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    FAILED = "failed"


class PhoneNumber(SupabaseModel):
    """Phone number model for business phone configurations."""
    table_name = "phone_numbers"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.phone_number = kwargs.get('phone_number')
        self.provider = kwargs.get('provider')
        self.provider_id = kwargs.get('provider_id')
        self.status = kwargs.get('status', NumberStatus.PENDING)
        self.is_primary = kwargs.get('is_primary', False)
        self.type = kwargs.get('type')
        self.webhook_url = kwargs.get('webhook_url')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
