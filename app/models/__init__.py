"""
Database models package.

This file makes it easy to import all models at once.
It also ensures all models are registered with Supabase.
"""

# Import all models
from .base import SupabaseModel
from .business import Business, SubscriptionPlan, PhoneNumberType, BusinessCategory
from .user import User, UserRole
from .table import Table, TableStatus
from .order import Order, OrderStatus, PaymentStatus, PaymentMethod
from .phone_number import PhoneNumber, NumberStatus
from .menu_item import MenuItem, MenuItemStatus
from .menu_category import MenuCategory
from .message import Message, MessageType, MessageStatus
from .appointment import Appointment, AppointmentStatus
from .service_provider import ServiceProvider, ServiceProviderStatus
from .waitlist_entry import WaitlistEntry, WaitlistStatus

# Export all models
__all__ = [
    # Base
    "SupabaseModel",
    
    # Business
    "Business",
    "SubscriptionPlan",
    "PhoneNumberType", 
    "BusinessCategory",
    
    # User
    "User",
    "UserRole",
    
    # Table
    "Table",
    "TableStatus",
    
    # Order
    "Order",
    "OrderStatus",
    "PaymentStatus",
    "PaymentMethod",
    
    # Phone
    "PhoneNumber",
    "NumberStatus",
    
    # Menu
    "MenuItem",
    "MenuItemStatus",
    "MenuCategory",
    
    # Message
    "Message",
    "MessageType",
    "MessageStatus",
    
    # Appointment
    "Appointment",
    "AppointmentStatus",
    
    # Service Provider
    "ServiceProvider",
    "ServiceProviderStatus",
    
    # Waitlist
    "WaitlistEntry",
    "WaitlistStatus",
]