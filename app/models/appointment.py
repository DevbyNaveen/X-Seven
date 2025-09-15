"""Appointment model for business appointments using Supabase."""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.base import SupabaseModel


class AppointmentStatus(str, Enum):
    """Appointment status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Appointment(SupabaseModel):
    """Appointment model for business appointments."""
    table_name = "appointments"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.customer_id = kwargs.get('customer_id')
        self.service_id = kwargs.get('service_id')
        self.staff_id = kwargs.get('staff_id')
        self.start_time = kwargs.get('start_time')
        self.end_time = kwargs.get('end_time')
        self.status = kwargs.get('status', AppointmentStatus.PENDING)
        self.notes = kwargs.get('notes')
        self.customer_name = kwargs.get('customer_name')
        self.customer_phone = kwargs.get('customer_phone')
        self.customer_email = kwargs.get('customer_email')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
