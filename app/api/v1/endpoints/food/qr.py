"""Food QR code management endpoints for AI integration."""
from typing import Any, List, Dict, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
import io
import base64
import json

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User, Table
from app.services.utils.qr_generator import QRCodeGenerator
from app.schemas.qr_codes import (
    QRCodeCreate,
    QRCodeResponse,
    QRCodeType,
    QRCodeTemplate,
    QRCodeAnalytics,
    QRCodeBatch
)
from app.services.websocket.connection_manager import manager

router = APIRouter()


class QRCodeUpdate(BaseModel):
    """QR code update configuration."""
    size: Optional[int] = None
    color: Optional[str] = None
    background_color: Optional[str] = None
    logo_url: Optional[str] = None
    template_id: Optional[str] = None


class QRCodeFoodTemplate(QRCodeTemplate):
    """Food-specific QR code template."""
    category: str = "food"


class FoodQRCodeAnalytics(QRCodeAnalytics):
    """Food-specific QR code analytics."""
    scans_by_food_item: Optional[Dict[str, int]] = None
    average_order_value: Optional[float] = None
    peak_scanning_hours: Optional[List[int]] = None


@router.get("/", response_model=List[QRCodeResponse])
async def get_food_qr_codes(
    type: Optional[QRCodeType] = Query(None, description="Filter by QR code type"),
    table_id: Optional[int] = Query(None, description="Filter by table ID"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get existing QR codes for food service.
    """
    # In a real implementation, this would query a QR codes table
    # For now, we'll return a mock response showing existing QR codes
    
    # Get tables for this business
    tables = db.query(Table).filter(Table.business_id == business.id).all()
    
    qr_codes = []
    qr_generator = QRCodeGenerator()
    
    # Generate mock QR codes for each table
    for table in tables:
        # Create table-specific URL
        base_url = f"https://x-sevenai.com/chat/{business.slug}"
        table_url = f"{base_url}?table_id={table.id}&business_id={business.id}"
        
        # Generate QR code data
        qr_data = json.dumps({
            "type": "table",
            "business_id": business.id,
            "business_name": business.name,
            "table_id": table.id,
            "table_number": table.table_number,
            "url": table_url,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Generate QR code image
        qr_image = qr_generator.generate_qr_code(qr_data)
        
        # Convert to base64
        img_buffer = io.BytesIO()
        qr_image.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        
        qr_codes.append(QRCodeResponse(
            id=f"table_{table.id}",
            type=QRCodeType.TABLE,
            data=qr_data,
            image_base64=img_str,
            size=256,
            color="#000000",
            background_color="#FFFFFF",
            created_at=table.created_at or datetime.utcnow(),
            business_id=business.id
        ))
    
    # Filter by type if specified
    if type:
        qr_codes = [qr for qr in qr_codes if qr.type == type]
    
    # Filter by table_id if specified
    if table_id:
        qr_codes = [qr for qr in qr_codes if qr.type == QRCodeType.TABLE and f"\"table_id\": {table_id}" in qr.data]
    
    return qr_codes


@router.post("/generate", response_model=QRCodeResponse)
async def generate_food_qr_code(
    qr_data: QRCodeCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Generate new QR codes for food service.
    """
    qr_generator = QRCodeGenerator()
    
    try:
        # Generate QR code based on type
        if qr_data.type == QRCodeType.TABLE:
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
            base_url = f"https://x-sevenai.com/chat/{business.slug}"
            table_url = f"{base_url}?table_id={table.id}&business_id={business.id}"
            
            qr_code_data = json.dumps({
                "type": "table",
                "business_id": business.id,
                "business_name": business.name,
                "table_id": table.id,
                "table_number": table.table_number,
                "url": table_url,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        elif qr_data.type == QRCodeType.MENU:
            # Create menu URL
            base_url = f"https://x-sevenai.com/menu/{business.slug}"
            menu_url = f"{base_url}?business_id={business.id}"
            
            qr_code_data = json.dumps({
                "type": "menu",
                "business_id": business.id,
                "business_name": business.name,
                "url": menu_url,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        elif qr_data.type == QRCodeType.CUSTOM:
            qr_code_data = qr_data.custom_data or ""
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported QR code type for food service: {qr_data.type}"
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
        
        response = QRCodeResponse(
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
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "qr_code_generated",
                "qr_code_id": response.id,
                "qr_code_type": response.type.value
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating QR code: {str(e)}"
        )


@router.get("/batch", response_model=Dict[str, Any])
async def bulk_generate_food_qr_codes(
    type: QRCodeType = Query(QRCodeType.TABLE, description="Type of QR codes to generate"),
    count: int = Query(10, description="Number of QR codes to generate"),
    template_id: str = Query("food_standard", description="Template to use"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Bulk generate QR codes for food service.
    """
    try:
        qr_codes = []
        errors = []
        
        if type == QRCodeType.TABLE:
            # Get tables for this business
            tables = db.query(Table).filter(Table.business_id == business.id).limit(count).all()
            
            for table in tables:
                try:
                    qr_data = QRCodeCreate(
                        type=QRCodeType.TABLE,
                        table_id=table.id,
                        size=256,
                        color="#000000",
                        background_color="#FFFFFF"
                    )
                    
                    qr_code = await generate_food_qr_code(qr_data, db, business)
                    qr_codes.append({
                        "table_id": table.id,
                        "table_number": table.table_number,
                        "qr_code": qr_code
                    })
                except Exception as e:
                    errors.append(f"Error generating QR code for table {table.id}: {str(e)}")
        
        elif type == QRCodeType.MENU:
            try:
                qr_data = QRCodeCreate(
                    type=QRCodeType.MENU,
                    size=256,
                    color="#000000",
                    background_color="#FFFFFF"
                )
                
                qr_code = await generate_food_qr_code(qr_data, db, business)
                qr_codes.append({
                    "type": "menu",
                    "qr_code": qr_code
                })
            except Exception as e:
                errors.append(f"Error generating menu QR code: {str(e)}")
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bulk generation not supported for type: {type}"
            )
        
        return {
            "total_requested": count,
            "qr_codes_generated": len(qr_codes),
            "errors": errors,
            "qr_codes": qr_codes
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in bulk QR code generation: {str(e)}"
        )


@router.get("/{qr_id}/analytics", response_model=FoodQRCodeAnalytics)
async def get_food_qr_analytics(
    qr_id: str,
    time_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get QR code usage stats for food service.
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
        "total_scans": 450,
        "unique_scanners": 320,
        "scans_by_type": {
            "table": 300,
            "menu": 150
        },
        "scans_by_table": [
            {"table_id": 1, "table_number": "A1", "scans": 45},
            {"table_id": 2, "table_number": "A2", "scans": 38},
            {"table_id": 3, "table_number": "B1", "scans": 42}
        ],
        "conversion_rate": 0.72,  # 72% of scans led to orders
        "average_session_duration": 210,  # seconds
        "time_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "scans_by_food_item": {
            "Burger": 120,
            "Pizza": 95,
            "Salad": 75,
            "Pasta": 80,
            "Dessert": 80
        },
        "average_order_value": 24.50,
        "peak_scanning_hours": [12, 13, 18, 19, 20]  # Lunch and dinner hours
    }
    
    return FoodQRCodeAnalytics(**analytics)


@router.put("/{qr_id}", response_model=QRCodeResponse)
async def update_food_qr_code(
    qr_id: str,
    update_data: QRCodeUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update QR code configuration for food service.
    """
    # In a real implementation, this would update the QR code in the database
    # For now, we'll simulate the update by regenerating the QR code
    
    try:
        # Parse the QR ID to determine what type of QR code it is
        # This is a simplified approach - in reality, you'd look up the QR code in a database
        if qr_id.startswith("table_"):
            table_id = int(qr_id.split("_")[1])
            
            # Get the table
            table = db.query(Table).filter(
                Table.id == table_id,
                Table.business_id == business.id
            ).first()
            
            if not table:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Table not found"
                )
            
            # Create QR code data
            qr_data = QRCodeCreate(
                type=QRCodeType.TABLE,
                table_id=table.id,
                size=update_data.size or 256,
                color=update_data.color or "#000000",
                background_color=update_data.background_color or "#FFFFFF",
                logo_url=update_data.logo_url
            )
            
            # Generate new QR code
            response = await generate_food_qr_code(qr_data, db, business)
            
            # Send WebSocket notification
            await manager.broadcast_to_business(
                business_id=business.id,
                message={
                    "type": "qr_code_updated",
                    "qr_code_id": response.id,
                    "table_id": table.id
                }
            )
            
            return response
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported QR code type for update"
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating QR code: {str(e)}"
        )
