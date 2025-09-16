# app/services/ai/dashboard_actions/inventory_manager.py
"""
Inventory Management for Dashboard AI
Handles natural language requests for inventory/items
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.models import MenuItem
import logging

logger = logging.getLogger(__name__)

class InventoryManager:
    def __init__(self, db: Session):
        self.db = db

    async def handle_inventory_request(self, business_id: int, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle all inventory-related requests based on AI intent"""
        action = intent.get("action", "")
        
        try:
            if action == "list_inventory":
                return await self.list_inventory(business_id)
            elif action == "update_stock":
                return await self.update_stock(
                    business_id,
                    intent.get("item_id") or intent.get("item_name"),
                    intent.get("quantity"),
                    intent.get("reorder_level")
                )
            elif action == "low_stock_report":
                return await self.low_stock_report(business_id)
            else:
                return {"success": False, "message": "I don't understand that inventory action."}
        except Exception as e:
            logger.error(f"Error handling inventory request: {str(e)}")
            return {"success": False, "message": f"Error processing inventory request: {str(e)}"}

    async def list_inventory(self, business_id: int) -> Dict[str, Any]:
        """List all inventory items with stock levels"""
        try:
            items = self.db.query(MenuItem).filter(
                MenuItem.business_id == business_id
            ).all()
            
            if not items:
                return {
                    "success": True,
                    "message": "You don't have any menu items yet. Add items to track inventory.",
                    "items": []
                }
            
            inventory_list = []
            response_text = "Here's your current inventory:\n\n"
            
            for item in items:
                stock_qty = int(item.stock_quantity or 0)
                min_stock = int(item.min_stock_threshold or 0)
                status = "🔴 Low Stock" if stock_qty <= min_stock and min_stock > 0 else "🟢 In Stock"
                
                inventory_list.append({
                    "id": item.id,
                    "name": item.name,
                    "stock_quantity": stock_qty,
                    "min_stock_threshold": min_stock,
                    "unit": "units",
                    "status": "low" if stock_qty <= min_stock and min_stock > 0 else "normal"
                })
                
                response_text += f"• **{item.name}** - {stock_qty} units {status}\n"
                if min_stock > 0:
                    response_text += f"  Reorder at: {min_stock} units\n"
                response_text += "\n"
            
            return {
                "success": True,
                "message": response_text,
                "items": inventory_list
            }
        except Exception as e:
            return {"success": False, "message": f"Error listing inventory: {str(e)}"}

    async def update_stock(self, business_id: int, item_ref: Any, 
                          quantity: Optional[int], reorder_level: Optional[int]) -> Dict[str, Any]:
        """Update stock quantity or reorder level for an item"""
        try:
            if not item_ref:
                return {"success": False, "message": "Please specify which item to update."}
            
            # Find the item
            item = None
            if isinstance(item_ref, int):
                item = self.db.query(MenuItem).filter(
                    MenuItem.id == item_ref,
                    MenuItem.business_id == business_id
                ).first()
            elif isinstance(item_ref, str):
                item = self.db.query(MenuItem).filter(
                    MenuItem.name.ilike(item_ref),
                    MenuItem.business_id == business_id
                ).first()
            
            if not item:
                return {"success": False, "message": "I couldn't find that inventory item."}
            
            updates = []
            
            if quantity is not None:
                old_qty = int(item.stock_quantity or 0)
                item.stock_quantity = int(quantity)
                updates.append(f"stock from {old_qty} to {quantity} units")
            
            if reorder_level is not None:
                old_reorder = int(item.min_stock_threshold or 0)
                item.min_stock_threshold = int(reorder_level)
                updates.append(f"reorder level from {old_reorder} to {reorder_level} units")
            
            if updates:
                self.db.commit()
                return {
                    "success": True,
                    "message": f"✅ I've updated inventory for '**{item.name}**': {', '.join(updates)}."
                }
            else:
                return {
                    "success": True,
                    "message": f"No changes were made to '**{item.name}**'."
                }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to update inventory: {str(e)}"}

    async def low_stock_report(self, business_id: int) -> Dict[str, Any]:
        """Generate a report of low-stock items"""
        try:
            # Get items with stock quantity <= reorder level
            items = self.db.query(MenuItem).filter(
                MenuItem.business_id == business_id,
                MenuItem.min_stock_threshold > 0
            ).all()
            
            low_stock_items = []
            for item in items:
                stock_qty = int(item.stock_quantity or 0)
                min_stock = int(item.min_stock_threshold or 0)
                if stock_qty <= min_stock:
                    low_stock_items.append(item)
            
            if not low_stock_items:
                return {
                    "success": True,
                    "message": "✅ Great news! All your inventory items are sufficiently stocked.",
                    "items": []
                }
            
            response_text = f"⚠️ You have {len(low_stock_items)} low-stock items:\n\n"
            item_list = []
            
            for item in low_stock_items:
                stock_qty = int(item.stock_quantity or 0)
                min_stock = int(item.min_stock_threshold or 0)
                
                item_list.append({
                    "id": item.id,
                    "name": item.name,
                    "current_stock": stock_qty,
                    "reorder_level": min_stock
                })
                
                response_text += f"• **{item.name}** - {stock_qty} units (reorder at {min_stock})\n"
            
            response_text += "\nConsider reordering these items soon to avoid stockouts."
            
            return {
                "success": True,
                "message": response_text,
                "items": item_list
            }
        except Exception as e:
            return {"success": False, "message": f"Error generating low stock report: {str(e)}"}