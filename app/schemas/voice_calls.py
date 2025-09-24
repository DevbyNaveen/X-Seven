"""Voice call system schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from enum import Enum


class VoiceCallStatus(str, Enum):
    """Voice call status."""
    INITIATING = "initiating"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no-answer"
    CANCELLED = "cancelled"


class VoiceCallType(str, Enum):
    """Voice call types."""
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    TRANSFER = "transfer"
    CONFERENCE = "conference"


class VoiceCallDirection(str, Enum):
    """Voice call direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class VoiceCallCreate(BaseSchema):
    """Create a new voice call."""
    phone_number: str
    call_type: VoiceCallType = VoiceCallType.OUTBOUND
    context: Optional[Dict[str, Any]] = None
    priority: str = "normal"  # "low", "normal", "high", "urgent"
    scheduled_at: Optional[datetime] = None


class VoiceCallResponse(BaseSchema):
    """Voice call response."""
    id: str
    status: VoiceCallStatus
    from_number: str
    to_number: str
    duration: int  # seconds
    created_at: datetime
    business_id: int
    call_type: VoiceCallType
    cost: float
    recording_url: Optional[str] = None
    transcription: Optional[str] = None


class VoiceCallHistory(BaseSchema):
    """Voice call history item."""
    id: str
    status: VoiceCallStatus
    from_number: str
    to_number: str
    duration: int
    created_at: datetime
    ended_at: Optional[datetime] = None
    business_id: int
    call_type: VoiceCallType
    cost: float
    recording_url: Optional[str] = None
    transcription: Optional[str] = None


class VoiceCallAnalytics(BaseSchema):
    """Voice call analytics."""
    time_range: str
    total_calls: int
    total_duration: int  # minutes
    average_duration: int  # minutes
    total_cost: float
    calls_by_status: Dict[str, int]
    calls_by_type: Dict[str, int]
    peak_hours: List[Dict[str, Any]]
    call_quality_score: float
    customer_satisfaction: float


class VoiceCallSettings(BaseSchema):
    """Voice call settings."""
    voice_enabled: bool = True
    ai_voice_enabled: bool = True
    human_transfer_enabled: bool = True
    business_hours_only: bool = False
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    timezone: str = "UTC"
    voice_personality: str = "friendly"  # "friendly", "professional", "casual"
    language: str = "en"
    greeting_message: str = "Welcome to {business_name}"
    transfer_message: str = "Transferring you to a human agent"
    recording_enabled: bool = True
    transcription_enabled: bool = True


class VoiceCallRecording(BaseSchema):
    """Voice call recording."""
    call_id: str
    recording_url: str
    duration: int
    file_size: int
    format: str
    created_at: datetime


class VoiceCallTranscription(BaseSchema):
    """Voice call transcription."""
    call_id: str
    transcription: str
    confidence: float
    language: str
    segments: List[Dict[str, Any]]
    sentiment: str
    keywords: List[str]


class VoiceCallTransfer(BaseSchema):
    """Voice call transfer request."""
    call_id: str
    transfer_to: str
    transfer_reason: Optional[str] = None
    transfer_message: Optional[str] = None


class VoiceCallSchedule(BaseSchema):
    """Scheduled voice call."""
    id: str
    phone_number: str
    scheduled_at: datetime
    call_type: VoiceCallType
    context: Optional[Dict[str, Any]] = None
    status: str = "scheduled"  # "scheduled", "completed", "cancelled"
    created_at: datetime


class VoiceCallQuality(BaseSchema):
    """Voice call quality metrics."""
    call_id: str
    audio_quality: float  # 0-1
    connection_stability: float  # 0-1
    latency: int  # milliseconds
    packet_loss: float  # percentage
    jitter: float  # milliseconds
    mos_score: float  # Mean Opinion Score 1-5


class VoiceCallAgent(BaseSchema):
    """Voice call agent information."""
    id: str
    name: str
    phone_number: str
    status: str  # "available", "busy", "offline"
    skills: List[str]
    current_calls: int
    max_calls: int
    average_rating: float


class VoiceCallQueue(BaseSchema):
    """Voice call queue item."""
    id: str
    phone_number: str
    priority: int
    wait_time: int  # seconds
    estimated_wait_time: int  # seconds
    position: int
    created_at: datetime


class VoiceCallCampaign(BaseSchema):
    """Voice call campaign."""
    id: str
    name: str
    description: str
    target_numbers: List[str]
    message_template: str
    call_type: VoiceCallType
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None
    status: str = "draft"  # "draft", "scheduled", "active", "completed", "cancelled"
    created_at: datetime
    total_calls: int = 0
    completed_calls: int = 0
    successful_calls: int = 0


class VoiceCallTemplate(BaseSchema):
    """Voice call template."""
    id: str
    name: str
    description: str
    greeting_message: str
    main_message: str
    closing_message: str
    language: str = "en"
    voice_personality: str = "friendly"
    variables: List[str] = []
    is_active: bool = True


class VoiceCallWebhook(BaseSchema):
    """Voice call webhook event."""
    event_type: str
    call_id: str
    timestamp: datetime
    data: Dict[str, Any]


class VoiceCallBulkOperation(BaseSchema):
    """Bulk voice call operation."""
    operation: str  # "initiate", "schedule", "cancel"
    phone_numbers: List[str]
    template_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    context: Optional[Dict[str, Any]] = None


class VoiceCallReport(BaseSchema):
    """Voice call performance report."""
    call_id: str
    period: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_duration: int
    total_cost: float
    call_quality_score: float
    customer_satisfaction: float
    top_issues: List[str]
    recommendations: List[str]


class VoiceCallIntegration(BaseSchema):
    """Voice call integration settings."""
    provider: str  # "twilio", "vonage", "custom"
    account_sid: Optional[str] = None
    auth_token: Optional[str] = None
    webhook_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: bool = True
    settings: Dict[str, Any] = {}


class VoiceCallAnalyticsSummary(BaseSchema):
    """Voice call analytics summary."""
    total_calls: int
    total_duration: int
    total_cost: float
    average_call_duration: int
    call_success_rate: float
    average_call_quality: float
    peak_calling_hours: List[int]
    most_called_numbers: List[Dict[str, Any]]
    call_trends: Dict[str, Any]


class VoiceCallHealthCheck(BaseSchema):
    """Voice call system health check."""
    service_status: str  # "healthy", "degraded", "down"
    provider_status: str
    active_calls: int
    queue_length: int
    average_response_time: float
    error_rate: float
    last_check: datetime
    issues: List[str] = []
