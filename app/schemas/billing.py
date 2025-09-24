"""Billing and subscription management schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from app.models.business import SubscriptionPlan


class SubscriptionDetails(BaseSchema):
    """Subscription details from Stripe."""
    id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    plan_id: SubscriptionPlan


class UsageMetrics(BaseSchema):
    """Usage metrics for the business."""
    time_range: str
    orders_count: int
    revenue: float
    voice_minutes_used: int
    sms_messages_sent: int
    whatsapp_messages: int
    active_conversations: int


class InvoiceResponse(BaseSchema):
    """Invoice response from Stripe."""
    id: str
    amount_due: float
    currency: str
    due_date: Optional[datetime] = None
    status: str
    invoice_pdf: Optional[str] = None
    hosted_invoice_url: Optional[str] = None


class PaymentMethodResponse(BaseSchema):
    """Payment method response."""
    id: str
    type: str
    last4: Optional[str] = None
    brand: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool = False


class PaymentIntentResponse(BaseSchema):
    """Payment intent response."""
    id: str
    client_secret: str
    amount: float
    currency: str
    status: str


class BillingOverview(BaseSchema):
    """Complete billing overview."""
    business_id: int
    subscription_plan: SubscriptionPlan
    subscription_status: str
    subscription_details: Optional[SubscriptionDetails] = None
    usage_metrics: UsageMetrics
    upcoming_invoice: Optional[InvoiceResponse] = None
    trial_ends_at: Optional[datetime] = None
    is_trial_active: bool


class BillingHistory(BaseSchema):
    """Billing history summary."""
    total_invoices: int
    total_paid: float
    outstanding_balance: float
    last_payment_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None


class PlanUpgradeRequest(BaseSchema):
    """Request to upgrade subscription plan."""
    new_plan: SubscriptionPlan
    payment_method_id: Optional[str] = None
    immediate_upgrade: bool = False


class PlanDowngradeRequest(BaseSchema):
    """Request to downgrade subscription plan."""
    new_plan: SubscriptionPlan
    effective_date: str = "end_of_period"  # "immediate" or "end_of_period"


class PaymentMethodCreate(BaseSchema):
    """Create new payment method."""
    payment_method_id: str
    set_as_default: bool = True


class PaymentMethodUpdate(BaseSchema):
    """Update payment method."""
    set_as_default: bool = False


class UsageAlert(BaseSchema):
    """Usage alert notification."""
    type: str  # "warning", "critical"
    message: str
    current: int
    limit: int
    percentage: float


class UsageAlertsResponse(BaseSchema):
    """Usage alerts response."""
    alerts: List[UsageAlert]
    usage_metrics: UsageMetrics
    plan_limits: Dict[str, int]


class BillingSettings(BaseSchema):
    """Billing settings for the business."""
    auto_renew: bool = True
    payment_reminders: bool = True
    usage_alerts: bool = True
    invoice_delivery: str = "email"  # "email", "postal", "both"
    tax_exempt: bool = False
    currency: str = "usd"


class InvoiceItem(BaseSchema):
    """Individual invoice item."""
    description: str
    quantity: int
    unit_amount: float
    total_amount: float
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class DetailedInvoice(BaseSchema):
    """Detailed invoice with line items."""
    id: str
    number: str
    amount_due: float
    amount_paid: float
    currency: str
    status: str
    due_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    items: List[InvoiceItem]
    subtotal: float
    tax: float
    total: float
    invoice_pdf: Optional[str] = None
    hosted_invoice_url: Optional[str] = None


class SubscriptionUsage(BaseSchema):
    """Detailed subscription usage breakdown."""
    plan: SubscriptionPlan
    period_start: datetime
    period_end: datetime
    usage_breakdown: Dict[str, Dict[str, Any]]
    # Example:
    # {
    #   "voice": {
    #     "used": 450,
    #     "limit": 500,
    #     "percentage": 90.0
    #   },
    #   "sms": {
    #     "used": 800,
    #     "limit": 1000,
    #     "percentage": 80.0
    #   }
    # }


class BillingReport(BaseSchema):
    """Billing report for a specific period."""
    period: str
    start_date: datetime
    end_date: datetime
    total_revenue: float
    total_orders: int
    average_order_value: float
    subscription_revenue: float
    usage_based_charges: float
    refunds: float
    net_revenue: float
    top_revenue_sources: List[Dict[str, Any]]


class PaymentHistory(BaseSchema):
    """Payment history item."""
    id: str
    amount: float
    currency: str
    status: str
    payment_method: str
    created_at: datetime
    description: Optional[str] = None
    invoice_id: Optional[str] = None


class RefundRequest(BaseSchema):
    """Request for a refund."""
    payment_intent_id: str
    amount: Optional[float] = None  # If None, refunds full amount
    reason: str = "requested_by_customer"
    metadata: Optional[Dict[str, str]] = None


class RefundResponse(BaseSchema):
    """Refund response."""
    id: str
    amount: float
    currency: str
    status: str
    reason: str
    created_at: datetime


class TaxCalculation(BaseSchema):
    """Tax calculation for an order."""
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    tax_id: Optional[str] = None
    tax_exempt: bool = False


class BillingWebhook(BaseSchema):
    """Billing webhook event."""
    event_type: str
    event_id: str
    timestamp: datetime
    data: Dict[str, Any]


class SubscriptionMetrics(BaseSchema):
    """Subscription performance metrics."""
    total_subscriptions: int
    active_subscriptions: int
    cancelled_subscriptions: int
    trial_subscriptions: int
    monthly_recurring_revenue: float
    annual_recurring_revenue: float
    average_subscription_value: float
    churn_rate: float
    upgrade_rate: float
    downgrade_rate: float


class PlanComparison(BaseSchema):
    """Plan comparison for upgrade/downgrade."""
    current_plan: SubscriptionPlan
    new_plan: SubscriptionPlan
    price_difference: float
    feature_changes: Dict[str, Dict[str, Any]]
    # Example:
    # {
    #   "voice_minutes": {
    #     "current": 500,
    #     "new": 2000,
    #     "change": "+1500"
    #   },
    #   "custom_phone": {
    #     "current": False,
    #     "new": True,
    #     "change": "Added"
    #   }
    # }


class BillingNotification(BaseSchema):
    """Billing notification settings."""
    payment_reminders: bool = True
    payment_failed: bool = True
    subscription_cancelled: bool = True
    usage_alerts: bool = True
    invoice_ready: bool = True
    trial_ending: bool = True
    email_addresses: List[str] = []
    phone_numbers: List[str] = []


class BillingExport(BaseSchema):
    """Billing data export request."""
    format: str = "csv"  # "csv", "json", "xlsx"
    date_range: Dict[str, datetime]
    include_invoices: bool = True
    include_payments: bool = True
    include_usage: bool = True
    include_subscriptions: bool = True


class BillingAnalytics(BaseSchema):
    """Billing analytics and insights."""
    revenue_trends: List[Dict[str, Any]]
    subscription_growth: List[Dict[str, Any]]
    churn_analysis: Dict[str, Any]
    usage_patterns: Dict[str, Any]
    payment_method_distribution: Dict[str, float]
    top_revenue_customers: List[Dict[str, Any]]
    seasonal_trends: Dict[str, float]


class SubscriptionCreate(BaseSchema):
    """Create subscription."""
    business_id: int
    plan_id: SubscriptionPlan
    payment_method_id: Optional[str] = None
    trial_period_days: Optional[int] = None


class SubscriptionUpdate(BaseSchema):
    """Update subscription."""
    plan_id: Optional[SubscriptionPlan] = None
    cancel_at_period_end: Optional[bool] = None


class SubscriptionResponse(BaseSchema):
    """Subscription response."""
    id: str
    business_id: int
    plan_id: SubscriptionPlan
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    created_at: datetime


class PaymentIntentCreate(BaseSchema):
    """Create payment intent."""
    amount: float
    currency: str = "usd"
    payment_method_id: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
