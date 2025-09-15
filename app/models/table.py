"""Table model for restaurant tables using Supabase."""
from enum import Enum
from datetime import datetime
from typing import Optional
from app.models.base import SupabaseModel


class TableStatus(str, Enum):
    """Table status enumeration."""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    CLEANING = "cleaning"
    OUT_OF_ORDER = "out_of_order"


class Table(SupabaseModel):
    """Restaurant table model for Supabase."""
    table_name = "tables"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.table_number = kwargs.get('table_number')
        self.capacity = kwargs.get('capacity', 4)
        self.section = kwargs.get('section')
        self.location_notes = kwargs.get('location_notes')
        self.qr_code_id = kwargs.get('qr_code_id')
        self.qr_code_url = kwargs.get('qr_code_url')
        self.status = kwargs.get('status', TableStatus.AVAILABLE)
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
