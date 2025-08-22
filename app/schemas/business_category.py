"""Business category schemas for API validation."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from app.models.business import BusinessCategory


class BusinessCategoryConfig(BaseModel):
    """Configuration for business category setup."""
    category: BusinessCategory
    config: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "category": "food_hospitality",
                "config": {
                    "has_tables": True,
                    "has_kitchen": True,
                    "delivery_available": True,
                    "qr_ordering": True,
                    "reservation_system": True
                }
            }
        }


class ServiceProviderCreate(BaseModel):
    """Create a new service provider."""
    name: str = Field(..., min_length=1, max_length=255)
    provider_type: str = Field(..., description="stylist, mechanic, doctor, technician, specialist")
    email: Optional[str] = None
    phone: Optional[str] = None
    specializations: List[str] = Field(default_factory=list)
    service_durations: Dict[str, int] = Field(default_factory=dict)
    service_pricing: Dict[str, float] = Field(default_factory=dict)
    working_hours: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Sarah Johnson",
                "provider_type": "stylist",
                "email": "sarah@salon.com",
                "phone": "+1234567890",
                "specializations": ["hair_coloring", "haircuts", "manicures"],
                "service_durations": {
                    "haircut": 30,
                    "hair_coloring": 120,
                    "manicure": 45
                },
                "service_pricing": {
                    "haircut": 25.00,
                    "hair_coloring": 80.00,
                    "manicure": 35.00
                },
                "working_hours": {
                    "monday": {"start": "09:00", "end": "17:00"},
                    "tuesday": {"start": "09:00", "end": "17:00"}
                }
            }
        }


class ServiceProviderResponse(ServiceProviderCreate, IDSchema, TimestampSchema):
    """Service provider response."""
    is_active: bool
    image_url: Optional[str] = None


class AppointmentCreate(BaseModel):
    """Create a new appointment."""
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_phone: str = Field(..., min_length=1, max_length=20)
    customer_email: Optional[str] = None
    provider_id: Optional[int] = None
    service_name: str = Field(..., min_length=1, max_length=255)
    service_category: Optional[str] = None
    scheduled_date: str = Field(..., description="ISO date string")
    start_time: str = Field(..., description="ISO datetime string")
    duration_minutes: int = Field(..., gt=0)
    total_amount: float = Field(..., gt=0)
    deposit_amount: float = Field(default=0.0, ge=0)
    notes: Optional[str] = None
    special_requirements: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "customer_name": "John Doe",
                "customer_phone": "+1234567890",
                "customer_email": "john@example.com",
                "provider_id": 1,
                "service_name": "Haircut and Style",
                "service_category": "Hair",
                "scheduled_date": "2024-01-15",
                "start_time": "2024-01-15T14:00:00Z",
                "duration_minutes": 60,
                "total_amount": 45.00,
                "deposit_amount": 10.00,
                "notes": "First time customer"
            }
        }


class AppointmentResponse(AppointmentCreate, IDSchema, TimestampSchema):
    """Appointment response."""
    business_id: int
    customer_id: Optional[int]
    appointment_type: str
    end_time: str
    status: str
    payment_status: str
    deposit_paid: bool
    reminder_sent: bool
    cancelled_at: Optional[str] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None


class CategoryTemplateResponse(BaseModel):
    """Response with category template information."""
    category: BusinessCategory
    template: Dict[str, Any]
    default_services: List[str]
    pricing_tier: str
    features: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "category": "food_hospitality",
                "template": {
                    "has_tables": True,
                    "has_kitchen": True,
                    "delivery_available": True
                },
                "default_services": ["Dine-in", "Takeout", "Delivery"],
                "pricing_tier": "basic",
                "features": ["QR Ordering", "Table Management", "Kitchen Display"]
            }
        }


class BusinessCategoryStats(BaseModel):
    """Statistics for business category."""
    total_businesses: int
    active_businesses: int
    total_orders: int
    total_appointments: int
    total_revenue: float
    average_rating: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_businesses": 150,
                "active_businesses": 142,
                "total_orders": 1250,
                "total_appointments": 890,
                "total_revenue": 45678.90,
                "average_rating": 4.5
            }
        }
