"""Service provider model for business services using Supabase."""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.base import SupabaseModel


class ServiceProviderStatus(str, Enum):
    """Service provider status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class ServiceProvider(SupabaseModel):
    """Service provider model for business services."""
    table_name = "service_providers"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.name = kwargs.get('name')
        self.email = kwargs.get('email')
        self.phone = kwargs.get('phone')
        self.specialties = kwargs.get('specialties', [])
        self.status = kwargs.get('status', ServiceProviderStatus.ACTIVE)
        self.availability = kwargs.get('availability', {})
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
