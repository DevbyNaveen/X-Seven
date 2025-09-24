"""Notification system schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from enum import Enum


class NotificationType(str, Enum):
    """Notification types."""
    ORDER_CONFIRMATION = "order_confirmation"
    ORDER_READY = "order_ready"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    BOOKING_CONFIRMATION = "booking_confirmation"
    BOOKING_REMINDER = "booking_reminder"
    SYSTEM_ALERT = "system_alert"
    MARKETING = "marketing"


class NotificationChannel(str, Enum):
    """Notification channels."""
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"


class NotificationCreate(BaseSchema):
    """Create a new notification."""
    type: str  # "order_confirmation", "order_ready", "payment_success", etc.
    recipients: List[str]  # List of recipient IDs or phone numbers
    message: str
    channels: List[str] = ["email"]  # "email", "sms", "whatsapp", "push"
    metadata: Optional[Dict[str, Any]] = None
    template_id: Optional[str] = None
    priority: str = "normal"  # "low", "normal", "high", "urgent"


class NotificationUpdate(BaseSchema):
    """Update notification."""
    type: Optional[str] = None
    message: Optional[str] = None
    channels: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    priority: Optional[str] = None


class NotificationResponse(BaseSchema):
    """Notification response."""
    id: str
    type: str
    message: str
    channels: List[str]
    status: str  # "pending", "sent", "delivered", "failed"
    sent_at: datetime
    recipients_count: int
    delivery_status: Optional[Dict[str, str]] = None


class NotificationSettings(BaseSchema):
    """Notification settings for a business."""
    order_notifications: bool = True
    payment_notifications: bool = True
    system_notifications: bool = True
    marketing_notifications: bool = False
    email_enabled: bool = True
    sms_enabled: bool = True
    whatsapp_enabled: bool = False
    push_enabled: bool = True
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    timezone: str = "UTC"


class NotificationTemplate(BaseSchema):
    """Notification template."""
    id: str
    name: str
    description: str
    subject: str
    body: str
    variables: List[str]
    channels: List[str]
    is_active: bool = True


class NotificationHistory(BaseSchema):
    """Notification history item."""
    id: int
    type: str
    message: str
    channels: List[str]
    status: str
    sent_at: datetime
    recipients_count: int
    delivery_status: Dict[str, str]


class NotificationStats(BaseSchema):
    """Notification statistics."""
    total_sent: int
    total_delivered: int
    total_failed: int
    delivery_rate: float
    by_channel: Dict[str, Dict[str, int]]
    by_type: Dict[str, int]
    time_period: Dict[str, str]


class PushNotification(BaseSchema):
    """Push notification data."""
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    image: Optional[str] = None
    action_url: Optional[str] = None
    badge: Optional[int] = None
    sound: Optional[str] = None


class EmailNotification(BaseSchema):
    """Email notification data."""
    subject: str
    body: str
    html_body: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class SMSNotification(BaseSchema):
    """SMS notification data."""
    message: str
    from_number: Optional[str] = None
    media_url: Optional[str] = None


class WhatsAppNotification(BaseSchema):
    """WhatsApp notification data."""
    message: str
    template_name: Optional[str] = None
    template_variables: Optional[Dict[str, str]] = None
    media_url: Optional[str] = None


class NotificationBatch(BaseSchema):
    """Batch notification request."""
    notifications: List[NotificationCreate]
    batch_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class NotificationSchedule(BaseSchema):
    """Scheduled notification."""
    id: str
    notification: NotificationCreate
    scheduled_at: datetime
    status: str = "scheduled"  # "scheduled", "sent", "cancelled"
    created_at: datetime
    sent_at: Optional[datetime] = None


class NotificationDeliveryStatus(BaseSchema):
    """Notification delivery status."""
    notification_id: str
    channel: str
    status: str  # "sent", "delivered", "read", "failed"
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class NotificationPreference(BaseSchema):
    """User notification preferences."""
    user_id: int
    email_enabled: bool = True
    sms_enabled: bool = True
    whatsapp_enabled: bool = False
    push_enabled: bool = True
    order_updates: bool = True
    payment_notifications: bool = True
    marketing_messages: bool = False
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"


class NotificationCampaign(BaseSchema):
    """Marketing notification campaign."""
    id: str
    name: str
    description: str
    target_audience: str  # "all_customers", "new_customers", "vip_customers"
    message: str
    channels: List[str]
    scheduled_at: Optional[datetime] = None
    status: str = "draft"  # "draft", "scheduled", "sent", "cancelled"
    created_at: datetime
    sent_at: Optional[datetime] = None
    recipients_count: Optional[int] = None
    delivery_stats: Optional[Dict[str, Any]] = None


class NotificationWebhook(BaseSchema):
    """Webhook for notification delivery status."""
    notification_id: str
    channel: str
    status: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class NotificationTemplateVariable(BaseSchema):
    """Template variable definition."""
    name: str
    type: str  # "string", "number", "date", "boolean"
    required: bool = False
    default_value: Optional[Any] = None
    description: Optional[str] = None


class NotificationTemplateCreate(BaseSchema):
    """Create a new notification template."""
    name: str
    description: str
    subject: str
    body: str
    variables: List[NotificationTemplateVariable]
    channels: List[str]
    is_active: bool = True


class NotificationTemplateUpdate(BaseSchema):
    """Update notification template."""
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    variables: Optional[List[NotificationTemplateVariable]] = None
    channels: Optional[List[str]] = None
    is_active: Optional[bool] = None


class NotificationQueue(BaseSchema):
    """Notification queue item."""
    id: str
    notification: NotificationCreate
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    scheduled_at: datetime
    created_at: datetime
    status: str = "queued"  # "queued", "processing", "sent", "failed"


class NotificationRetry(BaseSchema):
    """Notification retry configuration."""
    max_retries: int = 3
    retry_delay: int = 300  # seconds
    exponential_backoff: bool = True
    retry_on_failure: List[str] = ["network_error", "rate_limit", "temporary_failure"]


class NotificationAnalytics(BaseSchema):
    """Notification analytics data."""
    total_notifications: int
    successful_deliveries: int
    failed_deliveries: int
    delivery_rate: float
    average_delivery_time: float
    channel_performance: Dict[str, Dict[str, Any]]
    time_based_analysis: Dict[str, Any]
    user_engagement: Dict[str, Any]


class NotificationSegment(BaseSchema):
    """Customer segment for targeted notifications."""
    id: str
    name: str
    description: str
    criteria: Dict[str, Any]
    customer_count: int
    created_at: datetime
    last_updated: datetime


class NotificationAutomation(BaseSchema):
    """Automated notification trigger."""
    id: str
    name: str
    description: str
    trigger_event: str  # "order_placed", "payment_received", "customer_registered"
    conditions: Dict[str, Any]
    notification_template: str
    channels: List[str]
    is_active: bool = True
    created_at: datetime


class NotificationBulkOperation(BaseSchema):
    """Bulk notification operation."""
    operation_type: str  # "send", "schedule", "cancel"
    notification_ids: List[str]
    filters: Optional[Dict[str, Any]] = None
    batch_size: int = 100
    priority: str = "normal"


class NotificationExport(BaseSchema):
    """Notification data export."""
    format: str = "csv"  # "csv", "json", "xlsx"
    date_range: Dict[str, datetime]
    include_delivery_status: bool = True
    include_analytics: bool = True
    filters: Optional[Dict[str, Any]] = None


class NotificationHealthCheck(BaseSchema):
    """Notification system health check."""
    service_status: str  # "healthy", "degraded", "down"
    channels_status: Dict[str, str]
    queue_size: int
    average_processing_time: float
    error_rate: float
    last_check: datetime
    issues: List[str] = []
