"""
Database models package.

This file makes it easy to import all models at once.
It also ensures all models are registered with Supabase.
"""

from .base import SupabaseModel
from .business import Business, SubscriptionPlan, PhoneNumberType, BusinessCategory
from .user import User, UserRole
from .menu_category import MenuCategory
from .menu_item import MenuItem
from .order import Order, OrderStatus, PaymentStatus, PaymentMethod
from .table import Table, TableStatus
from .phone_number import PhoneNumber, NumberStatus
from .service_provider import ServiceProvider
from .appointment import Appointment
from .waitlist_entry import WaitlistEntry
from .message import Message
from .evolution_instance import (
    EvolutionInstance, 
    EvolutionMessage, 
    EvolutionWebhookEvent,
    InstanceStatus,
    WhatsAppStatus,
    MessageType
)

__all__ = [
    "SupabaseModel",
    "Business",
    "SubscriptionPlan", 
    "PhoneNumberType",
    "BusinessCategory",
    "User",
    "UserRole",
    "MenuCategory",
    "MenuItem", 
    "Order",
    "OrderStatus",
    "PaymentStatus",
    "PaymentMethod",
    "Table",
    "TableStatus",
    "PhoneNumber",
    "NumberStatus",
    "ServiceProvider",
    "Appointment",
    "WaitlistEntry",
    "Message",
    "EvolutionInstance",
    "EvolutionMessage",
    "EvolutionWebhookEvent",
    "InstanceStatus",
    "WhatsAppStatus",
    "MessageType"
]