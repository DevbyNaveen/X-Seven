"""
Database models package.

This file makes it easy to import all models at once.
It also ensures all models are registered with SQLAlchemy.
"""
from app.models.base import BaseModel, Base
from app.models.business import Business, SubscriptionPlan, PhoneNumberType, BusinessCategory
from app.models.user import User, UserRole
from app.models.menu import MenuCategory, MenuItem
from app.models.table import Table, TableStatus
from app.models.order import Order, OrderStatus, PaymentStatus, PaymentMethod
from app.models.message import Message 
from app.models.phone_number import PhoneNumber, NumberStatus, NumberProvider
from app.models.waitlist import WaitlistEntry
from app.models.service_provider import ServiceProvider, ProviderType
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType

# Export all models
__all__ = [
    # Base
    "BaseModel",
    "Base",
    
    # Business
    "Business",
    "SubscriptionPlan",
    "PhoneNumberType",
    "BusinessCategory",
    
    # User
    "User", 
    "UserRole",
    
    # Menu
    "MenuCategory",
    "MenuItem",
    
    # Table
    "Table",
    "TableStatus",
    
    # Order
    "Order",
    "OrderStatus",
    "PaymentStatus",
    "PaymentMethod",

    # Message
    "Message",
    
    # Phone Number
    "PhoneNumber",
    "NumberStatus",
    "NumberProvider",
    
    # Waitlist
    "WaitlistEntry",
    
    # Service Providers
    "ServiceProvider",
    "ProviderType",
    
    # Appointments
    "Appointment",
    "AppointmentStatus",
    "AppointmentType",
]