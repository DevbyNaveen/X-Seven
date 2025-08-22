"""Order schemas for API validation."""
from typing import Optional, List, Dict, Any
from datetime import datetime
# Make sure field_validator is imported
from pydantic import BaseModel, Field, field_validator 
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from app.models.order import OrderStatus, PaymentStatus, PaymentMethod


class OrderItemSchema(BaseModel):
    """Individual item in an order."""
    item_id: int
    name: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    customizations: Dict[str, Any] = {}
    subtotal: float = Field(gt=0)
    
    # === FIX IS HERE ===
    @field_validator('subtotal')
    @classmethod
    def validate_subtotal(cls, v, info):
        """Ensure subtotal matches quantity * unit_price."""
        # Access the data dictionary through info.data
        quantity = info.data.get('quantity', 0)
        unit_price = info.data.get('unit_price', 0)
        
        expected = quantity * unit_price
        # Allow for small floating point inaccuracies
        if abs(v - expected) > 0.01:
            raise ValueError(f"Subtotal {v} doesn't match quantity * price {expected}")
        return v


class OrderItemCreate(BaseModel):
    """Create order item."""
    item_id: int
    quantity: int = Field(gt=0)
    customizations: Dict[str, Any] = {}


class OrderItemResponse(BaseModel):
    """Order item response."""
    id: int
    item_id: int
    name: str
    quantity: int
    unit_price: float
    customizations: Dict[str, Any]
    subtotal: float


class OrderBase(BaseSchema):
    """Base order fields."""
    table_id: Optional[int] = None
    order_type: str = "dine-in"
    special_instructions: Optional[str] = None


class OrderCreate(OrderBase):
    """Create new order."""
    items: List[OrderItemSchema]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    payment_method: PaymentMethod = PaymentMethod.CASH
    
    # Scheduled orders and delivery
    scheduled_time: Optional[datetime] = None
    delivery_address: Optional[str] = None
    delivery_instructions: Optional[str] = None
    
    @field_validator('items')
    def validate_items(cls, v):
        """Ensure order has at least one item."""
        if not v:
            raise ValueError("Order must have at least one item")
        return v


class OrderUpdate(BaseSchema):
    """Update order status."""
    status: Optional[OrderStatus] = None
    payment_status: Optional[PaymentStatus] = None
    estimated_ready_time: Optional[datetime] = None


class OrderResponse(OrderBase, IDSchema, TimestampSchema):
    """Order response with all fields."""
    business_id: int
    items: List[Dict[str, Any]]
    subtotal: float
    tax_amount: float
    tip_amount: float
    total_amount: float
    status: OrderStatus
    payment_status: PaymentStatus
    payment_method: PaymentMethod
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    session_id: Optional[str]
    estimated_ready_time: Optional[datetime]
    
    # Scheduled orders and delivery
    scheduled_time: Optional[datetime] = None
    delivery_address: Optional[str] = None
    delivery_instructions: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "business_id": 1,
                "table_id": 5,
                "order_type": "dine-in",
                "items": [
                    {
                        "item_id": 1,
                        "name": "Cappuccino",
                        "quantity": 2,
                        "unit_price": 4.50,
                        "customizations": {"size": "Large", "milk": "Oat"},
                        "subtotal": 9.00
                    }
                ],
                "subtotal": 9.00,
                "tax_amount": 0.72,
                "tip_amount": 1.50,
                "total_amount": 11.22,
                "status": "pending",
                "payment_status": "pending",
                "payment_method": "online",
                "created_at": "2024-01-01T10:00:00Z"
            }
        }


class OrderStatusUpdate(BaseModel):
    """WebSocket message for order status updates."""
    status: OrderStatus
    message: Optional[str] = None
    estimated_time: Optional[int] = None  # minutes