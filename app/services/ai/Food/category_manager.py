# app/services/ai/dashboard_actions/category_manager.py
"""
Category Management for Dashboard AI
Handles natural language requests for menu categories
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.models import MenuCategory, MenuItem
import logging

logger = logging.getLogger(__name__)

class CategoryManager:
    def __init__(self, db: Session):
        self.db = db

    async def handle_category_request(self, business_id: int, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle all category-related requests based on AI intent"""
        action = intent.get("action", "")
        
        try:
            if action == "list_categories":
                return await self.list_categories(business_id)
            elif action == "add_category":
                return await self.add_category(
                    business_id, 
                    intent.get("name", ""), 
                    intent.get("description", "")
                )
            elif action == "update_category":
                return await self.update_category(
                    business_id,
                    intent.get("category_id"),
                    intent.get("name"),
                    intent.get("description")
                )
            elif action == "delete_category":
                return await self.delete_category(
                    business_id,
                    intent.get("category_id")
                )
            else:
                return {"success": False, "message": "I don't understand that category action."}
        except Exception as e:
            logger.error(f"Error handling category request: {str(e)}")
            return {"success": False, "message": f"Error processing category request: {str(e)}"}

    async def list_categories(self, business_id: int) -> Dict[str, Any]:
        """List all categories for a business"""
        try:
            categories = self.db.query(MenuCategory).filter(
                MenuCategory.business_id == business_id
            ).all()
            
            if not categories:
                return {
                    "success": True,
                    "message": "You don't have any menu categories yet. Would you like to add one?",
                    "categories": []
                }
            
            category_list = []
            for cat in categories:
                # Count items in each category
                item_count = self.db.query(MenuItem).filter(
                    MenuItem.category_id == cat.id,
                    MenuItem.is_available == True
                ).count()
                
                category_list.append({
                    "id": cat.id,
                    "name": cat.name,
                    "description": cat.description,
                    "item_count": item_count
                })
            
            response_text = f"I found {len(categories)} categories in your menu:\n"
            for cat in category_list:
                response_text += f"• **{cat['name']}** ({cat['item_count']} items)"
                if cat['description']:
                    response_text += f" - {cat['description']}"
                response_text += "\n"
            
            return {
                "success": True,
                "message": response_text,
                "categories": category_list
            }
        except Exception as e:
            return {"success": False, "message": f"Error listing categories: {str(e)}"}

    async def add_category(self, business_id: int, name: str, description: str = "") -> Dict[str, Any]:
        """Add a new menu category"""
        if not name:
            return {"success": False, "message": "Please provide a name for the new category."}
        
        try:
            # Check if category already exists
            existing = self.db.query(MenuCategory).filter(
                MenuCategory.business_id == business_id,
                MenuCategory.name.ilike(name)
            ).first()
            
            if existing:
                return {
                    "success": False, 
                    "message": f"A category named '{name}' already exists. Would you like to modify it instead?"
                }
            
            # Create new category
            category = MenuCategory(
                business_id=business_id,
                name=name.strip(),
                description=description.strip() if description else ""
            )
            
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)
            
            return {
                "success": True,
                "message": f"✅ I've added the new category '**{name}**' to your menu.",
                "category_id": category.id
            }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to add category: {str(e)}"}

    async def update_category(self, business_id: int, category_id: Optional[int], 
                            name: Optional[str], description: Optional[str]) -> Dict[str, Any]:
        """Update an existing category"""
        try:
            category = None
            if category_id:
                category = self.db.query(MenuCategory).filter(
                    MenuCategory.id == category_id,
                    MenuCategory.business_id == business_id
                ).first()
            elif name:
                category = self.db.query(MenuCategory).filter(
                    MenuCategory.name.ilike(name),
                    MenuCategory.business_id == business_id
                ).first()
            
            if not category:
                return {"success": False, "message": "I couldn't find that category. Can you specify which one to update?"}
            
            updates = []
            if name and name != category.name:
                category.name = name
                updates.append(f"name to '{name}'")
            
            if description is not None and description != category.description:
                category.description = description
                updates.append(f"description to '{description}'")
            
            if updates:
                self.db.commit()
                return {
                    "success": True,
                    "message": f"✅ I've updated the category '**{category.name}**': {', '.join(updates)}."
                }
            else:
                return {
                    "success": True,
                    "message": f"The category '**{category.name}**' is already up to date."
                }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to update category: {str(e)}"}

    async def delete_category(self, business_id: int, category_id: Optional[int]) -> Dict[str, Any]:
        """Delete a category (with safety checks)"""
        try:
            category = None
            if category_id:
                category = self.db.query(MenuCategory).filter(
                    MenuCategory.id == category_id,
                    MenuCategory.business_id == business_id
                ).first()
            
            if not category:
                return {"success": False, "message": "I couldn't find that category to delete."}
            
            # Check if category has items
            item_count = self.db.query(MenuItem).filter(
                MenuItem.category_id == category.id
            ).count()
            
            if item_count > 0:
                return {
                    "success": False,
                    "message": f"⚠️ The category '**{category.name}**' still has {item_count} items. "
                              f"Please move or delete those items first before removing the category."
                }
            
            # Safe to delete
            category_name = category.name
            self.db.delete(category)
            self.db.commit()
            
            return {
                "success": True,
                "message": f"✅ I've removed the category '**{category_name}**' from your menu."
            }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to delete category: {str(e)}"}