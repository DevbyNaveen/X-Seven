"""QR code generation and management endpoints."""
from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import io
import base64
import json
import logging

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, Table, MenuItem
from app.services.utils.qr_generator import QRCodeGenerator
from app.schemas.qr_codes import (
    QRCodeCreate,
    QRCodeResponse,
    QRCodeType,
    QRCodeTemplate,
    QRCodeAnalytics
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate", response_model=QRCodeResponse)
async def generate_qr_code(
    qr_data: QRCodeCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Generate a QR code for various purposes.
    """
    qr_generator = QRCodeGenerator()
    
    try:
        # Generate QR code based on type
        if qr_data.type == QRCodeType.TABLE:
            qr_code_data = await generate_table_qr_code(qr_data, business, db)
        elif qr_data.type == QRCodeType.MENU:
            qr_code_data = await generate_menu_qr_code(qr_data, business, db)
        elif qr_data.type == QRCodeType.BUSINESS_CARD:
            qr_code_data = await generate_business_card_qr_code(qr_data, business)
        elif qr_data.type == QRCodeType.ORDER:
            qr_code_data = await generate_order_qr_code(qr_data, business)
        elif qr_data.type == QRCodeType.CUSTOM:
            qr_code_data = qr_data.custom_data
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported QR code type: {qr_data.type}"
            )
        
        # Generate QR code image
        qr_image = qr_generator.generate_qr_code(
            data=qr_code_data,
            size=qr_data.size,
            color=qr_data.color,
            background_color=qr_data.background_color,
            logo_url=qr_data.logo_url
        )
        
        # Convert to base64
        img_buffer = io.BytesIO()
        qr_image.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        
        return QRCodeResponse(
            id=f"qr_{datetime.utcnow().timestamp()}",
            type=qr_data.type,
            data=qr_code_data,
            image_base64=img_str,
            size=qr_data.size,
            color=qr_data.color,
            background_color=qr_data.background_color,
            created_at=datetime.utcnow(),
            business_id=business.id
        )
        
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating QR code: {str(e)}"
        )


async def generate_table_qr_code(qr_data: QRCodeCreate, business: Business, db: Session) -> str:
    """Generate QR code data for table."""
    if not qr_data.table_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table ID is required for table QR codes"
        )
    
    table = db.query(Table).filter(
        Table.id == qr_data.table_id,
        Table.business_id == business.id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Create table-specific URL
    base_url = f"https://x-sevenai.ai/chat/{business.slug}"
    table_url = f"{base_url}?table_id={table.id}&business_id={business.id}"
    
    return json.dumps({
        "type": "table",
        "business_id": business.id,
        "business_name": business.name,
        "table_id": table.id,
        "table_number": table.number,
        "url": table_url,
        "timestamp": datetime.utcnow().isoformat()
    })


async def generate_menu_qr_code(qr_data: QRCodeCreate, business: Business, db: Session) -> str:
    """Generate QR code data for menu."""
    # Create menu URL
    base_url = f"https://x-sevenai.ai/menu/{business.slug}"
    menu_url = f"{base_url}?business_id={business.id}"
    
    return json.dumps({
        "type": "menu",
        "business_id": business.id,
        "business_name": business.name,
        "url": menu_url,
        "timestamp": datetime.utcnow().isoformat()
    })


async def generate_business_card_qr_code(qr_data: QRCodeCreate, business: Business) -> str:
    """Generate QR code data for business card."""
    # Create business card data
    business_data = {
        "type": "business_card",
        "business_id": business.id,
        "business_name": business.name,
        "description": business.description,
        "contact_info": business.contact_info,
        "website": business.settings.get("website"),
        "social_media": business.settings.get("social_media", {}),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return json.dumps(business_data)


async def generate_order_qr_code(qr_data: QRCodeCreate, business: Business) -> str:
    """Generate QR code data for order tracking."""
    if not qr_data.order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order ID is required for order QR codes"
        )
    
    # Create order tracking URL
    base_url = f"https://x-sevenai.ai/order/{business.slug}"
    order_url = f"{base_url}?order_id={qr_data.order_id}&business_id={business.id}"
    
    return json.dumps({
        "type": "order",
        "business_id": business.id,
        "business_name": business.name,
        "order_id": qr_data.order_id,
        "url": order_url,
        "timestamp": datetime.utcnow().isoformat()
    })


@router.get("/templates", response_model=List[QRCodeTemplate])
async def get_qr_code_templates(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get available QR code templates.
    """
    templates = [
        QRCodeTemplate(
            id="table_standard",
            name="Standard Table QR",
            description="QR code for table ordering",
            type=QRCodeType.TABLE,
            size=256,
            color="#000000",
            background_color="#FFFFFF",
            logo_url=None,
            preview_url="/api/v1/qr-codes/preview/table_standard"
        ),
        QRCodeTemplate(
            id="table_premium",
            name="Premium Table QR",
            description="QR code with business logo",
            type=QRCodeType.TABLE,
            size=512,
            color="#1F2937",
            background_color="#F9FAFB",
            logo_url=f"/api/v1/business/{business.id}/logo",
            preview_url="/api/v1/qr-codes/preview/table_premium"
        ),
        QRCodeTemplate(
            id="menu_standard",
            name="Menu QR Code",
            description="QR code for digital menu",
            type=QRCodeType.MENU,
            size=256,
            color="#000000",
            background_color="#FFFFFF",
            logo_url=None,
            preview_url="/api/v1/qr-codes/preview/menu_standard"
        ),
        QRCodeTemplate(
            id="business_card",
            name="Business Card QR",
            description="QR code for business contact info",
            type=QRCodeType.BUSINESS_CARD,
            size=256,
            color="#000000",
            background_color="#FFFFFF",
            logo_url=f"/api/v1/business/{business.id}/logo",
            preview_url="/api/v1/qr-codes/preview/business_card"
        )
    ]
    
    return templates


@router.get("/tables/{table_id}")
async def get_table_qr_code(
    table_id: int,
    template_id: str = "table_standard",
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Generate QR code for a specific table.
    """
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.business_id == business.id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Get template
    templates = await get_qr_code_templates(db, business)
    template = next((t for t in templates if t.id == template_id), templates[0])
    
    # Generate QR code
    qr_data = QRCodeCreate(
        type=QRCodeType.TABLE,
        table_id=table_id,
        size=template.size,
        color=template.color,
        background_color=template.background_color,
        logo_url=template.logo_url
    )
    
    return await generate_qr_code(qr_data, db, business)


@router.get("/menu")
async def get_menu_qr_code(
    template_id: str = "menu_standard",
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Generate QR code for the business menu.
    """
    # Get template
    templates = await get_qr_code_templates(db, business)
    template = next((t for t in templates if t.id == template_id), templates[0])
    
    # Generate QR code
    qr_data = QRCodeCreate(
        type=QRCodeType.MENU,
        size=template.size,
        color=template.color,
        background_color=template.background_color,
        logo_url=template.logo_url
    )
    
    return await generate_qr_code(qr_data, db, business)


@router.get("/business-card")
async def get_business_card_qr_code(
    template_id: str = "business_card",
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Generate QR code for business card.
    """
    # Get template
    templates = await get_qr_code_templates(db, business)
    template = next((t for t in templates if t.id == template_id), templates[0])
    
    # Generate QR code
    qr_data = QRCodeCreate(
        type=QRCodeType.BUSINESS_CARD,
        size=template.size,
        color=template.color,
        background_color=template.background_color,
        logo_url=template.logo_url
    )
    
    return await generate_qr_code(qr_data, db, business)


@router.get("/bulk-generate")
async def bulk_generate_qr_codes(
    type: QRCodeType,
    template_id: str = "table_standard",
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Bulk generate QR codes for multiple items (e.g., all tables).
    """
    if type == QRCodeType.TABLE:
        tables = db.query(Table).filter(Table.business_id == business.id).all()
        
        qr_codes = []
        for table in tables:
            qr_data = QRCodeCreate(
                type=QRCodeType.TABLE,
                table_id=table.id,
                size=256,
                color="#000000",
                background_color="#FFFFFF"
            )
            
            try:
                qr_code = await generate_qr_code(qr_data, db, business)
                qr_codes.append({
                    "table_id": table.id,
                    "table_number": table.number,
                    "qr_code": qr_code
                })
            except Exception as e:
                logger.error(f"Error generating QR code for table {table.id}: {e}")
        
        return {
            "total_tables": len(tables),
            "qr_codes_generated": len(qr_codes),
            "qr_codes": qr_codes
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bulk generation not supported for type: {type}"
        )


@router.get("/analytics", response_model=QRCodeAnalytics)
async def get_qr_code_analytics(
    time_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get QR code usage analytics.
    """
    # Calculate date range
    end_date = datetime.utcnow()
    if time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    elif time_range == "90d":
        start_date = end_date - timedelta(days=90)
    else:  # 1y
        start_date = end_date - timedelta(days=365)
    
    # Mock analytics data - in real implementation, track QR code scans
    analytics = {
        "total_scans": 1250,
        "unique_scanners": 890,
        "scans_by_type": {
            "table": 800,
            "menu": 300,
            "business_card": 100,
            "order": 50
        },
        "scans_by_table": [
            {"table_id": 1, "table_number": "A1", "scans": 45},
            {"table_id": 2, "table_number": "A2", "scans": 38},
            {"table_id": 3, "table_number": "B1", "scans": 42}
        ],
        "conversion_rate": 0.68,  # 68% of scans led to orders
        "average_session_duration": 180,  # seconds
        "time_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }
    
    return QRCodeAnalytics(**analytics)


@router.get("/download/{qr_id}")
async def download_qr_code(
    qr_id: str,
    format: str = Query("png", regex="^(png|svg|pdf)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Download QR code in various formats.
    """
    # In real implementation, retrieve QR code data and generate download
    qr_generator = QRCodeGenerator()
    
    # Mock QR code data
    qr_data = json.dumps({
        "type": "table",
        "business_id": business.id,
        "table_id": 1,
                    "url": f"https://x-sevenai.ai/chat/{business.slug}?table_id=1"
    })
    
    if format == "png":
        qr_image = qr_generator.generate_qr_code(qr_data)
        img_buffer = io.BytesIO()
        qr_image.save(img_buffer, format='PNG')
        return {
            "format": "png",
            "data": base64.b64encode(img_buffer.getvalue()).decode(),
            "filename": f"qr_code_{qr_id}.png"
        }
    elif format == "svg":
        svg_data = qr_generator.generate_qr_code_svg(qr_data)
        return {
            "format": "svg",
            "data": svg_data,
            "filename": f"qr_code_{qr_id}.svg"
        }
    else:  # pdf
        pdf_data = qr_generator.generate_qr_code_pdf(qr_data)
        return {
            "format": "pdf",
            "data": base64.b64encode(pdf_data).decode(),
            "filename": f"qr_code_{qr_id}.pdf"
        }


@router.post("/custom")
async def create_custom_qr_code(
    data: str,
    size: int = 256,
    color: str = "#000000",
    background_color: str = "#FFFFFF",
    logo_url: Optional[str] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Create a custom QR code with any data.
    """
    qr_generator = QRCodeGenerator()
    
    try:
        qr_image = qr_generator.generate_qr_code(
            data=data,
            size=size,
            color=color,
            background_color=background_color,
            logo_url=logo_url
        )
        
        # Convert to base64
        img_buffer = io.BytesIO()
        qr_image.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        
        return {
            "id": f"custom_qr_{datetime.utcnow().timestamp()}",
            "data": data,
            "image_base64": img_str,
            "size": size,
            "color": color,
            "background_color": background_color,
            "created_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating custom QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating custom QR code: {str(e)}"
        )
