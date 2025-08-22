"""Table model for QR code ordering."""
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
import uuid
from app.models.base import BaseModel


class TableStatus(str, enum.Enum):
    """Table availability status."""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"


class Table(BaseModel):
    """
    Physical tables in the cafe.
    
    Each table has a unique QR code that customers scan
    to start ordering.
    """
    __tablename__ = "tables"
    
    # Multi-tenant
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Table identification
    table_number = Column(String(20), nullable=False)  # "1", "A1", "Patio-3"
    capacity = Column(Integer, default=4)
    
    # QR Code
    qr_code_id = Column(
        String(36),
        unique=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False
    )
    qr_code_url = Column(String(500))  # Generated QR code image URL
    
    # Status
    status = Column(
        SQLEnum(TableStatus),
        default=TableStatus.AVAILABLE,
        nullable=False
    )
    
    # Location
    section = Column(String(50))  # "Main Floor", "Patio", "VIP"
    location_notes = Column(String(200))  # "By the window", "Corner booth"
    
    # Relationships
    business = relationship("Business", back_populates="tables")
    orders = relationship("Order", back_populates="table")
    
    def __repr__(self):
        return f"<Table {self.table_number} - {self.status}>"