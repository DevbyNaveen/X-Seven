"""Food inventory management endpoints for AI integration - FIXED VERSION."""
from typing import Any, List, Optional, Dict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator
import json
import logging

from app.config.database import get_supabase_client
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User
from app.services.websocket.connection_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


class InventoryItem(BaseModel):
    """Inventory item response."""
    id: str  # Changed from int to str for UUID
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
    item_id: str  # Changed from int to str for UUID
    item_name: str
    current_stock: int
    threshold: int
    days_since_last_order: Optional[int] = None


class ReorderRequest(BaseModel):
    """Reorder request."""
    item_id: str = Field(..., description="Menu item ID (UUID)")
    quantity: int = Field(..., gt=0, le=10000, description="Reorder quantity (1-10000)")
    supplier: Optional[str] = Field(None, max_length=100, description="Supplier name")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    
    @field_validator('item_id')
    @classmethod
    def validate_item_id(cls, v):
        """Validate that item_id is a valid UUID string."""
        if not v or len(v.strip()) == 0:
            raise ValueError('item_id cannot be empty')
        return v.strip()
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        """Ensure reorder quantity is reasonable."""
        if v > 10000:
            raise ValueError('Reorder quantity cannot exceed 10,000 units')
        return v


class UsageTracking(BaseModel):
    """Usage tracking response."""
    item_id: str  # Changed from int to str for UUID
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
        logger.info(f"Getting inventory for business {business.id}, low_stock_only: {low_stock_only}")
        
        # Build base query - ALWAYS get all items first
        query = supabase.table('menu_items').select('*').eq('business_id', business.id)
        
        if category_id:
            query = query.eq('category_id', category_id)
        
        response = query.execute()
        logger.info(f"Retrieved {len(response.data) if response.data else 0} menu items")
        
        if not response.data:
            return []
        
        inventory_items = []
        for item in response.data:
            # FIXED: Calculate low stock status in Python, not in Supabase query
            current_stock = item.get('stock_quantity', 0)
            min_threshold = item.get('min_stock_threshold', 0)
            is_low_stock = current_stock <= min_threshold
            is_out_of_stock = current_stock == 0
            
            # Apply low_stock_only filter here in Python
            if low_stock_only and not is_low_stock:
                continue
            
            inventory_items.append(InventoryItem(
                id=item['id'],
                name=item['name'],
                current_stock=current_stock,
                min_threshold=min_threshold,
                is_low_stock=is_low_stock,
                is_out_of_stock=is_out_of_stock,
                last_updated=item.get('updated_at')
            ))
        
        logger.info(f"Returning {len(inventory_items)} inventory items")
        return inventory_items
        
    except Exception as e:
        logger.error(f"Failed to get inventory: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get inventory: {str(e)}"
        )


