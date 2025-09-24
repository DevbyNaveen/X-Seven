"""Table schemas for API validation."""
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from app.models.table import TableStatus


class TableBase(BaseSchema):
    """Base table fields."""
    table_number: str = Field(..., min_length=1, max_length=20, description="Table identifier (e.g., 'A1', '5', 'VIP-1')")
    capacity: int = Field(4, gt=0, le=50, description="Maximum number of seats (1-50)")
    section: Optional[str] = Field(None, max_length=50, description="Section or area name")
    location_notes: Optional[str] = Field(None, max_length=200, description="Additional location details")
    
    @field_validator('table_number')
    @classmethod
    def validate_table_number(cls, v):
        """Ensure table number doesn't contain invalid characters."""
        if not v.strip():
            raise ValueError('Table number cannot be empty')
        # Allow alphanumeric, hyphens, and spaces
        import re
        if not re.match(r'^[A-Za-z0-9\s\-]+$', v):
            raise ValueError('Table number can only contain letters, numbers, spaces, and hyphens')
        return v.strip()


class TableCreate(TableBase):
    """Create new table."""
    pass


class TableCreateWithQR(TableBase):
    """Create new table with QR code generation."""
    generate_qr: bool = Field(False, description="Automatically generate QR code for the table")
    qr_size: int = Field(256, ge=64, le=2048, description="QR code size in pixels")
    qr_color: str = Field("#000000", description="QR code color")
    qr_background_color: str = Field("#FFFFFF", description="QR code background color")
    
    @field_validator('qr_color', 'qr_background_color')
    @classmethod
    def validate_qr_hex_color(cls, v):
        """Validate hex color format for QR codes."""
        if not v.startswith('#'):
            raise ValueError('QR color must be in hex format (e.g., #000000)')
        if len(v) != 7:
            raise ValueError('QR color must be 7 characters long (e.g., #000000)')
        try:
            int(v[1:], 16)
        except ValueError:
            raise ValueError('Invalid hex color format')
        return v


class TableUpdate(BaseSchema):
    """Update table fields."""
    table_number: Optional[str] = Field(None, min_length=1, max_length=20)
    capacity: Optional[int] = Field(None, gt=0, le=50)
    section: Optional[str] = Field(None, max_length=50)
    location_notes: Optional[str] = Field(None, max_length=200)
    status: Optional[TableStatus] = None
    
    @field_validator('table_number')
    @classmethod
    def validate_table_number(cls, v):
        """Ensure table number doesn't contain invalid characters."""
        if v is not None:
            if not v.strip():
                raise ValueError('Table number cannot be empty')
            # Allow alphanumeric, hyphens, and spaces
            import re
            if not re.match(r'^[A-Za-z0-9\s\-]+$', v):
                raise ValueError('Table number can only contain letters, numbers, spaces, and hyphens')
            return v.strip()
        return v


class TableResponse(TableBase, IDSchema, TimestampSchema):
    """Table response with all fields."""
    business_id: int
    qr_code_id: str
    qr_code_url: Optional[str]
    status: TableStatus
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "business_id": 1,
                "table_number": "5",
                "capacity": 4,
                "section": "Main Floor",
                "location_notes": "By the window",
                "qr_code_id": "123e4567-e89b-12d3-a456-426614174000",
                "qr_code_url": "https://api.x-sevenai.com/qr/123e4567.png",
                "status": "available",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class QRCodeResponse(BaseModel):
    """QR code generation response."""
    qr_code_id: str
    qr_code_url: str
    chat_url: str