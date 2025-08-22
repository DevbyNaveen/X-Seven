"""Table schemas for API validation."""
from typing import Optional
from pydantic import BaseModel 
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from app.models.table import TableStatus


class TableBase(BaseSchema):
    """Base table fields."""
    table_number: str
    capacity: int = 4
    section: Optional[str] = None
    location_notes: Optional[str] = None


class TableCreate(TableBase):
    """Create new table."""
    pass


class TableUpdate(BaseSchema):
    """Update table fields."""
    table_number: Optional[str] = None
    capacity: Optional[int] = None
    section: Optional[str] = None
    location_notes: Optional[str] = None
    status: Optional[TableStatus] = None


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