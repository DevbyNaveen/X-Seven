"""Customer management schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema


class CustomerPreferences(BaseModel):
    """Customer preferences and settings."""
    dietary_restrictions: Optional[List[str]] = []
    favorite_items: Optional[List[int]] = []
    language: Optional[str] = "en"
    notification_preferences: Optional[Dict[str, bool]] = {
        "email": True,
        "sms": True,
        "whatsapp": False
    }
    special_instructions: Optional[str] = None
    preferred_payment_method: Optional[str] = "card"
    marketing_consent: Optional[bool] = False


class CustomerCreate(BaseSchema):
    """Create new customer."""
    name: str
    email: EmailStr
    phone_number: Optional[str] = None
    preferences: Optional[CustomerPreferences] = None


class CustomerResponse(BaseSchema):
    """Customer response with all fields."""
    id: int
    name: str
    email: str
    phone_number: Optional[str] = None
    is_verified: bool = False
    is_active: bool = True
    preferences: Optional[CustomerPreferences] = None
    total_orders: int = 0
    total_spent: float = 0.0
    last_order: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class CustomerUpdate(BaseSchema):
    """Update customer profile."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None


class CustomerOrderHistory(BaseSchema):
    """Customer order history item."""
    id: int
    items: List[Dict[str, Any]]
    total_amount: float
    status: str
    payment_status: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class CustomerAnalytics(BaseSchema):
    """Customer analytics and behavior insights."""
    customer_id: int
    time_range: str
    total_orders: int
    total_spent: float
    average_order_value: float
    order_frequency: float
    top_ordered_items: List[tuple]
    preferred_order_hours: List[tuple]
    last_order_date: Optional[datetime] = None
    customer_since: datetime


class CustomerProfile(BaseSchema):
    """Complete customer profile with statistics."""
    id: int
    name: str
    email: str
    phone_number: Optional[str] = None
    is_verified: bool
    preferences: Optional[Dict[str, Any]] = {}
    total_orders: int
    total_spent: float
    last_order: Optional[datetime] = None
    created_at: datetime
    is_active: bool


class CustomerSearchResult(BaseSchema):
    """Customer search result."""
    id: int
    name: str
    email: str
    phone_number: Optional[str] = None
    total_orders: int
    total_spent: float
    last_order: Optional[datetime] = None
    is_verified: bool


class CustomerBulkAction(BaseSchema):
    """Bulk customer actions."""
    customer_ids: List[int]
    action: str  # "verify", "deactivate", "send_notification", "export"


class CustomerExport(BaseSchema):
    """Customer data export."""
    format: str = "csv"  # "csv", "json", "xlsx"
    include_orders: bool = True
    include_analytics: bool = True
    date_range: Optional[Dict[str, datetime]] = None


class CustomerNotification(BaseSchema):
    """Customer notification request."""
    customer_ids: List[int]
    message: str
    channel: str = "email"  # "email", "sms", "whatsapp", "all"
    template_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class CustomerSegment(BaseSchema):
    """Customer segmentation criteria."""
    name: str
    criteria: Dict[str, Any]
    # Example criteria:
    # {
    #   "min_orders": 5,
    #   "min_spent": 100,
    #   "last_order_within_days": 30,
    #   "preferred_items": ["coffee", "pastry"],
    #   "location": "downtown"
    # }


class CustomerLoyaltyProgram(BaseSchema):
    """Customer loyalty program settings."""
    points_per_dollar: float = 1.0
    points_redemption_rate: float = 0.01  # $0.01 per point
    minimum_redemption: int = 100
    expiration_days: Optional[int] = 365
    tiers: Optional[Dict[str, Dict[str, Any]]] = {
        "bronze": {"min_points": 0, "discount": 0.05},
        "silver": {"min_points": 500, "discount": 0.10},
        "gold": {"min_points": 1000, "discount": 0.15}
    }


class CustomerFeedback(BaseSchema):
    """Customer feedback and reviews."""
    customer_id: int
    order_id: Optional[int] = None
    rating: int  # 1-5 stars
    comment: Optional[str] = None
    categories: Optional[List[str]] = []  # ["food_quality", "service", "speed", "cleanliness"]
    sentiment: Optional[str] = None  # "positive", "neutral", "negative"


class CustomerRetentionMetrics(BaseSchema):
    """Customer retention and churn metrics."""
    period: str
    total_customers: int
    new_customers: int
    returning_customers: int
    churned_customers: int
    retention_rate: float
    churn_rate: float
    average_lifetime_value: float
    customer_acquisition_cost: Optional[float] = None


class CustomerBehaviorAnalysis(BaseSchema):
    """Customer behavior analysis."""
    customer_id: int
    order_patterns: Dict[str, Any]
    preferred_categories: List[str]
    average_order_value: float
    order_frequency: float
    peak_ordering_hours: List[int]
    seasonal_preferences: Dict[str, float]
    price_sensitivity: str  # "low", "medium", "high"
    loyalty_score: float  # 0-100


class CustomerCommunicationHistory(BaseSchema):
    """Customer communication history."""
    customer_id: int
    communications: List[Dict[str, Any]]
    # Each communication includes:
    # - type: "email", "sms", "whatsapp", "chat"
    # - timestamp: datetime
    # - content: str
    # - status: "sent", "delivered", "read", "failed"
    # - campaign_id: Optional[str]


class CustomerSegmentationReport(BaseSchema):
    """Customer segmentation analysis report."""
    total_customers: int
    segments: Dict[str, Dict[str, Any]]
    # Each segment includes:
    # - count: int
    # - percentage: float
    # - average_order_value: float
    # - retention_rate: float
    # - top_items: List[str]
    # - demographics: Dict[str, Any]


class CustomerPredictiveAnalytics(BaseSchema):
    """Predictive analytics for customer behavior."""
    customer_id: int
    churn_probability: float  # 0-1
    next_order_prediction: Optional[datetime] = None
    predicted_order_value: Optional[float] = None
    lifetime_value_prediction: float
    recommended_actions: List[str]
    risk_factors: List[str]
    opportunity_score: float  # 0-100
