"""Waitlist model for managing customer waitlists when tables are full."""
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from app.models.base import BaseModel


class WaitlistEntry(BaseModel):
    """
    Waitlist entries for when tables are full.
    
    Tracks customers waiting for tables and manages
    estimated wait times and notifications.
    """
    __tablename__ = "waitlist_entries"
    
    # Multi-tenant
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Customer info
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_email = Column(String(255))
    party_size = Column(Integer, default=1, nullable=False)
    
    # Waitlist details
    estimated_wait_time = Column(Integer)  # minutes
    actual_wait_time = Column(Integer)  # minutes (calculated when seated)
    priority_score = Column(Integer, default=0)  # For VIP customers or special cases
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_notified = Column(Boolean, default=False)  # Whether customer was notified of table ready
    is_seated = Column(Boolean, default=False)  # Whether customer was seated
    
    # Timing
    joined_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    notified_at = Column(DateTime(timezone=True))  # When table became available
    seated_at = Column(DateTime(timezone=True))  # When customer was seated
    
    # Additional info
    special_requests = Column(Text)  # Any special requests or notes
    source = Column(String(50), default="chat")  # chat, phone, walk-in, etc.
    session_id = Column(String(50))  # Links to chat conversation if applicable
    
    # Preferences (for personalization)
    preferences = Column(JSON, default=dict)
    # Example: {"preferred_table_type": "window", "dietary_restrictions": ["vegetarian"]}
    
    # Relationships
    business = relationship("Business", back_populates="waitlist_entries")
    
    def __repr__(self):
        return f"<WaitlistEntry {self.customer_name} - {self.party_size} people>"
    
    @property
    def wait_duration(self) -> int:
        """Calculate actual wait time in minutes."""
        if self.seated_at and self.joined_at:
            return int((self.seated_at - self.joined_at).total_seconds() / 60)
        elif self.is_active:
            return int((datetime.utcnow() - self.joined_at).total_seconds() / 60)
        return 0
    
    @property
    def is_overdue(self) -> bool:
        """Check if estimated wait time has been exceeded."""
        if not self.estimated_wait_time or not self.is_active:
            return False
        return self.wait_duration > self.estimated_wait_time
    
    def mark_notified(self):
        """Mark customer as notified of table availability."""
        self.is_notified = True
        self.notified_at = datetime.utcnow()
    
    def mark_seated(self):
        """Mark customer as seated."""
        self.is_seated = True
        self.seated_at = datetime.utcnow()
        self.is_active = False
        if self.actual_wait_time is None:
            self.actual_wait_time = self.wait_duration
