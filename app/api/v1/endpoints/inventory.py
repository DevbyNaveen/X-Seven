"""Inventory management endpoints for staff."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.dependencies import get_db, get_current_business
from app.models import Business, MenuItem
from app.services.notifications.notification_service import NotificationService

router = APIRouter()


class InventoryUpdate(BaseModel):
    """Inventory update request."""
    stock_quantity: int
    min_stock_threshold: Optional[int] = None


class InventoryItem(BaseModel):
    """Inventory item response."""
    id: int
    name: str
    current_stock: int
    min_threshold: int
    is_low_stock: bool
    is_out_of_stock: bool
    last_updated: Optional[str] = None


class LowStockAlert(BaseModel):
    """Low stock alert response."""
    item_id: int
    item_name: str
    current_stock: int
    threshold: int
    days_since_last_order: Optional[int] = None


@router.get("/", response_model=List[InventoryItem])
async def get_inventory(
    low_stock_only: bool = Query(False, description="Show only low stock items"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get inventory status for all menu items."""
    try:
        query = db.query(MenuItem).filter(
            MenuItem.business_id == business.id
        )
        
        if low_stock_only:
            query = query.filter(
                MenuItem.stock_quantity <= MenuItem.min_stock_threshold
            )
        
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


@router.get("/low-stock", response_model=List[LowStockAlert])
async def get_low_stock_alerts(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get low stock alerts."""
    try:
        low_stock_items = db.query(MenuItem).filter(
            MenuItem.business_id == business.id,
            MenuItem.stock_quantity <= MenuItem.min_stock_threshold
        ).all()
        
        alerts = []
        for item in low_stock_items:
            alerts.append(LowStockAlert(
                item_id=item.id,
                item_name=item.name,
                current_stock=item.stock_quantity,
                threshold=item.min_stock_threshold,
                days_since_last_order=None  # Could be calculated from order history
            ))
        
        return alerts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get low stock alerts: {str(e)}")


@router.put("/{item_id}", response_model=InventoryItem)
async def update_inventory(
    item_id: int,
    update_data: InventoryUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Update inventory for a menu item."""
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
            
            notification_service = NotificationService(db)
            await notification_service.send_low_stock_alert(
                business_id=business.id,
                item_name=menu_item.name,
                current_stock=menu_item.stock_quantity,
                threshold=menu_item.min_stock_threshold
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


@router.post("/{item_id}/restock")
async def restock_item(
    item_id: int,
    quantity: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Add stock to an item (restock)."""
    try:
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == item_id,
            MenuItem.business_id == business.id
        ).first()
        
        if not menu_item:
            raise HTTPException(status_code=404, detail="Menu item not found")
        
        # Add stock
        old_stock = menu_item.stock_quantity
        menu_item.stock_quantity += quantity
        
        # Mark as available if it was out of stock
        if old_stock == 0 and menu_item.stock_quantity > 0:
            menu_item.is_available = True
        
        db.commit()
        
        return {
            "message": f"Restocked {quantity} units of {menu_item.name}",
            "new_stock": menu_item.stock_quantity
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restock item: {str(e)}")


@router.post("/{item_id}/adjust")
async def adjust_inventory(
    item_id: int,
    adjustment: int,  # Positive for addition, negative for reduction
    reason: str = "Manual adjustment",
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Adjust inventory (add or subtract stock)."""
    try:
        menu_item = db.query(MenuItem).filter(
            MenuItem.id == item_id,
            MenuItem.business_id == business.id
        ).first()
        
        if not menu_item:
            raise HTTPException(status_code=404, detail="Menu item not found")
        
        # Adjust stock
        old_stock = menu_item.stock_quantity
        new_stock = max(0, old_stock + adjustment)  # Don't go below 0
        menu_item.stock_quantity = new_stock
        
        # Update availability
        if new_stock == 0:
            menu_item.is_available = False
        elif old_stock == 0 and new_stock > 0:
            menu_item.is_available = True
        
        db.commit()
        
        # Check for low stock alert
        if (menu_item.stock_quantity <= menu_item.min_stock_threshold and 
            old_stock > menu_item.min_stock_threshold):
            
            notification_service = NotificationService(db)
            await notification_service.send_low_stock_alert(
                business_id=business.id,
                item_name=menu_item.name,
                current_stock=menu_item.stock_quantity,
                threshold=menu_item.min_stock_threshold
            )
        
        return {
            "message": f"Adjusted {menu_item.name} by {adjustment} units",
            "old_stock": old_stock,
            "new_stock": new_stock,
            "reason": reason
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to adjust inventory: {str(e)}")


@router.get("/summary")
async def get_inventory_summary(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get inventory summary statistics."""
    try:
        menu_items = db.query(MenuItem).filter(
            MenuItem.business_id == business.id
        ).all()
        
        total_items = len(menu_items)
        low_stock_items = len([item for item in menu_items if item.stock_quantity <= item.min_stock_threshold])
        out_of_stock_items = len([item for item in menu_items if item.stock_quantity == 0])
        unavailable_items = len([item for item in menu_items if not item.is_available])
        
        total_stock_value = sum(item.stock_quantity * item.base_price for item in menu_items)
        
        return {
            "total_items": total_items,
            "low_stock_items": low_stock_items,
            "out_of_stock_items": out_of_stock_items,
            "unavailable_items": unavailable_items,
            "total_stock_value": round(total_stock_value, 2),
            "low_stock_percentage": round((low_stock_items / total_items * 100), 2) if total_items > 0 else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get inventory summary: {str(e)}")


@router.post("/bulk-update")
async def bulk_update_inventory(
    updates: List[dict],  # List of {item_id, stock_quantity, min_threshold}
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Bulk update inventory for multiple items."""
    try:
        updated_items = []
        errors = []
        
        for update in updates:
            try:
                item_id = update.get("item_id")
                stock_quantity = update.get("stock_quantity")
                min_threshold = update.get("min_stock_threshold")
                
                if not all([item_id, stock_quantity is not None]):
                    errors.append(f"Missing required fields for item {item_id}")
                    continue
                
                menu_item = db.query(MenuItem).filter(
                    MenuItem.id == item_id,
                    MenuItem.business_id == business.id
                ).first()
                
                if not menu_item:
                    errors.append(f"Menu item {item_id} not found")
                    continue
                
                # Update item
                old_stock = menu_item.stock_quantity
                menu_item.stock_quantity = stock_quantity
                
                if min_threshold is not None:
                    menu_item.min_stock_threshold = min_threshold
                
                # Update availability
                if stock_quantity == 0:
                    menu_item.is_available = False
                elif old_stock == 0 and stock_quantity > 0:
                    menu_item.is_available = True
                
                updated_items.append({
                    "item_id": item_id,
                    "name": menu_item.name,
                    "old_stock": old_stock,
                    "new_stock": stock_quantity
                })
                
            except Exception as e:
                errors.append(f"Error updating item {item_id}: {str(e)}")
        
        if updated_items:
            db.commit()
        
        return {
            "updated_items": updated_items,
            "errors": errors,
            "success_count": len(updated_items),
            "error_count": len(errors)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk update inventory: {str(e)}")
