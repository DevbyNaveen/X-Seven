"""Service Provider model for appointment-based businesses."""
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, JSON, Enum as SQLEnum, Time, DateTime
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class ProviderType(str, enum.Enum):
    """Types of service providers."""
    STYLIST = "stylist"  # Hair, nails, beauty
    MECHANIC = "mechanic"  # Auto repair
    DOCTOR = "doctor"  # Medical professionals
    TECHNICIAN = "technician"  # General service providers
    SPECIALIST = "specialist"  # Specialized services


class ServiceProvider(BaseModel):
    """
    Service providers like stylists, mechanics, doctors.
    
    Used for appointment scheduling and service assignment.
    """
    __tablename__ = "service_providers"
    
    # Multi-tenant
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Basic info
    name = Column(String(255), nullable=False)
    provider_type = Column(SQLEnum(ProviderType), nullable=False)
    
    # Contact info
    email = Column(String(255))
    phone = Column(String(20))
    
    # Availability
    is_active = Column(Boolean, default=True, nullable=False)
    working_hours = Column(JSON, default=dict)
    # Example: {
    #   "monday": {"start": "09:00", "end": "17:00"},
    #   "tuesday": {"start": "09:00", "end": "17:00"},
    #   "wednesday": {"start": "09:00", "end": "17:00"},
    #   "thursday": {"start": "09:00", "end": "17:00"},
    #   "friday": {"start": "09:00", "end": "17:00"},
    #   "saturday": {"start": "10:00", "end": "16:00"},
    #   "sunday": {"start": null, "end": null}
    # }
    
    # Specializations
    specializations = Column(JSON, default=list)
    # Example: ["hair_coloring", "haircuts", "manicures"]
    
    # Service durations (in minutes)
    service_durations = Column(JSON, default=dict)
    # Example: {
    #   "haircut": 30,
    #   "hair_coloring": 120,
    #   "manicure": 45
    # }
    
    # Pricing
    service_pricing = Column(JSON, default=dict)
    # Example: {
    #   "haircut": 25.00,
    #   "hair_coloring": 80.00,
    #   "manicure": 35.00
    # }
    
    # Schedule management
    break_time = Column(Integer, default=15)  # minutes between appointments
    max_appointments_per_day = Column(Integer, default=8)
    
    # Profile
    bio = Column(String(500))
    image_url = Column(String(500))
    experience_years = Column(Integer)
    
    # Relationships
    business = relationship("Business", back_populates="service_providers")
    appointments = relationship("Appointment", back_populates="provider")
    
    def __repr__(self):
        return f"<ServiceProvider {self.name} ({self.provider_type})>"
    
    def is_available_at(self, date, time_slot_minutes: int) -> bool:
        """Check if provider is available for a specific time slot."""
        # This would be implemented with actual availability checking logic
        return True
    
    def get_available_slots(self, date, duration_minutes: int) -> list:
        """Get available time slots for a specific date and duration."""
        # This would be implemented with actual slot calculation logic
        return []
