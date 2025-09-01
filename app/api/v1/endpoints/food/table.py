"""Food table management endpoints for AI integration."""
from typing import Any, List, Optional, Dict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Table, TableStatus, Business, User, Order, OrderStatus
from app.schemas.table import TableResponse, TableUpdate
from app.services.websocket.connection_manager import manager

router = APIRouter()


class TableLayoutUpdate(BaseModel):
    """Schema for updating table layout."""
    tables: List[Dict[str, Any]]


class CustomerAssignment(BaseModel):
    """Schema for assigning customer to table."""
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    party_size: int = 1
    special_requests: Optional[str] = None


@router.get("/", response_model=List[TableResponse])
async def get_food_tables(
    status: Optional[TableStatus] = Query(None, description="Filter by table status"),
    section: Optional[str] = Query(None, description="Filter by section"),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get all tables with current status for food service.
    """
    query = db.query(Table).filter(Table.business_id == business.id)
    
    # Apply filters
    if status:
        query = query.filter(Table.status == status)
    
    if section:
        query = query.filter(Table.section == section)
    
    # Order by table number
    tables = query.order_by(Table.table_number).all()
    
    return tables


@router.put("/{table_id}/status", response_model=TableResponse)
async def update_table_status(
    table_id: int,
    status: TableStatus,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update table status.
    """
    # Get table
    table = db.query(Table).filter(
        and_(
            Table.id == table_id,
            Table.business_id == business.id
        )
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Update status
    old_status = table.status
    table.status = status
    db.commit()
    db.refresh(table)
    
    # Send WebSocket notification
    await manager.broadcast_to_business(
        business_id=business.id,
        message={
            "type": "table_status_update",
            "table_id": table.id,
            "table_number": table.table_number,
            "old_status": old_status.value,
            "new_status": status.value
        }
    )
    
    return table


@router.post("/{table_id}/assign", response_model=Dict[str, Any])
async def assign_customer_to_table(
    table_id: int,
    assignment: CustomerAssignment,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Assign customer to table and create initial order.
    """
    # Get table
    table = db.query(Table).filter(
        and_(
            Table.id == table_id,
            Table.business_id == business.id
        )
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Check if table is available
    if table.status != TableStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Table is not available (current status: {table.status.value})"
        )
    
    # Create initial order for the table
    from app.models.order import Order, OrderStatus, PaymentStatus, PaymentMethod
    
    order = Order(
        business_id=business.id,
        table_id=table.id,
        customer_name=assignment.customer_name,
        customer_phone=assignment.customer_phone,
        customer_email=assignment.customer_email,
        order_type="dine-in",
        items=[],
        subtotal=0.0,
        tax_amount=0.0,
        tip_amount=0.0,
        total_amount=0.0,
        status=OrderStatus.PENDING,
        payment_status=PaymentStatus.PENDING,
        payment_method=PaymentMethod.CASH,
        special_instructions=assignment.special_requests
    )
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    # Update table status to occupied
    table.status = TableStatus.OCCUPIED
    db.commit()
    db.refresh(table)
    
    # Send WebSocket notifications
    await manager.broadcast_to_business(
        business_id=business.id,
        message={
            "type": "table_assigned",
            "table_id": table.id,
            "table_number": table.table_number,
            "order_id": order.id,
            "customer_name": assignment.customer_name
        }
    )
    
    return {
        "message": f"Customer assigned to table {table.table_number}",
        "table": table,
        "order_id": order.id
    }


@router.get("/availability", response_model=Dict[str, Any])
async def check_table_availability(
    section: Optional[str] = Query(None, description="Filter by section"),
    capacity: Optional[int] = Query(None, description="Minimum capacity required"),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Check table availability.
    """
    query = db.query(Table).filter(Table.business_id == business.id)
    
    # Apply filters
    if section:
        query = query.filter(Table.section == section)
    
    if capacity:
        query = query.filter(Table.capacity >= capacity)
    
    # Get all tables
    all_tables = query.order_by(Table.table_number).all()
    
    # Categorize by status
    available_tables = [t for t in all_tables if t.status == TableStatus.AVAILABLE]
    occupied_tables = [t for t in all_tables if t.status == TableStatus.OCCUPIED]
    reserved_tables = [t for t in all_tables if t.status == TableStatus.RESERVED]
    maintenance_tables = [t for t in all_tables if t.status == TableStatus.MAINTENANCE]
    
    return {
        "total_tables": len(all_tables),
        "available_count": len(available_tables),
        "occupied_count": len(occupied_tables),
        "reserved_count": len(reserved_tables),
        "maintenance_count": len(maintenance_tables),
        "available_tables": [
            {
                "id": t.id,
                "table_number": t.table_number,
                "capacity": t.capacity,
                "section": t.section
            }
            for t in available_tables
        ]
    }


@router.put("/layout", response_model=Dict[str, Any])
async def update_table_layout(
    layout_update: TableLayoutUpdate,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update table layout.
    """
    updated_tables = []
    
    for table_data in layout_update.tables:
        table_id = table_data.get("id")
        if not table_id:
            continue
            
        # Get table
        table = db.query(Table).filter(
            and_(
                Table.id == table_id,
                Table.business_id == business.id
            )
        ).first()
        
        if not table:
            continue
        
        # Update table fields
        if "section" in table_data:
            table.section = table_data["section"]
        if "location_notes" in table_data:
            table.location_notes = table_data["location_notes"]
        if "capacity" in table_data:
            table.capacity = table_data["capacity"]
        
        updated_tables.append(table)
    
    # Commit all changes
    db.commit()
    
    # Refresh all updated tables
    for table in updated_tables:
        db.refresh(table)
    
    # Send WebSocket notification
    await manager.broadcast_to_business(
        business_id=business.id,
        message={
            "type": "table_layout_updated",
            "updated_count": len(updated_tables)
        }
    )
    
    return {
        "message": f"Updated layout for {len(updated_tables)} tables",
        "updated_tables": len(updated_tables)
    }
