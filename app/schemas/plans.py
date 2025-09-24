"""Subscription plan schemas."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.schemas.base import BaseSchema


class PlanFeature(BaseModel):
    """Individual feature in a subscription plan."""
    name: str
    description: str
    included: bool


class PlanCreate(BaseModel):
    """Create subscription plan."""
    name: str
    description: str
    price: float
    currency: str = "USD"
    billing_cycle: str = "monthly"
    features: List[PlanFeature]
    limits: Dict[str, int]


class PlanUpdate(BaseModel):
    """Update subscription plan."""
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    billing_cycle: Optional[str] = None
    features: Optional[List[PlanFeature]] = None
    limits: Optional[Dict[str, int]] = None


class PlanLimits(BaseModel):
    """Usage limits for a subscription plan."""
    menu_items: int
    monthly_orders: int
    voice_minutes: int
    sms_messages: int
    whatsapp_messages: int


class PlanResponse(BaseModel):
    """Subscription plan response."""
    id: str
    name: str
    description: str
    price: float
    currency: str = "USD"
    billing_cycle: str = "monthly"
    features: List[PlanFeature]
    limits: Dict[str, int]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "pro",
                "name": "Pro",
                "description": "For growing businesses with custom needs",
                "price": 79.0,
                "currency": "USD",
                "billing_cycle": "monthly",
                "features": [
                    {
                        "name": "Custom Phone Number",
                        "description": "Dedicated business phone number",
                        "included": True
                    }
                ],
                "limits": {
                    "menu_items": -1,
                    "monthly_orders": -1,
                    "voice_minutes": 2000,
                    "sms_messages": 5000,
                    "whatsapp_messages": 10000
                }
            }
        }


class SubscriptionRequest(BaseModel):
    """Request to subscribe to a plan."""
    plan_id: str = Field(..., description="ID of the plan to subscribe to")
    payment_method_id: str = Field(..., description="Stripe payment method ID")

    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": "pro",
                "payment_method_id": "pm_1234567890"
            }
        }


class UsageLimit(BaseModel):
    """Usage limit information."""
    used: int
    limit: int
    remaining: int


class UsageResponse(BaseModel):
    """Usage and limits response."""
    plan: PlanResponse
    usage: Dict[str, UsageLimit]

    class Config:
        json_schema_extra = {
            "example": {
                "plan": {
                    "id": "pro",
                    "name": "Pro",
                    "price": 79.0
                },
                "usage": {
                    "menu_items": {
                        "used": 25,
                        "limit": -1,
                        "remaining": -1
                    },
                    "monthly_orders": {
                        "used": 150,
                        "limit": -1,
                        "remaining": -1
                    }
                }
            }
        }
