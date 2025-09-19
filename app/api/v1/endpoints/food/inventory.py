"""Food inventory management endpoints for AI integration."""
from typing import Any, List, Optional, Dict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator

from app.config.database import get_supabase_client
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User
from app.services.websocket.connection_manager import manager

router = APIRouter()


class InventoryItem(BaseModel):
    """Inventory item response."""
    id: int
    name: str
    current_stock: int
    min_threshold: int
    is_low_stock: bool
    is_out_of_stock: bool
    last_updated: Optional[str] = None


class InventoryUpdate(BaseModel):
    """Inventory update request."""
    stock_quantity: int = Field(..., ge=0, description="New stock quantity (must be >= 0)")
    min_stock_threshold: Optional[int] = Field(None, ge=0, description="Minimum stock threshold (must be >= 0)")


class LowStockItem(BaseModel):
    """Low stock item response."""
    item_id: int
    item_name: str
    current_stock: int
    threshold: int
    days_since_last_order: Optional[int] = None


class ReorderRequest(BaseModel):
    """Reorder request."""
    item_id: int = Field(..., gt=0, description="Menu item ID (must be > 0)")
    quantity: int = Field(..., gt=0, le=10000, description="Reorder quantity (1-10000)")
    supplier: Optional[str] = Field(None, max_length=100, description="Supplier name")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        """Ensure reorder quantity is reasonable."""
        if v > 10000:
            raise ValueError('Reorder quantity cannot exceed 10,000 units')
        return v


class UsageTracking(BaseModel):
    """Usage tracking response."""
    item_id: int
    item_name: str
    total_sold: int
    total_revenue: float
    period: str


class UsageFilter(BaseModel):
    """Usage filter parameters."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period: str = "7d"  # 7d, 30d, 90d


@router.get("/items", response_model=List[InventoryItem])
async def get_food_inventory(
    low_stock_only: bool = Query(False, description="Show only low stock items"),
    category_id: Optional[int] = Query(None, description="Filter by category"),
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Get inventory with stock levels for food service.
    """
    try:
        query = supabase.table('menu_items').select('*').eq('business_id', business.id)
        
        if low_stock_only:
            query = query.filter('stock_quantity', 'lte', 'min_stock_threshold')
        
        if category_id:
            query = query.eq('category_id', category_id)
        
        response = query.execute()
        
        if not response.data:
            return []
        
        inventory_items = []
        for item in response.data:
            is_low_stock = item['stock_quantity'] <= item['min_stock_threshold']
            is_out_of_stock = item['stock_quantity'] == 0
            
            inventory_items.append(InventoryItem(
                id=item['id'],
                name=item['name'],
                current_stock=item['stock_quantity'],
                min_threshold=item['min_stock_threshold'],
                is_low_stock=is_low_stock,
                is_out_of_stock=is_out_of_stock,
                last_updated=item.get('updated_at')
            ))
        
        return inventory_items
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get inventory: {str(e)}"
        )


