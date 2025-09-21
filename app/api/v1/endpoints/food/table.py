"""Food table management endpoints for AI integration."""
from typing import Any, List, Optional, Dict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from app.config.database import get_supabase_client
from app.core.dependencies import get_current_business, get_current_user
from app.models import TableStatus, Business, User, OrderStatus, PaymentStatus, PaymentMethod
from app.schemas.table import TableResponse, TableUpdate, TableCreate
from app.schemas.qr_codes import QRCodeCreate, QRCodeType
from app.services.utils.qr_generator import QRCodeGenerator
from app.services.websocket.connection_manager import manager
import io
import base64
import json

router = APIRouter()


class TableLayoutUpdate(BaseModel):
    """Schema for updating table layout."""
    tables: List[Dict[str, Any]]


class CustomerAssignment(BaseModel):
    """Schema for assigning customer to table."""
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    party_size: int = Field(gt=0, le=20, description="Number of people (1-20)")
    special_requests: Optional[str] = Field(None, max_length=500)
    
    @field_validator('customer_email')
    @classmethod
    def validate_email(cls, v):
        """Validate email format if provided."""
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v
    
    @field_validator('customer_phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate phone format if provided."""
        if v and len(v.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')) < 10:
            raise ValueError('Phone number must be at least 10 digits')
        return v


@router.post("/", response_model=TableResponse)
async def create_table(
    table_data: TableCreate,
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Create a new table for food service.
    """
    try:
        # Check if table number already exists for this business
        existing_response = supabase.table('tables').select('*').eq('business_id', business.id).eq('table_number', table_data.table_number).execute()
        
        if existing_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table number '{table_data.table_number}' already exists for this business"
            )
        
        # Create table data
        table_dict = {
            'business_id': str(business.id),  # Convert UUID to string
            'table_number': table_data.table_number,
            'capacity': table_data.capacity,
            'section': table_data.section,
            'location_notes': table_data.location_notes,
            'status': 'available',  # Default status
            'qr_code_id': None,
            'qr_code_url': None,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Insert table
        response = supabase.table('tables').insert(table_dict).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create table"
            )
        
        created_table = response.data[0]
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "table_created",
                "table_id": str(created_table['id']),  # Convert UUID to string
                "table_number": created_table['table_number']
            }
        )
        
        return created_table
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create table: {str(e)}"
        )


@router.get("/{table_id}/qr", response_model=Dict[str, Any])
async def get_table_qr_code(
    table_id: UUID,
    size: int = Query(256, ge=64, le=2048, description="QR code size in pixels"),
    color: str = Query("#000000", description="QR code color"),
    background_color: str = Query("#FFFFFF", description="QR code background color"),
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Get or generate QR code for a specific table.
    """
    try:
        # Get table
        table_response = supabase.table('tables').select('*').eq('id', table_id).eq('business_id', business.id).execute()
        
        if not table_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found"
            )
        
        table = table_response.data[0]
        
        # Generate QR code
        qr_generator = QRCodeGenerator()
        
        # Create table-specific URL
        base_url = f"https://x-sevenai.com/chat/{business.slug}"
        table_url = f"{base_url}?table_id={table_id}&business_id={business.id}"
        
        # Convert UUIDs to strings for JSON serialization
        qr_data = json.dumps({
            "type": "table",
            "business_id": str(business.id),  # Convert UUID to string
            "business_name": business.name,
            "table_id": str(table_id),       # Convert UUID to string
            "table_number": table['table_number'],
            "url": table_url,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Generate QR code image
        qr_image = qr_generator.generate_qr_code(
            data=qr_data,
            size=size,
            color=color,
            background_color=background_color
        )
        
        # Convert to base64
        img_buffer = io.BytesIO()
        qr_image.save(img_buffer, format='PNG')
        qr_code_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        return {
            "table_id": str(table_id),  # Convert to string for consistency
            "table_number": table['table_number'],
            "qr_code": {
                "id": f"table_{str(table_id)}_qr_{datetime.utcnow().timestamp()}",
                "image_base64": qr_code_base64,
                "data": qr_data,
                "size": size,
                "color": color,
                "background_color": background_color,
                "url": table_url
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate QR code: {str(e)}"
        )


@router.delete("/{table_id}", response_model=Dict[str, Any])
async def delete_table(
    table_id: UUID,
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Delete a table.
    """
    try:
        # Check if table exists and belongs to business
        table_response = supabase.table('tables').select('*').eq('id', table_id).eq('business_id', business.id).execute()
        
        if not table_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found"
            )
        
        table = table_response.data[0]
        
        # Check if table is currently occupied
        if table['status'] == 'occupied':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete table that is currently occupied"
            )
        
        # Check if table has active orders
        orders_response = supabase.table('orders').select('*').eq('table_id', table_id).in_('status', ['pending', 'confirmed', 'preparing', 'ready']).execute()
        
        if orders_response.data and len(orders_response.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete table with active orders. Please complete or cancel all orders first."
            )
        
        # Delete table
        delete_response = supabase.table('tables').delete().eq('id', table_id).eq('business_id', business.id).execute()
        
        if not delete_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete table"
            )
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "table_deleted",
                "table_id": str(table_id),  # Convert UUID to string
                "table_number": table['table_number']
            }
        )
        
        return {
            "message": f"Table {table['table_number']} deleted successfully",
            "table_id": str(table_id)  # Convert UUID to string
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete table: {str(e)}"
        )


@router.get("/", response_model=List[TableResponse])
async def get_food_tables(
    status: Optional[TableStatus] = Query(None, description="Filter by table status"),
    section: Optional[str] = Query(None, description="Filter by section"),
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Get all tables with current status for food service.
    """
    try:
        query = supabase.table('tables').select('*').eq('business_id', business.id)
        
        # Apply filters
        if status:
            query = query.eq('status', status.value)
        
        if section:
            query = query.eq('section', section)
        
        # Order by table number
        response = query.order('table_number').execute()
        
        if response.data:
            return response.data
        return []
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve tables: {str(e)}"
        )


@router.put("/{table_id}/status", response_model=TableResponse)
async def update_table_status(
    table_id: UUID,
    status: TableStatus,
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Update table status.
    """
    try:
        # Get current table
        response = supabase.table('tables').select('*').eq('id', table_id).eq('business_id', business.id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found"
            )
        
        table = response.data[0]
        old_status = table['status']
        
        # Update table status
        update_response = supabase.table('tables').update({
            'status': status.value,
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', table_id).eq('business_id', business.id).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update table status"
            )
        
        updated_table = update_response.data[0]
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "table_status_update",
                "table_id": str(table_id),  # Convert UUID to string
                "table_number": updated_table['table_number'],
                "old_status": old_status,
                "new_status": status.value
            }
        )
        
        return updated_table
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update table status: {str(e)}"
        )


@router.post("/{table_id}/assign", response_model=Dict[str, Any])
async def assign_customer_to_table(
    table_id: UUID,
    assignment: CustomerAssignment,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Assign customer to table and create initial order.
    """
    try:
        # Get table
        table_response = supabase.table('tables').select('*').eq('id', table_id).eq('business_id', business.id).execute()
        
        if not table_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table not found"
            )
        
        table = table_response.data[0]
        
        # Check if table is available
        if table['status'] != 'available':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table is not available (current status: {table['status']})"
            )
        
        # Validate party size against table capacity
        if assignment.party_size > table['capacity']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Party size ({assignment.party_size}) exceeds table capacity ({table['capacity']})"
            )
        
        # Validate customer information - require at least name or phone
        if not assignment.customer_name and not assignment.customer_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either customer name or phone number must be provided"
            )
        
        # Create initial order
        order_data = {
            'business_id': str(business.id),  # Convert UUID to string
            'table_id': str(table_id),       # Convert UUID to string
            'customer_name': assignment.customer_name,
            'customer_phone': assignment.customer_phone,
            'customer_email': assignment.customer_email,
            'order_type': 'dine-in',
            'items': [],
            'subtotal': 0.0,
            'tax_amount': 0.0,
            'tip_amount': 0.0,
            'total_amount': 0.0,
            'status': 'pending',
            'payment_status': 'pending',
            'payment_method': 'cash',
            'special_instructions': assignment.special_requests,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        order_response = supabase.table('orders').insert(order_data).execute()
        
        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order"
            )
        
        order = order_response.data[0]
        
        # Update table status to occupied
        table_update_response = supabase.table('tables').update({
            'status': 'occupied',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', table_id).eq('business_id', business.id).execute()
        
        if not table_update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update table status"
            )
        
        updated_table = table_update_response.data[0]
        
        # Send WebSocket notifications
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "table_assigned",
                "table_id": str(table_id),      # Convert UUID to string
                "table_number": updated_table['table_number'],
                "order_id": str(order['id']),   # Convert UUID to string
                "customer_name": assignment.customer_name
            }
        )
        
        return {
            "message": f"Customer assigned to table {updated_table['table_number']}",
            "table": updated_table,
            "order_id": str(order['id'])  # Convert UUID to string
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign customer to table: {str(e)}"
        )


@router.get("/availability", response_model=Dict[str, Any])
async def check_table_availability(
    section: Optional[str] = Query(None, description="Filter by section"),
    capacity: Optional[int] = Query(None, description="Minimum capacity required"),
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Check table availability.
    """
    try:
        query = supabase.table('tables').select('*').eq('business_id', business.id)
        
        # Apply filters
        if section:
            query = query.eq('section', section)
        
        if capacity:
            query = query.gte('capacity', capacity)
        
        # Get all tables
        response = query.order('table_number').execute()
        
        if not response.data:
            all_tables = []
        else:
            all_tables = response.data
        
        # Categorize by status
        available_tables = [t for t in all_tables if t['status'] == 'available']
        occupied_tables = [t for t in all_tables if t['status'] == 'occupied']
        reserved_tables = [t for t in all_tables if t['status'] == 'reserved']
        maintenance_tables = [t for t in all_tables if t['status'] == 'maintenance']
        
        return {
            "total_tables": len(all_tables),
            "available_count": len(available_tables),
            "occupied_count": len(occupied_tables),
            "reserved_count": len(reserved_tables),
            "maintenance_count": len(maintenance_tables),
            "available_tables": [
                {
                    "id": str(t['id']),  # Convert UUID to string
                    "table_number": t['table_number'],
                    "capacity": t['capacity'],
                    "section": t['section']
                }
                for t in available_tables
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check table availability: {str(e)}"
        )


@router.put("/layout", response_model=Dict[str, Any])
async def update_table_layout(
    layout_update: TableLayoutUpdate,
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Update table layout.
    """
    try:
        updated_tables = []
        
        for table_data in layout_update.tables:
            table_id = table_data.get("id")
            if not table_id:
                continue
                
            # Get table first to verify it exists
            table_response = supabase.table('tables').select('*').eq('id', table_id).eq('business_id', business.id).execute()
            
            if not table_response.data:
                continue
            
            # Prepare update data
            update_data = {'updated_at': datetime.utcnow().isoformat()}
            
            if "section" in table_data:
                update_data['section'] = table_data["section"]
            if "location_notes" in table_data:
                update_data['location_notes'] = table_data["location_notes"]
            if "capacity" in table_data:
                update_data['capacity'] = table_data["capacity"]
            
            # Update table
            update_response = supabase.table('tables').update(update_data).eq('id', table_id).eq('business_id', business.id).execute()
            
            if update_response.data:
                updated_tables.append(update_response.data[0])
        
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
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update table layout: {str(e)}"
        )