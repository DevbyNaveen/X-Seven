"""Appointment schemas for API requests and responses."""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    """Schema for creating appointments."""
    customer_name: str = Field(..., description="Customer's full name")
    customer_email: str = Field(..., description="Customer's email address")
    customer_phone: Optional[str] = Field(None, description="Customer's phone number")
    business_id: int = Field(..., description="Business ID for the appointment")
    service_type: str = Field(..., description="Type of service (e.g., haircut, consultation)")
    start_time: str = Field(..., description="Appointment start time in ISO format")
    end_time: Optional[str] = Field(None, description="Appointment end time in ISO format")
    notes: Optional[str] = Field(None, description="Additional notes about the appointment")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_name": "John Doe",
                "customer_email": "john@example.com",
                "customer_phone": "+1234567890",
                "business_id": 1,
                "service_type": "haircut",
                "start_time": "2024-01-15T10:00:00Z",
                "end_time": "2024-01-15T11:00:00Z",
                "notes": "Customer prefers a specific stylist",
                "metadata": {"source": "online_booking"}
            }
        }


class AppointmentResponse(BaseModel):
    """Response schema for appointment operations."""
    appointment_id: str = Field(..., description="Unique appointment identifier")
    status: str = Field(..., description="Appointment status")
    message: str = Field(..., description="Response message")
    estimated_wait_time: Optional[int] = Field(None, description="Estimated wait time in minutes")

    class Config:
        json_schema_extra = {
            "example": {
                "appointment_id": "apt_12345",
                "status": "confirmed",
                "message": "Appointment confirmed successfully",
                "estimated_wait_time": 5
            }
        }