@router.put("/items/{item_id}", response_model=InventoryItem)
async def update_food_inventory(
    item_id: str,  # Changed from int to str for UUID
    update_data: InventoryUpdate,
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Update stock quantity for a menu item.
    """
    try:
        logger.info(f"Updating inventory for item {item_id} in business {business.id}")
        
        # Get current menu item
        item_response = supabase.table('menu_items').select('*').eq('id', item_id).eq('business_id', business.id).execute()
        
        if not item_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )
        
        item = item_response.data[0]
        old_stock = item.get('stock_quantity', 0)
        # Handle different possible column names for stock thresholds
        old_threshold = (item.get('min_stock_threshold') or 
                        item.get('minimum_stock') or 
                        item.get('min_threshold') or 
                        item.get('reorder_level') or 0)
        
        # Prepare update data
        update_dict = {
            'stock_quantity': update_data.stock_quantity,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Only update threshold if the column exists and value is provided
        if update_data.min_stock_threshold is not None:
            # Try to determine the correct column name for minimum stock
            if 'min_stock_threshold' in item:
                update_dict['min_stock_threshold'] = update_data.min_stock_threshold
            elif 'minimum_stock' in item:
                update_dict['minimum_stock'] = update_data.min_stock_threshold
            elif 'min_threshold' in item:
                update_dict['min_threshold'] = update_data.min_stock_threshold
            elif 'reorder_level' in item:
                update_dict['reorder_level'] = update_data.min_stock_threshold
            # If none of these columns exist, we'll skip updating the threshold
        
        # Update availability based on stock
        if update_data.stock_quantity == 0:
            update_dict['is_available'] = False
        elif old_stock == 0 and update_data.stock_quantity > 0:
            update_dict['is_available'] = True
        
        # Update item
        update_response = supabase.table('menu_items').update(update_dict).eq('id', str(item_id)).eq('business_id', business.id).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update inventory item"
            )
        
        updated_item = update_response.data[0]
        current_stock = updated_item.get('stock_quantity', 0)
        # Use the same logic to get current threshold
        current_threshold = (updated_item.get('min_stock_threshold') or 
                           updated_item.get('minimum_stock') or 
                           updated_item.get('min_threshold') or 
                           updated_item.get('reorder_level') or old_threshold)
        
        # Check if stock is now low and send alert
        if (current_stock <= current_threshold and old_stock > current_threshold):
            try:
                # Send WebSocket notification
                await manager.broadcast_to_business(
                    business_id=business.id,
                    message={
                        "type": "low_stock_alert",
                        "item_id": updated_item['id'],
                        "item_name": updated_item['name'],
                        "current_stock": current_stock,
                        "threshold": current_threshold
                    }
                )
            except Exception as ws_error:
                logger.warning(f"Failed to send WebSocket notification: {ws_error}")
                # Don't fail the entire request if WebSocket fails
        
        return InventoryItem(
            id=updated_item['id'],
            name=updated_item['name'],
            current_stock=current_stock,
            min_threshold=current_threshold,
            is_low_stock=current_stock <= current_threshold,
            is_out_of_stock=current_stock == 0,
            last_updated=updated_item.get('updated_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update inventory: {str(e)}", exc_info=True)
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
        logger.info(f"Getting low stock items for business {business.id}")
        
        # FIXED: Get all items and filter in Python instead of trying to compare columns in Supabase
        response = supabase.table('menu_items').select('*').eq('business_id', business.id).execute()
        
        if not response.data:
            return []
        
        alerts = []
        for item in response.data:
            current_stock = item.get('stock_quantity', 0)
            # Handle different possible column names for stock thresholds
            threshold = (item.get('min_stock_threshold') or 
                        item.get('minimum_stock') or 
                        item.get('min_threshold') or 
                        item.get('reorder_level') or 0)
            
            # Filter low stock items in Python
            if current_stock <= threshold:
                alerts.append(LowStockItem(
                    item_id=item['id'],
                    item_name=item['name'],
                    current_stock=current_stock,
                    threshold=threshold,
                    days_since_last_order=None  # Could be calculated from order history
                ))
        
        logger.info(f"Found {len(alerts)} low stock items")
        return alerts
        
    except Exception as e:
        logger.error(f"Failed to get low stock alerts: {str(e)}", exc_info=True)
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
        logger.info(f"Creating reorder request for item {reorder_request.item_id}")
        logger.info(f"Request data: {reorder_request.model_dump()}")
        
        # Get menu item
        item_response = supabase.table('menu_items').select('*').eq('id', reorder_request.item_id).eq('business_id', business.id).execute()
        
        if not item_response.data:
            logger.warning(f"Menu item not found: {reorder_request.item_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )
        
        item = item_response.data[0]
        logger.info(f"Found menu item: {item['name']}")
        
        # In a real implementation, this would create a purchase order
        # For now, we'll just log the request and send a notification
        
        try:
            # Send WebSocket notification
            await manager.broadcast_to_business(
                business_id=business.id,
                message={
                    "type": "reorder_request",
                    "item_id": str(item['id']),
                    "item_name": item['name'],
                    "quantity": reorder_request.quantity,
                    "requested_by": getattr(current_user, 'email', getattr(current_user, 'phone', 'Unknown')),
                    "supplier": reorder_request.supplier,
                    "notes": reorder_request.notes
                }
            )
            logger.info("WebSocket notification sent successfully")
        except Exception as ws_error:
            logger.warning(f"Failed to send WebSocket notification: {ws_error}")
            # Don't fail the entire request if WebSocket fails
        
        response_data = {
            "message": f"Reorder request created for {reorder_request.quantity} units of {item['name']}",
            "item_id": str(item['id']),
            "item_name": item['name'],
            "requested_quantity": reorder_request.quantity
        }
        logger.info(f"Returning response: {response_data}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create reorder request: {str(e)}", exc_info=True)
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
        logger.info(f"Tracking ingredient usage for business {business.id}, period: {period}")
        
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
        
        logger.info(f"Date range: {start_date.isoformat()} to {end_date.isoformat()}")
        
        # Get completed orders in the period (assuming you have an orders table)
        # You'll need to replace 'orders' with your actual orders table name
        orders_response = supabase.table('orders').select(
            '*, order_items(*)'  # Get orders with their items
        ).eq(
            'business_id', business.id
        ).gte(
            'created_at', start_date.isoformat()
        ).lte(
            'created_at', end_date.isoformat()
        ).in_(
            'status', ['completed', 'delivered']
        ).execute()
        
        logger.info(f"Found {len(orders_response.data) if orders_response.data else 0} completed orders")
        
        # Track usage by item
        usage_stats = {}
        
        if orders_response.data:
            for order in orders_response.data:
                try:
                    # Get order items
                    order_items = order.get('order_items', [])
                    
                    for item in order_items:
                        item_id = item.get('menu_item_id')
                        quantity = item.get('quantity', 1)
                        price = item.get('price', 0)
                        
                        if item_id is None:
                            continue
                        
                        # Get menu item details to get the name
                        if item_id not in usage_stats:
                            # Fetch menu item details
                            menu_item_response = supabase.table('menu_items').select('name').eq('id', item_id).single().execute()
                            item_name = menu_item_response.data.get('name', f'Unknown Item {item_id}') if menu_item_response.data else f'Unknown Item {item_id}'
                            
                            usage_stats[item_id] = {
                                "name": item_name,
                                "total_sold": 0,
                                "total_revenue": 0.0
                            }
                        
                        usage_stats[item_id]["total_sold"] += quantity
                        usage_stats[item_id]["total_revenue"] += quantity * price
                        
                except Exception as item_error:
                    logger.warning(f"Error processing order {order.get('id')}: {item_error}")
                    continue
        
        # Convert to response format
        usage_tracking = []
        for item_id, stats in usage_stats.items():
            usage_tracking.append(UsageTracking(
                item_id=str(item_id),
                item_name=stats["name"],
                total_sold=stats["total_sold"],
                total_revenue=round(stats["total_revenue"], 2),
                period=period
            ))
        
        # Sort by total sold descending
        usage_tracking.sort(key=lambda x: x.total_sold, reverse=True)
        
        logger.info(f"Returning usage data for {len(usage_tracking)} items")
        return usage_tracking
        
    except Exception as e:
        logger.error(f"Failed to track ingredient usage: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track ingredient usage: {str(e)}"
        )

@router.get("/debug", response_model=Dict[str, Any])
async def debug_inventory_schema(
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Debug endpoint to check database schema and sample data.
    """
    try:
        # Get a sample menu item to see the actual column structure
        response = supabase.table('menu_items').select('*').eq('business_id', business.id).limit(1).execute()
        
        sample_item = response.data[0] if response.data else {}
        
        # Get all possible stock-related column names
        stock_columns = []
        quantity_columns = []
        threshold_columns = []
        
        if sample_item:
            all_columns = list(sample_item.keys())
            for col in all_columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ['stock', 'inventory', 'quantity']):
                    stock_columns.append(col)
                if any(keyword in col_lower for keyword in ['quantity', 'qty', 'amount', 'count']):
                    quantity_columns.append(col)
                if any(keyword in col_lower for keyword in ['threshold', 'minimum', 'min', 'reorder', 'level']):
                    threshold_columns.append(col)
        
        return {
            "status": "success",
            "business_id": str(business.id),
            "all_columns": list(sample_item.keys()) if sample_item else [],
            "sample_item": sample_item,
            "stock_related_columns": stock_columns,
            "quantity_related_columns": quantity_columns,
            "threshold_related_columns": threshold_columns,
            "menu_items_count": len(response.data) if response.data else 0
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "business_id": str(business.id) if business else "No business"
        }