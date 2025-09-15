"""Menu category model for restaurant menus using Supabase."""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.base import SupabaseModel


class MenuCategory(SupabaseModel):
    """Menu category model for organizing menu items."""
    table_name = "menu_categories"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.business_id = kwargs.get('business_id')
        self.name = kwargs.get('name')
        self.description = kwargs.get('description')
        self.sort_order = kwargs.get('sort_order', 0)
        self.is_active = kwargs.get('is_active', True)
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
