"""Menu item model for restaurant menus using Supabase."""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.base import SupabaseModel


class MenuItemStatus(str, Enum):
    """Menu item status enumeration."""
    AVAILABLE = "available"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    HIDDEN = "hidden"


class MenuItem(SupabaseModel):
    """Menu item model for restaurant menus."""
    table_name = "menu_items"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.name = kwargs.get('name')
        self.description = kwargs.get('description')
        self.price = kwargs.get('price', 0.0)
        self.category = kwargs.get('category')
        self.image_url = kwargs.get('image_url')
        self.is_vegetarian = kwargs.get('is_vegetarian', False)
        self.is_vegan = kwargs.get('is_vegan', False)
        self.is_gluten_free = kwargs.get('is_gluten_free', False)
        self.spice_level = kwargs.get('spice_level', 0)
        self.preparation_time = kwargs.get('preparation_time', 0)
        self.status = kwargs.get('status', MenuItemStatus.AVAILABLE)
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
