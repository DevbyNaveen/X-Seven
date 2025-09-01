"""Food inventory management endpoints for AI integration."""
from typing import Any, List, Optional, Dict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from pydantic import BaseModel

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User, MenuItem, Order
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
    stock_quantity: int
    min_stock_threshold: Optional[int] = None


class LowStockItem(BaseModel):
    """Low stock item response."""
    item_id: int
    item_name: str
    current_stock: int
    threshold: int
    days_since_last_order: Optional[int] = None


class ReorderRequest(BaseModel):
    """Reorder request."""
    item_id: int
    quantity: int
    supplier: Optional[str] = None
    notes: Optional[str] = None


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
    db: Session = Depends(get_db)
) -> Any:
    """
    Get inventory with stock levels for food service.
    """
    try:
        query = db.query(MenuItem).filter(
            MenuItem.business_id == business.id
        )
        
        if low_stock_only:
            query = query.filter(
                MenuItem.stock_quantity <= MenuItem.min_stock_threshold
            )
        
        if category_id:
            query = query.filter(MenuItem.category_id == category_id)
        
        menu_items = query.all()
        
        inventory_items = []
        for item in menu_items:
            is_low_stock = item.stock_quantity <= item.min_stock_threshold
            is_out_of_stock = item.stock_quantity == 0
            
            inventory_items.append(InventoryItem(
                id=item.id,
                name=item.name,
                current_stock=item.stock_quantity,
                min_threshold=item.min_stock_threshold,
                is_low_stock=is_low_stock,
                is_out_of_stock=is_out_of_stock,
                last_updated=item.updated_at.isoformat() if item.updated_at else None
            ))
        
        return inventory_items
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get inventory: {str(e)}")


@router.put("/items/{item_id}", response_model=InventoryItem)
async def update_food_inventory(
    item_id: int,
    update_data: InventoryUpdate,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update stock quantity for a menu item.
    """
    try:
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == item_id,
            MenuItem.business_id == business.id
        ).first()
        
        if not menu_item:
            raise HTTPException(status_code=404, detail="Menu item not found")
        
        # Update stock quantity
        old_stock = menu_item.stock_quantity
        menu_item.stock_quantity = update_data.stock_quantity
        
        # Update threshold if provided
        if update_data.min_stock_threshold is not None:
            menu_item.min_stock_threshold = update_data.min_stock_threshold
        
        # Check if item should be marked as unavailable
        if update_data.stock_quantity == 0:
            menu_item.is_available = False
        elif old_stock == 0 and update_data.stock_quantity > 0:
            menu_item.is_available = True
        
        db.commit()
        db.refresh(menu_item)
        
        # Check if stock is now low and send alert
        if (menu_item.stock_quantity <= menu_item.min_stock_threshold and 
            old_stock > menu_item.min_stock_threshold):
            
            # Send WebSocket notification
            await manager.broadcast_to_business(
                business_id=business.id,
                message={
                    "type": "low_stock_alert",
                    "item_id": menu_item.id,
                    "item_name": menu_item.name,
                    "current_stock": menu_item.stock_quantity,
                    "threshold": menu_item.min_stock_threshold
                }
            )
        
        return InventoryItem(
            id=menu_item.id,
            name=menu_item.name,
            current_stock=menu_item.stock_quantity,
            min_threshold=menu_item.min_stock_threshold,
            is_low_stock=menu_item.stock_quantity <= menu_item.min_stock_threshold,
            is_out_of_stock=menu_item.stock_quantity == 0,
            last_updated=menu_item.updated_at.isoformat() if menu_item.updated_at else None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update inventory: {str(e)}")


@router.get("/low-stock", response_model=List[LowStockItem])
async def get_food_low_stock(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get items needing reorder.
    """
    try:
        low_stock_items = db.query(MenuItem).filter(
            MenuItem.business_id == business.id,
            MenuItem.stock_quantity <= MenuItem.min_stock_threshold
        ).all()
        
        alerts = []
        for item in low_stock_items:
            alerts.append(LowStockItem(
                item_id=item.id,
                item_name=item.name,
                current_stock=item.stock_quantity,
                threshold=item.min_stock_threshold,
                days_since_last_order=None  # Could be calculated from order history
            ))
        
        return alerts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get low stock alerts: {str(e)}")


@router.post("/reorder", response_model=Dict[str, Any])
async def create_reorder_request(
    reorder_request: ReorderRequest,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create reorder request.
    """
    try:
        # Get menu item
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == reorder_request.item_id,
            MenuItem.business_id == business.id
        ).first()
        
        if not menu_item:
            raise HTTPException(status_code=404, detail="Menu item not found")
        
        # In a real implementation, this would create a purchase order
        # For now, we'll just log the request and send a notification
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "reorder_request",
                "item_id": menu_item.id,
                "item_name": menu_item.name,
                "quantity": reorder_request.quantity,
                "requested_by": current_user.email if current_user.email else current_user.phone,
                "supplier": reorder_request.supplier,
                "notes": reorder_request.notes
            }
        )
        
        return {
            "message": f"Reorder request created for {reorder_request.quantity} units of {menu_item.name}",
            "item_id": menu_item.id,
            "item_name": menu_item.name,
            "requested_quantity": reorder_request.quantity
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create reorder request: {str(e)}")


@router.get("/usage", response_model=List[UsageTracking])
async def track_ingredient_usage(
    period: str = Query("7d", description="Period to track usage (7d, 30d, 90d)"),
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
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
        orders = db.query(Order).filter(
            and_(
                Order.business_id == business.id,
                Order.created_at >= start_date,
                Order.created_at <= end_date,
                Order.status.in_(["completed", "delivered"])
            )
        ).all()
        
        # Track usage by item
        usage_stats = {}
        
        for order in orders:
            # Parse order items (assuming they're stored as JSON)
            for item in order.items:
                item_id = item.get("menu_item_id")
                item_name = item.get("name")
                quantity = item.get("quantity", 1)
                price = item.get("price", 0)
                
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
        raise HTTPException(status_code=500, detail=f"Failed to track ingredient usage: {str(e)}")
