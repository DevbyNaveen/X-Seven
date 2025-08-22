"""Phone number management model."""
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, JSON, Enum as SQLEnum, DateTime
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class NumberStatus(str, enum.Enum):
    """Phone number status."""
    PROVISIONING = "provisioning"  # Being set up
    ACTIVE = "active"  # Ready to use
    SUSPENDED = "suspended"  # Temporarily disabled
    RELEASED = "released"  # Number released back to pool


class NumberProvider(str, enum.Enum):
    """Phone service provider."""
    TWILIO = "twilio"
    WHATSAPP = "whatsapp"
    BOTH = "both"


class PhoneNumber(BaseModel):
    """
    Manages phone numbers assigned to businesses.
    Tracks both universal and custom numbers.
    """
    __tablename__ = "phone_numbers"
    
    # Business relationship
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Number details
    phone_number = Column(String(20), unique=True, nullable=False)
    country_code = Column(String(5), default="+371")  # Latvia
    provider = Column(SQLEnum(NumberProvider), default=NumberProvider.TWILIO)
    
    # Twilio/WhatsApp identifiers
    twilio_sid = Column(String(50))
    whatsapp_id = Column(String(50))
    
    # Configuration
    is_universal = Column(Boolean, default=False)  # Part of universal pool
    is_primary = Column(Boolean, default=False)  # Primary number for business
    status = Column(SQLEnum(NumberStatus), default=NumberStatus.PROVISIONING)
    
    # Features
    capabilities = Column(JSON, default=dict)
    # Example: {
    #   "voice": true,
    #   "sms": true,
    #   "mms": false,
    #   "whatsapp": true
    # }
    
    # Usage limits
    monthly_limit = Column(JSON, default=dict)
    # Example: {
    #   "voice_minutes": 1000,
    #   "sms_count": 5000,
    #   "whatsapp_messages": 10000
    # }
    
    # Activation dates
    activated_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    business = relationship("Business", back_populates="phone_numbers")