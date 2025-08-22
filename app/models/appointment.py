"""Appointment model for service-based businesses."""
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, JSON, Enum as SQLEnum, DateTime, Float, Text
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
from app.models.base import BaseModel


class AppointmentStatus(str, enum.Enum):
    """Appointment lifecycle status."""
    SCHEDULED = "scheduled"  # Booked but not yet started
    CONFIRMED = "confirmed"  # Customer confirmed
    IN_PROGRESS = "in_progress"  # Currently happening
    COMPLETED = "completed"  # Service finished
    CANCELLED = "cancelled"  # Cancelled by customer or business
    NO_SHOW = "no_show"  # Customer didn't show up


class AppointmentType(str, enum.Enum):
    """Types of appointments."""
    CONSULTATION = "consultation"  # Initial meeting
    SERVICE = "service"  # Regular service
    EMERGENCY = "emergency"  # Urgent appointment
    FOLLOW_UP = "follow_up"  # Follow-up visit
    MAINTENANCE = "maintenance"  # Regular maintenance


class Appointment(BaseModel):
    """
    Appointments for service-based businesses.
    
    Used for scheduling services with specific providers.
    """
    __tablename__ = "appointments"
    
    # Multi-tenant
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Customer info
    customer_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL")
    )
    customer_name = Column(String(255))  # For guest appointments
    customer_phone = Column(String(20))
    customer_email = Column(String(255))
    
    # Service provider
    provider_id = Column(
        Integer,
        ForeignKey("service_providers.id", ondelete="SET NULL")
    )
    
    # Appointment details
    appointment_type = Column(SQLEnum(AppointmentType), default=AppointmentType.SERVICE)
    service_name = Column(String(255), nullable=False)
    service_category = Column(String(100))  # e.g., "Hair", "Nails", "Maintenance"
    
    # Scheduling
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    
    # Status
    status = Column(
        SQLEnum(AppointmentStatus),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
        index=True
    )
    
    # Payment
    total_amount = Column(Float, nullable=False)
    deposit_amount = Column(Float, default=0.0)
    deposit_paid = Column(Boolean, default=False)
    payment_status = Column(String(50), default="pending")  # pending, paid, refunded
    
    # Additional info
    notes = Column(Text)  # Customer notes
    internal_notes = Column(Text)  # Staff notes
    special_requirements = Column(JSON, default=dict)
    # Example: {
    #   "allergies": ["latex"],
    #   "preferences": ["quiet_room"],
    #   "medical_conditions": ["diabetes"]
    # }
    
    # Reminders
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime(timezone=True))
    
    # Cancellation
    cancelled_at = Column(DateTime(timezone=True))
    cancelled_by = Column(String(50))  # "customer", "business", "system"
    cancellation_reason = Column(String(255))
    
    # Chat context
    session_id = Column(String(50), index=True)  # Links to chat conversation
    
    # Relationships
    business = relationship("Business", back_populates="appointments")
    customer = relationship("User", back_populates="appointments")
    provider = relationship("ServiceProvider", back_populates="appointments")
    
    def __repr__(self):
        return f"<Appointment {self.service_name} - {self.status} - {self.scheduled_date}>"
    
    @property
    def is_upcoming(self) -> bool:
        """Check if appointment is in the future."""
        return self.start_time > datetime.utcnow()
    
    @property
    def is_today(self) -> bool:
        """Check if appointment is today."""
        now = datetime.utcnow()
        return (self.start_time.date() == now.date())
    
    @property
    def is_overdue(self) -> bool:
        """Check if appointment is overdue."""
        return (self.status == AppointmentStatus.SCHEDULED and 
                self.start_time < datetime.utcnow())
    
    def can_be_cancelled(self) -> bool:
        """Check if appointment can be cancelled."""
        # Allow cancellation up to 24 hours before appointment
        from datetime import timedelta
        return (self.status in [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED] and
                self.start_time > datetime.utcnow() + timedelta(hours=24))
    
    def get_reminder_time(self) -> datetime:
        """Get when reminder should be sent (24 hours before)."""
        from datetime import timedelta
        return self.start_time - timedelta(hours=24)
