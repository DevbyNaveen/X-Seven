"""Table management endpoints with QR code generation."""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Table, TableStatus, Business
from app.schemas.table import (
    TableCreate,
    TableUpdate,
    TableResponse,
    QRCodeResponse
)
from app.services.utils.qr_generator import QRCodeGenerator

router = APIRouter()


@router.get("/", response_model=List[TableResponse])
async def get_tables(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Get all tables for the business."""
    tables = db.query(Table).filter(
        Table.business_id == business.id
    ).order_by(Table.table_number).all()
    
    return tables


@router.get("/{table_id}", response_model=TableResponse)
async def get_table(
    table_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Get specific table details."""
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.business_id == business.id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    return table


@router.post("/", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    table_data: TableCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Create a new table with QR code.
    
    This automatically generates a unique QR code for the table.
    """
    # Check if table number already exists
    existing = db.query(Table).filter(
        Table.business_id == business.id,
        Table.table_number == table_data.table_number
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Table {table_data.table_number} already exists"
        )
    
    # Create table
    table = Table(
        **table_data.dict(),
        business_id=business.id
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    
    # Generate QR code URL (actual image generation happens on request)
    table.qr_code_url = f"/api/v1/tables/{table.id}/qr"
    db.commit()
    
    return table


@router.put("/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int,
    table_data: TableUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Update table information."""
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.business_id == business.id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Update fields
    update_data = table_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(table, field, value)
    
    db.commit()
    db.refresh(table)
    
    return table


@router.get("/{table_id}/qr")
async def get_table_qr_code(
    table_id: int,
    size: int = 10,  # Size multiplier (10 = 300x300 pixels)
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> StreamingResponse:
    """
    Generate and return QR code image for a table.
    
    The QR code contains a URL that opens the chat interface
    with the table ID pre-populated.
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
    
    # Generate chat URL
    chat_url = f"https://x-sevenai.com/chat?business={business.slug}&table={table.qr_code_id}"
    
    # Generate QR code
    qr_generator = QRCodeGenerator()
    qr_image = qr_generator.generate_qr_code(
        data=chat_url,
        size=size,
        logo_url=business.branding_config.get("logo_url")
    )
    
    # Convert to bytes
    img_byte_arr = io.BytesIO()
    qr_image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return StreamingResponse(
        img_byte_arr,
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=table_{table.table_number}_qr.png"
        }
    )


@router.get("/{table_id}/qr-info", response_model=QRCodeResponse)
async def get_table_qr_info(
    table_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Get QR code information without generating the image."""
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.business_id == business.id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    chat_url = f"https://x-sevenai.com/chat?business={business.slug}&table={table.qr_code_id}"
    
    return QRCodeResponse(
        qr_code_id=table.qr_code_id,
        qr_code_url=f"/api/v1/tables/{table.id}/qr",
        chat_url=chat_url
    )


@router.post("/{table_id}/occupy")
async def occupy_table(
    table_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Mark table as occupied."""
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.business_id == business.id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    table.status = TableStatus.OCCUPIED
    db.commit()
    
    return {"message": f"Table {table.table_number} marked as occupied"}


@router.post("/{table_id}/free")
async def free_table(
    table_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Mark table as available."""
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.business_id == business.id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    table.status = TableStatus.AVAILABLE
    db.commit()
    
    return {"message": f"Table {table.table_number} marked as available"}


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    table_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> None:
    """Delete a table."""
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.business_id == business.id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    db.delete(table)
    db.commit()