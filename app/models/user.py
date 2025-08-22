"""User model for authentication and customer data."""
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """User roles in the system."""
    CUSTOMER = "customer"  # Can only place orders
    STAFF = "staff"  # Can manage orders
    MANAGER = "manager"  # Can manage menu and staff
    OWNER = "owner"  # Full access to business


class User(BaseModel):
    """
    Represents users of the system.
    
    Can be:
    1. Cafe owners/staff (linked to a business)
    2. Customers (may or may not be linked to a business)
    """
    __tablename__ = "users"
    
    # Authentication
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone_number = Column(String(20), index=True)  # For SMS/WhatsApp
    hashed_password = Column(String(255))  # Null for customers who order without account
    
    # Profile
    name = Column(String(255))
    role = Column(SQLEnum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False)
    
    # Multi-tenant relationship
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"))
    business = relationship("Business", back_populates="users")
    
    # Customer preferences (stored as JSON)
    preferences = Column(JSON, default=dict)
    # Example: {
    #   "dietary_restrictions": ["vegan", "gluten-free"],
    #   "favorite_items": [1, 2, 3],
    #   "language": "es"
    # }
    
    # Relationships
    orders = relationship("Order", back_populates="customer")
    appointments = relationship("Appointment", back_populates="customer")
    
    def __repr__(self):
        return f"<User {self.email} ({self.role})>"