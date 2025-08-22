"""Booking system schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from enum import Enum


class BookingStatus(str, Enum):
    """Booking status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class BookingSource(str, Enum):
    """Booking sources."""
    WEBSITE = "website"
    PHONE = "phone"
    WALK_IN = "walk_in"
    THIRD_PARTY = "third_party"
    AI_CHAT = "ai_chat"


class BookingCreate(BaseSchema):
    """Create a new booking."""
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    party_size: int
    booking_time: datetime
    duration: int = 120  # minutes
    special_requests: Optional[str] = None
    source: BookingSource = BookingSource.WEBSITE


class BookingUpdate(BaseSchema):
    """Update booking."""
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    party_size: Optional[int] = None
    booking_time: Optional[datetime] = None
    duration: Optional[int] = None
    special_requests: Optional[str] = None
    status: Optional[BookingStatus] = None


class BookingTimeSlot(BaseSchema):
    """Booking time slot."""
    start_time: datetime
    end_time: datetime
    is_available: bool
    table_id: Optional[int] = None


class BookingResponse(BaseSchema):
    """Booking response."""
    id: int
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    party_size: int
    booking_time: datetime
    duration: int
    table_id: Optional[int] = None
    status: BookingStatus
    special_requests: Optional[str] = None
    source: BookingSource
    created_at: datetime
    business_id: int


class BookingHistory(BaseSchema):
    """Booking history item."""
    id: int
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    party_size: int
    booking_time: datetime
    duration: int
    table_id: Optional[int] = None
    status: BookingStatus
    special_requests: Optional[str] = None
    source: BookingSource
    created_at: datetime
    updated_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    business_id: int


class BookingAnalytics(BaseSchema):
    """Booking analytics."""
    time_range: str
    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    no_shows: int
    average_party_size: float
    peak_hours: List[Dict[str, Any]]
    popular_tables: List[Dict[str, Any]]
    booking_sources: Dict[str, int]
    conversion_rate: float


class BookingSettings(BaseSchema):
    """Booking settings."""
    booking_enabled: bool = True
    advance_booking_days: int = 30
    max_party_size: int = 20
    min_party_size: int = 1
    booking_duration: int = 120  # minutes
    auto_confirm: bool = True
    require_confirmation: bool = False
    cancellation_policy: str = "24h"  # "1h", "24h", "48h", "no_refund"
    deposit_required: bool = False
    deposit_amount: float = 0.0
    business_hours_start: str = "09:00"
    business_hours_end: str = "22:00"
    timezone: str = "UTC"


class TableAvailability(BaseSchema):
    """Table availability."""
    table_id: int
    table_number: str
    capacity: int
    available_times: List[str]
    is_available: bool


class WaitlistEntry(BaseSchema):
    """Waitlist entry."""
    id: int
    customer_name: str
    customer_phone: str
    party_size: int
    position: int
    estimated_wait: int  # minutes
    created_at: datetime
    business_id: int


class BookingReminder(BaseSchema):
    """Booking reminder."""
    booking_id: int
    reminder_type: str  # "1h", "24h", "1d"
    sent_at: Optional[datetime] = None
    status: str = "pending"  # "pending", "sent", "failed"


class BookingCalendar(BaseSchema):
    """Booking calendar view."""
    date: str
    total_bookings: int
    bookings: List[Dict[str, Any]]
    time_slots: List[str]


class BookingTemplate(BaseSchema):
    """Booking template."""
    id: str
    name: str
    description: str
    party_size_range: Dict[str, int]
    duration: int
    special_requests_template: Optional[str] = None
    is_active: bool = True


class BookingBulkOperation(BaseSchema):
    """Bulk booking operation."""
    operation: str  # "create", "update", "cancel"
    bookings: List[BookingCreate]
    template_id: Optional[str] = None


class BookingExport(BaseSchema):
    """Booking export configuration."""
    format: str = "csv"  # "csv", "json", "xlsx"
    date_range: Dict[str, datetime]
    include_cancelled: bool = True
    include_completed: bool = True
    fields: List[str] = ["all"]


class BookingReport(BaseSchema):
    """Booking performance report."""
    period: str
    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    no_shows: int
    average_party_size: float
    total_revenue: float
    average_booking_value: float
    peak_booking_hours: List[int]
    popular_tables: List[Dict[str, Any]]
    booking_sources_distribution: Dict[str, float]
    customer_satisfaction: float


class BookingIntegration(BaseSchema):
    """Booking integration settings."""
    provider: str  # "opentable", "resy", "custom"
    api_key: Optional[str] = None
    webhook_url: Optional[str] = None
    sync_enabled: bool = True
    auto_import: bool = False
    settings: Dict[str, Any] = {}


class BookingNotification(BaseSchema):
    """Booking notification settings."""
    email_notifications: bool = True
    sms_notifications: bool = True
    reminder_notifications: bool = True
    confirmation_notifications: bool = True
    cancellation_notifications: bool = True
    staff_notifications: bool = True
    notification_templates: Dict[str, str] = {}


class BookingValidation(BaseSchema):
    """Booking validation result."""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []


class BookingConflict(BaseSchema):
    """Booking conflict information."""
    conflicting_booking_id: int
    conflict_type: str  # "time_overlap", "table_unavailable", "capacity_exceeded"
    conflict_details: Dict[str, Any]
    suggested_alternatives: List[Dict[str, Any]]


class BookingAnalyticsSummary(BaseSchema):
    """Booking analytics summary."""
    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    no_shows: int
    average_party_size: float
    booking_success_rate: float
    average_booking_value: float
    peak_booking_hours: List[int]
    most_popular_tables: List[Dict[str, Any]]
    booking_trends: Dict[str, Any]


class BookingHealthCheck(BaseSchema):
    """Booking system health check."""
    service_status: str  # "healthy", "degraded", "down"
    database_status: str
    integration_status: str
    active_bookings: int
    pending_bookings: int
    waitlist_length: int
    error_rate: float
    last_check: datetime
    issues: List[str] = []
