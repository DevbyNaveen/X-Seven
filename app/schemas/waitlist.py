"""Waitlist schemas for API validation."""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema


class WaitlistEntryBase(BaseSchema):
    """Base waitlist entry fields."""
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_phone: str = Field(..., min_length=10, max_length=20)
    customer_email: Optional[str] = None
    party_size: int = Field(1, ge=1, le=20)
    special_requests: Optional[str] = None
    source: str = "chat"  # chat, phone, walk-in, etc.
    session_id: Optional[str] = None
    preferences: Dict[str, Any] = {}


class WaitlistEntryCreate(WaitlistEntryBase):
    """Create new waitlist entry."""
    pass


class WaitlistEntryUpdate(BaseSchema):
    """Update waitlist entry."""
    estimated_wait_time: Optional[int] = Field(None, ge=0)  # minutes
    priority_score: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    is_notified: Optional[bool] = None
    is_seated: Optional[bool] = None
    special_requests: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class WaitlistEntryResponse(WaitlistEntryBase, IDSchema, TimestampSchema):
    """Waitlist entry response with all fields."""
    business_id: int
    estimated_wait_time: Optional[int]  # minutes
    actual_wait_time: Optional[int]  # minutes
    priority_score: int
    is_active: bool
    is_notified: bool
    is_seated: bool
    joined_at: datetime
    notified_at: Optional[datetime]
    seated_at: Optional[datetime]
    wait_duration: int  # calculated field
    is_overdue: bool  # calculated field
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "business_id": 1,
                "customer_name": "John Doe",
                "customer_phone": "+1234567890",
                "customer_email": "john@example.com",
                "party_size": 2,
                "estimated_wait_time": 15,
                "actual_wait_time": 12,
                "priority_score": 0,
                "is_active": True,
                "is_notified": False,
                "is_seated": False,
                "joined_at": "2024-01-01T10:00:00Z",
                "wait_duration": 12,
                "is_overdue": False
            }
        }


class WaitlistSummary(BaseModel):
    """Summary of waitlist status."""
    total_waiting: int
    average_wait_time: int  # minutes
    estimated_wait_time: int  # minutes for new customers
    longest_wait: int  # minutes
    priority_customers: int  # customers with priority_score > 0


class WaitlistNotification(BaseModel):
    """Notification for table availability."""
    customer_name: str
    customer_phone: str
    estimated_wait_time: int
    message: str
    notification_type: str = "table_ready"  # table_ready, wait_update, etc.
