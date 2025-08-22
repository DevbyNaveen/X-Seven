"""Business schemas."""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from app.models.business import SubscriptionPlan
from app.models.business import SubscriptionPlan, PhoneNumberType


class BusinessBase(BaseSchema):
    """Base business fields."""
    name: str
    slug: str
    description: Optional[str] = None


class BusinessCreate(BusinessBase):
    """Create new business."""
    contact_info: Optional[Dict[str, Any]] = {}
    settings: Optional[Dict[str, Any]] = {}


class BusinessUpdate(BaseSchema):
    """Update business fields."""
    name: Optional[str] = None
    description: Optional[str] = None
    contact_info: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    branding_config: Optional[Dict[str, Any]] = None


class BusinessResponse(BusinessBase, IDSchema, TimestampSchema):
    """Business response with all fields."""
    subscription_plan: SubscriptionPlan
    is_active: bool
    contact_info: Dict[str, Any]
    settings: Dict[str, Any]
    branding_config: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Sunrise Cafe",
                "slug": "sunrise-cafe",
                "description": "Best coffee in town",
                "subscription_plan": "pro",
                "is_active": True,
                "contact_info": {
                    "phone": "+1234567890",
                    "email": "hello@sunrisecafe.com",
                    "address": "123 Main St"
                },
                "settings": {
                    "working_hours": {
                        "mon": "9:00-17:00",
                        "tue": "9:00-17:00"
                    },
                    "languages": ["en", "es"]
                },
                "branding_config": {
                    "primary_color": "#FF6B6B",
                    "logo_url": "https://example.com/logo.png"
                },
                "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z"
                }
            }
        
class BusinessPhoneConfig(BaseModel):
    """Request schema for setting up phone configuration."""
    phone_config: PhoneNumberType
    enable_whatsapp: bool = False

class PhoneProvisioningResponse(BaseModel):
    """Response schema after provisioning a number."""
    business_id: int
    universal_access: bool
    custom_number: Optional[str] = None
    whatsapp_enabled: bool
    monthly_cost: float
    message: str


class BusinessSettings(BaseSchema):
    """Business settings schema."""
    working_hours: Optional[Dict[str, str]] = {}
    languages: Optional[list[str]] = ["en"]
    timezone: Optional[str] = "UTC"
    currency: Optional[str] = "USD"
    tax_rate: Optional[float] = 0.0
    auto_confirm_orders: Optional[bool] = False
    require_phone_verification: Optional[bool] = False





