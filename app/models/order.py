"""Order model for order management."""
from sqlalchemy import Column, String, Float, ForeignKey, Integer, JSON, Enum as SQLEnum, Text, DateTime
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class OrderStatus(str, enum.Enum):
    """Order lifecycle status."""
    PENDING = "pending"  # Just created
    CONFIRMED = "confirmed"  # Payment received or confirmed
    PREPARING = "preparing"  # Kitchen is making it
    READY = "ready"  # Ready for pickup/serving
    COMPLETED = "completed"  # Delivered to customer
    CANCELLED = "cancelled"  # Cancelled by customer or business


class PaymentStatus(str, enum.Enum):
    """Payment status."""
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    """How customer will pay."""
    ONLINE = "online"  # Stripe/card payment
    CASH = "cash"  # Pay at counter
    WALLET = "wallet"  # Digital wallet


class Order(BaseModel):
    """
    Customer orders.
    
    Contains all information about what was ordered,
    by whom, and its current status.
    """
    __tablename__ = "orders"
    
    # Multi-tenant
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Customer info
    customer_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL")
    )
    customer_name = Column(String(255))  # For guest orders
    customer_phone = Column(String(20))
    customer_email = Column(String(255))
    
    # Table/Location
    table_id = Column(
        Integer,
        ForeignKey("tables.id", ondelete="SET NULL")
    )
    order_type = Column(String(20), default="dine-in")  # dine-in, takeout, delivery
    
    # Scheduled orders and delivery
    scheduled_time = Column(DateTime(timezone=True))  # For future orders
    delivery_address = Column(Text)  # For delivery orders
    delivery_instructions = Column(Text)  # Special delivery instructions
    
    # Order details
    items = Column(JSON, nullable=False)
    # Example: [
    #   {
    #     "item_id": 1,
    #     "name": "Cappuccino",
    #     "quantity": 2,
    #     "unit_price": 4.50,
    #     "customizations": {"size": "Large", "milk": "Oat"},
    #     "subtotal": 9.00
    #   }
    # ]
    
    subtotal = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0)
    tip_amount = Column(Float, default=0)
    total_amount = Column(Float, nullable=False)
    
    # Status
    status = Column(
        SQLEnum(OrderStatus),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True
    )
    payment_status = Column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False
    )
    payment_method = Column(SQLEnum(PaymentMethod))
    
    # Additional info
    special_instructions = Column(Text)
    estimated_ready_time = Column(DateTime(timezone=True))
    
    # Chat context
    session_id = Column(String(50), index=True)  # Links to chat conversation
    
    # Relationships
    business = relationship("Business", back_populates="orders")
    customer = relationship("User", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    
    def __repr__(self):
        return f"<Order #{self.id} - {self.status} - ${self.total_amount}>"