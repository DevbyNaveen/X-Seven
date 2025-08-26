# app/services/ai/dashboard_actions/menu_manager.py
"""
Menu Item Management for Dashboard AI
Handles natural language requests for menu items
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.models import MenuItem, MenuCategory
import logging

logger = logging.getLogger(__name__)

class MenuManager:
    def __init__(self, db: Session):
        self.db = db

    async def handle_menu_request(self, business_id: int, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle all menu-related requests based on AI intent"""
        action = intent.get("action", "")
        
        try:
            if action == "list_menu":
                return await self.list_menu(business_id)
            elif action == "add_item":
                return await self.add_menu_item(
                    business_id,
                    intent.get("name", ""),
                    intent.get("price", 0),
                    intent.get("description", ""),
                    intent.get("category_id") or intent.get("category_name")
                )
            elif action == "update_item":
                return await self.update_menu_item(
                    business_id,
                    intent.get("item_id"),
                    intent.get("name"),
                    intent.get("price"),
                    intent.get("description"),
                    intent.get("category_id") or intent.get("category_name")
                )
            elif action == "delete_item":
                return await self.delete_menu_item(business_id, intent.get("item_id"))
            else:
                return {"success": False, "message": "I don't understand that menu action."}
        except Exception as e:
            logger.error(f"Error handling menu request: {str(e)}")
            return {"success": False, "message": f"Error processing menu request: {str(e)}"}

    async def list_menu(self, business_id: int) -> Dict[str, Any]:
        """List all menu items grouped by category"""
        try:
            # Get all categories with items
            categories = self.db.query(MenuCategory).filter(
                MenuCategory.business_id == business_id
            ).all()
            
            if not categories:
                return {
                    "success": True,
                    "message": "You don't have any menu categories yet. Please add categories before adding items.",
                    "items": []
                }
            
            all_items = []
            response_text = "Here's your current menu:\n\n"
            
            for category in categories:
                items = self.db.query(MenuItem).filter(
                    MenuItem.category_id == category.id,
                    MenuItem.is_available == True
                ).all()
                
                if items:
                    response_text += f"**{category.name}**\n"
                    for item in items:
                        response_text += f"• **{item.name}** - ${item.base_price:.2f}"
                        if item.description:
                            response_text += f" ({item.description})"
                        response_text += "\n"
                        all_items.append({
                            "id": item.id,
                            "name": item.name,
                            "price": float(item.base_price),
                            "description": item.description,
                            "category": category.name
                        })
                    response_text += "\n"
            
            if not all_items:
                response_text = "Your menu is empty. Would you like to add some items?"
            
            return {
                "success": True,
                "message": response_text,
                "items": all_items
            }
        except Exception as e:
            return {"success": False, "message": f"Error listing menu: {str(e)}"}

    async def add_menu_item(self, business_id: int, name: str, price: float, 
                          description: str = "", category_ref: Any = None) -> Dict[str, Any]:
        """Add a new menu item"""
        if not name:
            return {"success": False, "message": "Please provide a name for the new menu item."}
        
        if price <= 0:
            return {"success": False, "message": "Please provide a valid price for the menu item."}
        
        try:
            # Find or create category
            category = None
            if isinstance(category_ref, int):
                category = self.db.query(MenuCategory).filter(
                    MenuCategory.id == category_ref,
                    MenuCategory.business_id == business_id
                ).first()
            elif isinstance(category_ref, str):
                category = self.db.query(MenuCategory).filter(
                    MenuCategory.name.ilike(category_ref),
                    MenuCategory.business_id == business_id
                ).first()
            
            if not category:
                # Create default category if none provided or found
                category = self.db.query(MenuCategory).filter(
                    MenuCategory.business_id == business_id
                ).first()
                
                if not category:
                    # Create a default "General" category
                    category = MenuCategory(
                        business_id=business_id,
                        name="General",
                        description="General menu items"
                    )
                    self.db.add(category)
                    self.db.flush()
            
            # Check if item already exists
            existing = self.db.query(MenuItem).filter(
                MenuItem.name.ilike(name),
                MenuItem.business_id == business_id
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "message": f"An item named '{name}' already exists. Would you like to update it instead?"
                }
            
            # Create new menu item
            menu_item = MenuItem(
                business_id=business_id,
                category_id=category.id,
                name=name.strip(),
                base_price=float(price),
                description=description.strip() if description else ""
            )
            
            self.db.add(menu_item)
            self.db.commit()
            self.db.refresh(menu_item)
            
            return {
                "success": True,
                "message": f"✅ I've added '**{name}**' (${price:.2f}) to your '{category.name}' category.",
                "item_id": menu_item.id
            }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to add menu item: {str(e)}"}

    async def update_menu_item(self, business_id: int, item_id: Optional[int],
                             name: Optional[str], price: Optional[float],
                             description: Optional[str], category_ref: Any = None) -> Dict[str, Any]:
        """Update an existing menu item"""
        try:
            item = None
            if item_id:
                item = self.db.query(MenuItem).filter(
                    MenuItem.id == item_id,
                    MenuItem.business_id == business_id
                ).first()
            elif name:
                item = self.db.query(MenuItem).filter(
                    MenuItem.name.ilike(name),
                    MenuItem.business_id == business_id
                ).first()
            
            if not item:
                return {"success": False, "message": "I couldn't find that menu item. Can you specify which one to update?"}
            
            updates = []
            
            if name and name != item.name:
                old_name = item.name
                item.name = name
                updates.append(f"name from '{old_name}' to '{name}'")
            
            if price is not None and float(price) != float(item.base_price):
                old_price = float(item.base_price)
                item.base_price = float(price)
                updates.append(f"price from ${old_price:.2f} to ${float(price):.2f}")
            
            if description is not None and description != item.description:
                old_desc = item.description or "no description"
                item.description = description
                updates.append(f"description from '{old_desc}' to '{description}'")
            
            # Handle category change
            if category_ref:
                new_category = None
                if isinstance(category_ref, int):
                    new_category = self.db.query(MenuCategory).filter(
                        MenuCategory.id == category_ref,
                        MenuCategory.business_id == business_id
                    ).first()
                elif isinstance(category_ref, str):
                    new_category = self.db.query(MenuCategory).filter(
                        MenuCategory.name.ilike(category_ref),
                        MenuCategory.business_id == business_id
                    ).first()
                
                if new_category and new_category.id != item.category_id:
                    old_category = self.db.query(MenuCategory).filter(
                        MenuCategory.id == item.category_id
                    ).first()
                    old_cat_name = old_category.name if old_category else "unknown"
                    item.category_id = new_category.id
                    updates.append(f"category from '{old_cat_name}' to '{new_category.name}'")
            
            if updates:
                self.db.commit()
                return {
                    "success": True,
                    "message": f"✅ I've updated '**{item.name}**': {', '.join(updates)}."
                }
            else:
                return {
                    "success": True,
                    "message": f"The item '**{item.name}**' is already up to date."
                }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to update menu item: {str(e)}"}

    async def delete_menu_item(self, business_id: int, item_id: Optional[int]) -> Dict[str, Any]:
        """Delete a menu item"""
        try:
            item = None
            if item_id:
                item = self.db.query(MenuItem).filter(
                    MenuItem.id == item_id,
                    MenuItem.business_id == business_id
                ).first()
            
            if not item:
                return {"success": False, "message": "I couldn't find that menu item to delete."}
            
            item_name = item.name
            self.db.delete(item)
            self.db.commit()
            
            return {
                "success": True,
                "message": f"✅ I've removed '**{item_name}**' from your menu."
            }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to delete menu item: {str(e)}"}