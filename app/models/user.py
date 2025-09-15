"""User model for Supabase operations."""
import enum
from typing import Dict, Any, Optional
from datetime import datetime
from app.models.base import SupabaseModel


class UserRole(str, enum.Enum):
    """User roles in the system."""
    CUSTOMER = "customer"  # Can only place orders
    STAFF = "staff"  # Can manage orders
    MANAGER = "manager"  # Can manage menu and staff
    OWNER = "owner"  # Full access to business


class User(SupabaseModel):
    """
    Represents users of the system.
    
    Can be:
    1. Cafe owners/staff (linked to a business)
    2. Customers (may or may not be linked to a business)
    """
    table_name = "users"
    
    # Authentication
    email: str
    phone_number: Optional[str] = None  # For SMS/WhatsApp
    hashed_password: Optional[str] = None  # Null for customers without account
    
    # Profile
    name: Optional[str] = None
    role: str = "customer"
    is_active: bool = True
    is_verified: bool = False
    
    # Multi-tenant relationship
    business_id: Optional[str] = None  # UUID reference to businesses
    
    # Customer preferences (stored as JSON)
    preferences: Dict[str, Any] = {}
    
    # Timestamps (handled by Supabase)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __repr__(self):
        return f"<User {self.email} ({self.role})>"