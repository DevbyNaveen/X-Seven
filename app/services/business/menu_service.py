"""
Menu Service - Single source of truth for all menu operations.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging
from datetime import datetime
from sqlalchemy import func

from app.models import MenuItem, MenuCategory, Business, Order, OrderStatus
from app.schemas.menu import MenuItemCreate, MenuItemUpdate, MenuCategoryCreate, MenuCategoryUpdate
from app.services.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)


class MenuService:
    """
    Service for managing menu items and categories.
    Single source of truth for all menu operations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        # Inject notification service for menu-related notifications
        self.notification_service = NotificationService(db)
    
    async def create_menu_item(
        self,
        business_id: int,
        item_data: MenuItemCreate
    ) -> MenuItem:
        """
        Create a new menu item with validation and notifications.
        
        Args:
            business_id: Business ID
            item_data: Menu item creation data
            
        Returns:
            Created menu item
            
        Raises:
            ValueError: If validation fails
        """
        # Validate category exists
        if item_data.category_id:
            category = self.db.query(MenuCategory).filter(
                MenuCategory.id == item_data.category_id,
                MenuCategory.business_id == business_id
            ).first()
            
            if not category:
                raise ValueError(f"Category {item_data.category_id} not found")
        
        # Check for duplicate item names in the same business
        existing_item = self.db.query(MenuItem).filter(
            MenuItem.business_id == business_id,
            MenuItem.name == item_data.name
        ).first()
        
        if existing_item:
            raise ValueError(f"Menu item '{item_data.name}' already exists")
        
        # Create menu item
        menu_item = MenuItem(
            business_id=business_id,
            name=item_data.name,
            description=item_data.description,
            base_price=item_data.base_price,
            category_id=item_data.category_id,
            is_available=item_data.is_available,
            preparation_time=item_data.preparation_time,
            customizations=item_data.customizations or [],
            allergens=item_data.allergens or [],
            nutritional_info=item_data.nutritional_info or {},
            image_url=item_data.image_url
        )
        
        self.db.add(menu_item)
        self.db.commit()
        self.db.refresh(menu_item)
        
        # Send notification to staff about new menu item
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business:
                await self.notification_service.send_staff_alert(
                    business=business,
                    alert_type="New Menu Item",
                    message=f"New menu item '{menu_item.name}' added - ${menu_item.base_price:.2f}",
                    priority="low"
                )
        except Exception as e:
            logger.error(f"Failed to send menu item notification: {e}")
        
        return menu_item
    
    def update_menu_item(
        self,
        item_id: int,
        business_id: int,
        item_data: MenuItemUpdate
    ) -> MenuItem:
        """
        Update a menu item with validation.
        
        Args:
            item_id: Menu item ID to update
            business_id: Business ID for validation
            item_data: Menu item update data
            
        Returns:
            Updated menu item
            
        Raises:
            ValueError: If validation fails
        """
        menu_item = self._get_menu_item(item_id, business_id)
        
        # Validate category if being updated
        if item_data.category_id and item_data.category_id != menu_item.category_id:
            category = self.db.query(MenuCategory).filter(
                MenuCategory.id == item_data.category_id,
                MenuCategory.business_id == business_id
            ).first()
            
            if not category:
                raise ValueError(f"Category {item_data.category_id} not found")
        
        # Check for duplicate names if name is being updated
        if item_data.name and item_data.name != menu_item.name:
            existing_item = self.db.query(MenuItem).filter(
                MenuItem.business_id == business_id,
                MenuItem.name == item_data.name,
                MenuItem.id != item_id
            ).first()
            
            if existing_item:
                raise ValueError(f"Menu item '{item_data.name}' already exists")
        
        # Update fields
        if item_data.name is not None:
            menu_item.name = item_data.name
        if item_data.description is not None:
            menu_item.description = item_data.description
        if item_data.base_price is not None:
            menu_item.base_price = item_data.base_price
        if item_data.category_id is not None:
            menu_item.category_id = item_data.category_id
        if item_data.is_available is not None:
            menu_item.is_available = item_data.is_available
        if item_data.preparation_time is not None:
            menu_item.preparation_time = item_data.preparation_time
        if item_data.customizations is not None:
            menu_item.customizations = item_data.customizations
        if item_data.allergens is not None:
            menu_item.allergens = item_data.allergens
        if item_data.nutritional_info is not None:
            menu_item.nutritional_info = item_data.nutritional_info
        if item_data.image_url is not None:
            menu_item.image_url = item_data.image_url
        
        menu_item.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(menu_item)
        
        return menu_item
    
    async def toggle_item_availability(
        self,
        item_id: int,
        business_id: int,
        is_available: bool
    ) -> MenuItem:
        """
        Toggle menu item availability.
        
        Args:
            item_id: Menu item ID to toggle
            business_id: Business ID for validation
            is_available: New availability status
            
        Returns:
            Updated menu item
            
        Raises:
            ValueError: If item not found
        """
        menu_item = self._get_menu_item(item_id, business_id)
        
        menu_item.is_available = is_available
        menu_item.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(menu_item)
        
        # Send notification about availability change
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business:
                status = "available" if is_available else "unavailable"
                await self.notification_service.send_staff_alert(
                    business=business,
                    alert_type="Menu Item Status",
                    message=f"Menu item '{menu_item.name}' is now {status}",
                    priority="low"
                )
        except Exception as e:
            logger.error(f"Failed to send availability notification: {e}")
        
        return menu_item
    
    async def delete_menu_item(
        self,
        item_id: int,
        business_id: int
    ) -> bool:
        """
        Delete a menu item.
        
        Args:
            item_id: Menu item ID to delete
            business_id: Business ID for validation
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If item not found or has active orders
        """
        menu_item = self._get_menu_item(item_id, business_id)
        
        # Check if item has any active orders (simplified check)
        # In production, you'd check for orders in PENDING, CONFIRMED, PREPARING status
        active_orders = self.db.query(Order).filter(
            Order.business_id == business_id,
            Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PREPARING])
        ).all()
        
        for order in active_orders:
            for item in order.items:
                if item.get("item_id") == item_id:
                    raise ValueError(f"Cannot delete '{menu_item.name}' - it has active orders")
        
        # Store item name for notification
        item_name = menu_item.name
        
        self.db.delete(menu_item)
        self.db.commit()
        
        # Send notification about item deletion
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business:
                await self.notification_service.send_staff_alert(
                    business=business,
                    alert_type="Menu Item Deleted",
                    message=f"Menu item '{item_name}' has been removed",
                    priority="normal"
                )
        except Exception as e:
            logger.error(f"Failed to send deletion notification: {e}")
        
        return True
    
    def create_menu_category(
        self,
        business_id: int,
        category_data: MenuCategoryCreate
    ) -> MenuCategory:
        """
        Create a new menu category.
        
        Args:
            business_id: Business ID
            category_data: Category creation data
            
        Returns:
            Created category
            
        Raises:
            ValueError: If validation fails
        """
        # Check for duplicate category names
        existing_category = self.db.query(MenuCategory).filter(
            MenuCategory.business_id == business_id,
            MenuCategory.name == category_data.name
        ).first()
        
        if existing_category:
            raise ValueError(f"Category '{category_data.name}' already exists")
        
        # Create category
        category = MenuCategory(
            business_id=business_id,
            name=category_data.name,
            description=category_data.description,
            is_active=category_data.is_active,
            display_order=category_data.display_order,
            image_url=category_data.image_url
        )
        
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        
        return category
    
    def update_menu_category(
        self,
        category_id: int,
        business_id: int,
        category_data: MenuCategoryUpdate
    ) -> MenuCategory:
        """
        Update a menu category.
        
        Args:
            category_id: Category ID to update
            business_id: Business ID for validation
            category_data: Category update data
            
        Returns:
            Updated category
            
        Raises:
            ValueError: If validation fails
        """
        category = self._get_menu_category(category_id, business_id)
        
        # Check for duplicate names if name is being updated
        if category_data.name and category_data.name != category.name:
            existing_category = self.db.query(MenuCategory).filter(
                MenuCategory.business_id == business_id,
                MenuCategory.name == category_data.name,
                MenuCategory.id != category_id
            ).first()
            
            if existing_category:
                raise ValueError(f"Category '{category_data.name}' already exists")
        
        # Update fields
        if category_data.name is not None:
            category.name = category_data.name
        if category_data.description is not None:
            category.description = category_data.description
        if category_data.is_active is not None:
            category.is_active = category_data.is_active
        if category_data.display_order is not None:
            category.display_order = category_data.display_order
        if category_data.image_url is not None:
            category.image_url = category_data.image_url
        
        category.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(category)
        
        return category
    
    def get_menu_items(
        self,
        business_id: int,
        category_id: Optional[int] = None,
        available_only: bool = True
    ) -> List[MenuItem]:
        """
        Get menu items for a business with optional filtering.
        
        Args:
            business_id: Business ID to get items for
            category_id: Optional category filter
            available_only: Whether to return only available items
            
        Returns:
            List of menu items
        """
        query = self.db.query(MenuItem).filter(MenuItem.business_id == business_id)
        
        if category_id:
            query = query.filter(MenuItem.category_id == category_id)
        
        if available_only:
            query = query.filter(MenuItem.is_available == True)
        
        return query.order_by(MenuItem.name).all()
    
    def get_menu_categories(
        self,
        business_id: int,
        active_only: bool = True
    ) -> List[MenuCategory]:
        """
        Get menu categories for a business.
        
        Args:
            business_id: Business ID to get categories for
            active_only: Whether to return only active categories
            
        Returns:
            List of menu categories
        """
        query = self.db.query(MenuCategory).filter(MenuCategory.business_id == business_id)
        
        if active_only:
            query = query.filter(MenuCategory.is_active == True)
        
        return query.order_by(MenuCategory.display_order, MenuCategory.name).all()
    
    def get_full_menu(
        self,
        business_id: int,
        include_unavailable: bool = False
    ) -> Dict[str, Any]:
        """
        Get complete menu structure with categories and items.
        
        Args:
            business_id: Business ID to get menu for
            include_unavailable: Whether to include unavailable items
            
        Returns:
            Complete menu structure
        """
        categories = self.get_menu_categories(business_id, active_only=not include_unavailable)
        
        menu_structure = []
        for category in categories:
            items = self.get_menu_items(
                business_id=business_id,
                category_id=category.id,
                available_only=not include_unavailable
            )
            
            menu_structure.append({
                "category": {
                    "id": category.id,
                    "name": category.name,
                    "description": category.description,
                    "image_url": category.image_url
                },
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "description": item.description,
                        "base_price": item.base_price,
                        "is_available": item.is_available,
                        "preparation_time": item.preparation_time,
                        "customizations": item.customizations,
                        "allergens": item.allergens,
                        "nutritional_info": item.nutritional_info,
                        "image_url": item.image_url
                    }
                    for item in items
                ]
            })
        
        return {
            "business_id": business_id,
            "categories": menu_structure,
            "total_items": sum(len(cat["items"]) for cat in menu_structure),
            "available_items": sum(
                len([item for item in cat["items"] if item["is_available"]])
                for cat in menu_structure
            )
        }
    
    def search_menu_items(
        self,
        business_id: int,
        query: str,
        limit: int = 10
    ) -> List[MenuItem]:
        """
        Search menu items by name or description.
        
        Args:
            business_id: Business ID to search in
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching menu items
        """
        query_lower = query.lower()
        
        items = self.db.query(MenuItem).filter(
            MenuItem.business_id == business_id,
            MenuItem.is_available == True
        ).all()
        
        # Simple text search
        matching_items = []
        for item in items:
            if (query_lower in item.name.lower() or 
                query_lower in item.description.lower() or
                any(query_lower in allergen.lower() for allergen in item.allergens)):
                matching_items.append(item)
        
        return matching_items[:limit]
    
    def get_menu_stats(
        self,
        business_id: int
    ) -> Dict[str, Any]:
        """
        Get menu statistics for a business.
        
        Args:
            business_id: Business ID to get stats for
            
        Returns:
            Menu statistics
        """
        total_items = self.db.query(MenuItem).filter(
            MenuItem.business_id == business_id
        ).count()
        
        available_items = self.db.query(MenuItem).filter(
            MenuItem.business_id == business_id,
            MenuItem.is_available == True
        ).count()
        
        total_categories = self.db.query(MenuCategory).filter(
            MenuCategory.business_id == business_id
        ).count()
        
        active_categories = self.db.query(MenuCategory).filter(
            MenuCategory.business_id == business_id,
            MenuCategory.is_active == True
        ).count()
        
        # Get price range
        price_stats = self.db.query(
            func.min(MenuItem.base_price),
            func.max(MenuItem.base_price),
            func.avg(MenuItem.base_price)
        ).filter(
            MenuItem.business_id == business_id,
            MenuItem.is_available == True
        ).first()
        
        return {
            "total_items": total_items,
            "available_items": available_items,
            "unavailable_items": total_items - available_items,
            "total_categories": total_categories,
            "active_categories": active_categories,
            "inactive_categories": total_categories - active_categories,
            "price_range": {
                "min": float(price_stats[0]) if price_stats[0] else 0,
                "max": float(price_stats[1]) if price_stats[1] else 0,
                "average": float(price_stats[2]) if price_stats[2] else 0
            }
        }
    
    def _get_menu_item(self, item_id: int, business_id: int) -> MenuItem:
        """
        Helper to get and validate a menu item.
        
        Args:
            item_id: Menu item ID to get
            business_id: Business ID for validation
            
        Returns:
            Menu item object
            
        Raises:
            ValueError: If item not found
        """
        menu_item = self.db.query(MenuItem).filter(
            MenuItem.id == item_id,
            MenuItem.business_id == business_id
        ).first()
        
        if not menu_item:
            raise ValueError(f"Menu item {item_id} not found for business {business_id}")
        
        return menu_item
    
    def _get_menu_category(self, category_id: int, business_id: int) -> MenuCategory:
        """
        Helper to get and validate a menu category.
        
        Args:
            category_id: Category ID to get
            business_id: Business ID for validation
            
        Returns:
            Menu category object
            
        Raises:
            ValueError: If category not found
        """
        category = self.db.query(MenuCategory).filter(
            MenuCategory.id == category_id,
            MenuCategory.business_id == business_id
        ).first()
        
        if not category:
            raise ValueError(f"Menu category {category_id} not found for business {business_id}")
        
        return category
