"""QR code generation schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema, IDSchema
from enum import Enum


class QRCodeType(str, Enum):
    """Types of QR codes."""
    TABLE = "TABLE"          # Changed to uppercase to match frontend
    MENU = "MENU"            # Changed to uppercase to match frontend
    BUSINESS_CARD = "business_card"
    ORDER = "order"
    CUSTOM = "CUSTOM"        # Changed to uppercase to match frontend


class QRCodeCreate(BaseSchema):
    """Create a new QR code."""
    type: QRCodeType
    table_id: Optional[str] = Field(None, description="Table ID for table QR codes")  # Changed from int to str
    order_id: Optional[str] = Field(None, description="Order ID for order QR codes")  # Changed from int to str
    custom_data: Optional[str] = Field(None, max_length=1000, description="Custom data for custom QR codes")
    size: int = Field(256, ge=64, le=2048, description="QR code size in pixels (64-2048)")
    color: str = Field("#000000", description="QR code color (hex format)")
    background_color: str = Field("#FFFFFF", description="Background color (hex format)")
    logo_url: Optional[str] = Field(None, max_length=500, description="Logo URL")
    error_correction: str = Field("M", description="Error correction level")
    
    @field_validator('color', 'background_color')
    @classmethod
    def validate_hex_color(cls, v):
        """Validate hex color format."""
        if not v.startswith('#'):
            raise ValueError('Color must be in hex format (e.g., #000000)')
        if len(v) != 7:
            raise ValueError('Color must be 7 characters long (e.g., #000000)')
        try:
            int(v[1:], 16)
        except ValueError:
            raise ValueError('Invalid hex color format')
        return v
    
    @field_validator('error_correction')
    @classmethod
    def validate_error_correction(cls, v):
        """Validate error correction level."""
        if v not in ['L', 'M', 'Q', 'H']:
            raise ValueError('Error correction must be L, M, Q, or H')
        return v
    
    @field_validator('table_id')
    @classmethod
    def validate_table_id_for_type(cls, v, info):
        """Ensure table_id is provided for table QR codes."""
        qr_type = info.data.get('type')
        if qr_type == QRCodeType.TABLE and v is None:
            raise ValueError('table_id is required for table QR codes')
        return v


class QRCodeResponse(BaseSchema):
    """QR code response."""
    id: str
    type: QRCodeType
    data: str
    image_base64: str
    size: int
    color: str
    background_color: str
    created_at: datetime
    business_id: str  # Changed from int to str for UUID compatibility
    table_id: Optional[str] = None  # Changed from int to str for UUID table IDs
    logo_url: Optional[str] = None  # Added for logo support
    scan_count: Optional[int] = None  # Added for analytics
    last_scanned_at: Optional[datetime] = None  # Added for analytics


class QRCodeTemplate(BaseSchema):
    """QR code template."""
    id: str
    name: str
    description: str
    type: QRCodeType
    size: int
    color: str
    background_color: str
    logo_url: Optional[str] = None
    preview_url: str


class QRCodeAnalytics(BaseSchema):
    """QR code analytics."""
    total_scans: int
    unique_scanners: int
    scans_by_type: Dict[str, int]
    scans_by_table: List[Dict[str, Any]]
    conversion_rate: float
    average_session_duration: int
    time_period: Dict[str, str]


class QRCodeScan(BaseSchema):
    """QR code scan event."""
    qr_code_id: str
    scanner_id: str
    scan_timestamp: datetime
    device_info: Optional[Dict[str, str]] = None
    location: Optional[Dict[str, float]] = None
    user_agent: Optional[str] = None


class QRCodeBatch(BaseSchema):
    """Batch QR code generation."""
    type: QRCodeType
    template_id: str
    items: List[Dict[str, Any]]  # List of items to generate QR codes for
    output_format: str = "png"  # png, svg, pdf


class QRCodeDownload(BaseSchema):
    """QR code download response."""
    format: str
    data: str  # Base64 encoded data
    filename: str
    size_bytes: int


class QRCodeCustomization(BaseSchema):
    """QR code customization options."""
    size: int = 256
    color: str = "#000000"
    background_color: str = "#FFFFFF"
    logo_url: Optional[str] = None
    logo_size: Optional[int] = None
    logo_position: str = "center"  # center, top-left, top-right, bottom-left, bottom-right
    border_width: int = 0
    border_color: str = "#000000"
    corner_radius: int = 0
    shadow: bool = False
    shadow_color: str = "#000000"
    shadow_offset: int = 2


class QRCodeStyle(BaseSchema):
    """QR code style configuration."""
    name: str
    description: str
    size: int
    color: str
    background_color: str
    logo_url: Optional[str] = None
    border_width: int = 0
    border_color: str = "#000000"
    corner_radius: int = 0
    shadow: bool = False
    is_default: bool = False


class QRCodeCampaign(BaseSchema):
    """QR code marketing campaign."""
    id: str
    name: str
    description: str
    qr_code_type: QRCodeType
    template_id: str
    target_audience: str
    start_date: datetime
    end_date: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime
    scan_count: int = 0
    conversion_count: int = 0


class QRCodeTracking(BaseSchema):
    """QR code tracking configuration."""
    qr_code_id: str
    track_scans: bool = True
    track_conversions: bool = True
    track_location: bool = False
    track_device_info: bool = False
    conversion_events: List[str] = []  # List of events that count as conversions
    utm_parameters: Optional[Dict[str, str]] = None


class QRCodeExport(BaseSchema):
    """QR code export configuration."""
    format: str = "zip"  # zip, pdf, individual
    include_analytics: bool = True
    include_templates: bool = False
    date_range: Optional[Dict[str, datetime]] = None
    qr_codes: List[str] = []  # List of QR code IDs to export


class QRCodeBulkOperation(BaseSchema):
    """Bulk QR code operation."""
    operation: str  # "generate", "update", "delete", "download"
    qr_code_ids: List[str]
    template_id: Optional[str] = None
    customization: Optional[QRCodeCustomization] = None


class QRCodePreview(BaseSchema):
    """QR code preview data."""
    qr_code_id: str
    preview_url: str
    thumbnail_url: str
    size: int
    format: str
    created_at: datetime


class QRCodeValidation(BaseSchema):
    """QR code validation result."""
    qr_code_id: str
    is_valid: bool
    scan_count: int
    last_scan: Optional[datetime] = None
    error_rate: float
    readability_score: float
    recommendations: List[str] = []


class QRCodeIntegration(BaseSchema):
    """QR code integration settings."""
    qr_code_id: str
    integration_type: str  # "webhook", "api", "database"
    webhook_url: Optional[str] = None
    api_key: Optional[str] = None
    database_connection: Optional[Dict[str, str]] = None
    event_types: List[str] = ["scan", "conversion"]
    is_active: bool = True


class QRCodeReport(BaseSchema):
    """QR code performance report."""
    qr_code_id: str
    period: str
    total_scans: int
    unique_scanners: int
    conversion_rate: float
    average_session_duration: int
    top_referrers: List[Dict[str, Any]]
    geographic_distribution: Dict[str, int]
    device_distribution: Dict[str, int]
    time_distribution: Dict[str, int]


class QRCodeTemplateCategory(BaseSchema):
    """QR code template category."""
    id: str
    name: str
    description: str
    templates: List[QRCodeTemplate]
    is_active: bool = True


class QRCodeBulkTemplate(BaseSchema):
    """Bulk QR code template."""
    id: str
    name: str
    description: str
    base_template: QRCodeTemplate
    variations: List[QRCodeCustomization]
    output_format: str = "zip"
    naming_convention: str = "{business_name}_{type}_{index}"


class QRCodeAnalyticsSummary(BaseSchema):
    """QR code analytics summary."""
    total_qr_codes: int
    total_scans: int
    total_conversions: int
    average_conversion_rate: float
    most_popular_type: QRCodeType
    most_popular_template: str
    recent_activity: List[Dict[str, Any]]
    performance_trends: Dict[str, Any]


class QRCodeHealthCheck(BaseSchema):
    """QR code system health check."""
    service_status: str  # "healthy", "degraded", "down"
    qr_codes_generated: int
    qr_codes_scanned: int
    error_rate: float
    average_generation_time: float
    last_check: datetime
    issues: List[str] = []


# Additional schema for food-specific analytics
class FoodQRCodeAnalytics(QRCodeAnalytics):
    """Food-specific QR code analytics."""
    scans_by_food_item: Optional[Dict[str, int]] = None
    average_order_value: Optional[float] = None
    peak_scanning_hours: Optional[List[int]] = None


# QR code update schema
class QRCodeUpdate(BaseSchema):
    """QR code update configuration."""
    size: Optional[int] = None
    color: Optional[str] = None
    background_color: Optional[str] = None
    logo_url: Optional[str] = None
    template_id: Optional[str] = None