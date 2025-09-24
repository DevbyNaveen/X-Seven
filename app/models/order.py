"""Order model for restaurant orders using Supabase."""
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.base import SupabaseModel


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """Payment method enumeration."""
    CASH = "cash"
    CARD = "card"
    MOBILE_PAY = "mobile_pay"
    ONLINE = "online"


class Order(SupabaseModel):
    """Restaurant order model for Supabase."""
    table_name = "orders"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.table_id = kwargs.get('table_id')
        self.customer_session_id = kwargs.get('customer_session_id')
        self.order_number = kwargs.get('order_number')
        self.status = kwargs.get('status', OrderStatus.PENDING)
        self.total_amount = kwargs.get('total_amount', 0.0)
        self.tax_amount = kwargs.get('tax_amount', 0.0)
        self.discount_amount = kwargs.get('discount_amount', 0.0)
        self.final_amount = kwargs.get('final_amount', 0.0)
        self.special_instructions = kwargs.get('special_instructions')
        self.payment_status = kwargs.get('payment_status', PaymentStatus.PENDING)
        self.payment_method = kwargs.get('payment_method')
        self.payment_reference = kwargs.get('payment_reference')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.completed_at = kwargs.get('completed_at')
