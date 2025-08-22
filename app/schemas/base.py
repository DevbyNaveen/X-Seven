"""Base schemas with common patterns."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(
        from_attributes=True,  # Allow creation from ORM models
        populate_by_name=True,  # Allow both field names and aliases
        use_enum_values=True,  # Use enum values instead of names
        validate_assignment=True,  # Validate on assignment
    )


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""
    created_at: datetime
    updated_at: Optional[datetime] = None


class IDSchema(BaseSchema):
    """Schema with ID field."""
    id: int


class BaseResponse(BaseSchema):
    """Base response schema."""
    success: bool = True
    message: Optional[str] = None