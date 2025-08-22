"""Menu models for categories and items."""
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class MenuCategory(BaseModel):
    """
    Menu categories like 'Beverages', 'Main Dishes', etc.
    
    Helps organize menu items for better UX.
    """
    __tablename__ = "menu_categories"
    
    # Multi-tenant
    business_id = Column(
        Integer, 
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Category info
    name = Column(String(100), nullable=False)
    description = Column(Text)
    display_order = Column(Integer, default=0)  # For sorting
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Display settings
    icon = Column(String(50))  # emoji or icon name
    image_url = Column(String(500))
    
    # Multi-language support
    translations = Column(JSON, default=dict)
    # Example: {
    #   "es": {"name": "Bebidas", "description": "Bebidas calientes y frías"},
    #   "fr": {"name": "Boissons", "description": "Boissons chaudes et froides"}
    # }
    
    # Relationships
    business = relationship("Business", back_populates="menu_categories")
    items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MenuCategory {self.name}>"


class MenuItem(BaseModel):
    """
    Individual menu items that customers can order.
    
    Contains all information needed for AI to describe
    and customers to order.
    """
    __tablename__ = "menu_items"
    
    # Multi-tenant
    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Category
    category_id = Column(
        Integer,
        ForeignKey("menu_categories.id", ondelete="SET NULL")
    )
    
    # Basic info
    name = Column(String(200), nullable=False)
    description = Column(Text)
    base_price = Column(Float, nullable=False)
    
    # Availability
    is_available = Column(Boolean, default=True, nullable=False)
    preparation_time = Column(Integer, default=10)  # minutes
    
    # Dietary information (for AI to filter)
    dietary_tags = Column(JSON, default=list)
    # Example: ["vegan", "gluten-free", "dairy-free", "nut-free"]
    
    allergens = Column(JSON, default=list)
    # Example: ["milk", "eggs", "peanuts", "soy"]
    
    # Nutritional info (optional)
    calories = Column(Integer)
    
    # Display
    image_url = Column(String(500))
    display_order = Column(Integer, default=0)
    
    # Customization options
    customizations = Column(JSON, default=list)
    # Example: [
    #   {"name": "Size", "options": ["Small", "Medium", "Large"], "price_diff": [0, 1.5, 3]},
    #   {"name": "Milk", "options": ["Regular", "Oat", "Almond"], "price_diff": [0, 0.5, 0.5]}
    # ]
    
    # Inventory management
    stock_quantity = Column(Integer, default=0)  # 0 means unlimited
    min_stock_threshold = Column(Integer, default=5)  # Alert when stock goes below this
    
    # Multi-language support
    translations = Column(JSON, default=dict)
    # Example: {
    #   "es": {"name": "Café con Leche", "description": "Café con leche tradicional"},
    #   "fr": {"name": "Café au Lait", "description": "Café au lait traditionnel"}
    # }
    
    # Relationships
    business = relationship("Business", back_populates="menu_items")
    category = relationship("MenuCategory", back_populates="items")
    
    def __repr__(self):
        return f"<MenuItem {self.name} - ${self.base_price}>"