@router.put("/items/{item_id}", response_model=InventoryItem)
async def update_food_inventory(
    item_id: int,
    update_data: InventoryUpdate,
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Update stock quantity for a menu item.
    """
    try:
        # Get current menu item
        item_response = supabase.table('menu_items').select('*').eq('id', item_id).eq('business_id', business.id).execute()
        
        if not item_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )
        
        item = item_response.data[0]
        old_stock = item['stock_quantity']
        
        # Prepare update data
        update_dict = {
            'stock_quantity': update_data.stock_quantity,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if update_data.min_stock_threshold is not None:
            update_dict['min_stock_threshold'] = update_data.min_stock_threshold
        
        # Update availability based on stock
        if update_data.stock_quantity == 0:
            update_dict['is_available'] = False
        elif old_stock == 0 and update_data.stock_quantity > 0:
            update_dict['is_available'] = True
        
        # Update item
        update_response = supabase.table('menu_items').update(update_dict).eq('id', item_id).eq('business_id', business.id).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update inventory item"
            )
        
        updated_item = update_response.data[0]
        
        # Check if stock is now low and send alert
        if (updated_item['stock_quantity'] <= updated_item['min_stock_threshold'] and 
            old_stock > updated_item['min_stock_threshold']):
            
            # Send WebSocket notification
            await manager.broadcast_to_business(
                business_id=business.id,
                message={
                    "type": "low_stock_alert",
                    "item_id": updated_item['id'],
                    "item_name": updated_item['name'],
                    "current_stock": updated_item['stock_quantity'],
                    "threshold": updated_item['min_stock_threshold']
                }
            )
        
        return InventoryItem(
            id=updated_item['id'],
            name=updated_item['name'],
            current_stock=updated_item['stock_quantity'],
            min_threshold=updated_item['min_stock_threshold'],
            is_low_stock=updated_item['stock_quantity'] <= updated_item['min_stock_threshold'],
            is_out_of_stock=updated_item['stock_quantity'] == 0,
            last_updated=updated_item.get('updated_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update inventory: {str(e)}"
        )


@router.get("/low-stock", response_model=List[LowStockItem])
async def get_food_low_stock(
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Get items needing reorder.
    """
    try:
        response = supabase.table('menu_items').select('*').eq('business_id', business.id).filter('stock_quantity', 'lte', 'min_stock_threshold').execute()
        
        if not response.data:
            return []
        
        alerts = []
        for item in response.data:
            alerts.append(LowStockItem(
                item_id=item['id'],
                item_name=item['name'],
                current_stock=item['stock_quantity'],
                threshold=item['min_stock_threshold'],
                days_since_last_order=None  # Could be calculated from order history
            ))
        
        return alerts
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get low stock alerts: {str(e)}"
        )


@router.post("/reorder", response_model=Dict[str, Any])
async def create_reorder_request(
    reorder_request: ReorderRequest,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Create reorder request.
    """
    try:
        # Get menu item
        item_response = supabase.table('menu_items').select('*').eq('id', reorder_request.item_id).eq('business_id', business.id).execute()
        
        if not item_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )
        
        item = item_response.data[0]
        
        # In a real implementation, this would create a purchase order
        # For now, we'll just log the request and send a notification
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "reorder_request",
                "item_id": item['id'],
                "item_name": item['name'],
                "quantity": reorder_request.quantity,
                "requested_by": current_user.email if hasattr(current_user, 'email') and current_user.email else getattr(current_user, 'phone', 'Unknown'),
                "supplier": reorder_request.supplier,
                "notes": reorder_request.notes
            }
        )
        
        return {
            "message": f"Reorder request created for {reorder_request.quantity} units of {item['name']}",
            "item_id": item['id'],
            "item_name": item['name'],
            "requested_quantity": reorder_request.quantity
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reorder request: {str(e)}"
        )


@router.get("/usage", response_model=List[UsageTracking])
async def track_ingredient_usage(
    period: str = Query("7d", description="Period to track usage (7d, 30d, 90d)"),
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Track ingredient usage.
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        if period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=7)
        
        # Get completed orders in the period
        orders_response = supabase.table('orders').select('*').eq('business_id', business.id).gte('created_at', start_date.isoformat()).lte('created_at', end_date.isoformat()).in_('status', ['completed', 'delivered']).execute()
        
        # Track usage by item
        usage_stats = {}
        
        if orders_response.data:
            for order in orders_response.data:
                # Parse order items (assuming they're stored as JSON)
                items = order.get('items', [])
                if isinstance(items, str):
                    import json
                    try:
                        items = json.loads(items)
                    except:
                        items = []
                
                for item in items:
                    item_id = item.get('menu_item_id') or item.get('id')
                    item_name = item.get('name')
                    quantity = item.get('quantity', 1)
                    price = item.get('price', 0)
                    
                    if item_id not in usage_stats:
                        usage_stats[item_id] = {
                            "name": item_name,
                            "total_sold": 0,
                            "total_revenue": 0.0
                        }
                    
                    usage_stats[item_id]["total_sold"] += quantity
                    usage_stats[item_id]["total_revenue"] += quantity * price
        
        # Convert to response format
        usage_tracking = []
        for item_id, stats in usage_stats.items():
            usage_tracking.append(UsageTracking(
                item_id=item_id,
                item_name=stats["name"],
                total_sold=stats["total_sold"],
                total_revenue=round(stats["total_revenue"], 2),
                period=period
            ))
        
        # Sort by total sold descending
        usage_tracking.sort(key=lambda x: x.total_sold, reverse=True)
        
        return usage_tracking
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track ingredient usage: {str(e)}"
        )
