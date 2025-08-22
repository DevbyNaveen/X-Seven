"""Base model with common fields."""
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func
from app.config.database import Base


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamps.
    
    These fields are automatically managed:
    - created_at: Set when record is created
    - updated_at: Updated whenever record changes
    """
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),  # Database sets this
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),  # Database updates this
        nullable=True
    )


class BaseModel(Base, TimestampMixin):
    """
    Abstract base model that all models inherit from.
    
    Provides:
    1. Auto-incrementing ID
    2. Timestamp fields
    3. Common methods (we'll add more later)
    """
    __abstract__ = True  # SQLAlchemy won't create a table for this
    
    id = Column(Integer, primary_key=True, index=True)
    
    def dict(self):
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}