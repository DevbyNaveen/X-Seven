"""Menu management endpoints for food businesses."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User, MenuItem, MenuCategory

router = APIRouter()

class MenuItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    base_price: float
    category_id: int
    image_url: Optional[str] = None
    is_available: bool = True
    preparation_time: Optional[int] = None
    dietary_tags: Optional[List[str]] = []
    allergens: Optional[List[str]] = []
    calories: Optional[int] = None
    customizations: Optional[List[dict]] = []
    stock_quantity: Optional[int] = 0

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[float] = None
    category_id: Optional[int] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    preparation_time: Optional[int] = None
    dietary_tags: Optional[List[str]] = None
    allergens: Optional[List[str]] = None
    calories: Optional[int] = None
    customizations: Optional[List[dict]] = None
    stock_quantity: Optional[int] = None

class MenuItemAvailabilityUpdate(BaseModel):
    is_available: bool

class MenuCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

@router.get("/items", response_model=List[dict])
async def get_menu_items(
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all menu items with filtering options."""
    query = db.query(MenuItem).filter(MenuItem.business_id == current_business.id)
    
    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)
    
    if is_available is not None:
        query = query.filter(MenuItem.is_available == is_available)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            func.lower(MenuItem.name).contains(func.lower(search_filter)) |
            func.lower(MenuItem.description).contains(func.lower(search_filter))
        )
    
    items = query.order_by(MenuItem.created_at.desc()).all()
    
    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "base_price": item.base_price,
            "category_id": item.category_id,
            "image_url": item.image_url,
            "is_available": item.is_available,
            "preparation_time": item.preparation_time,
            "dietary_tags": item.dietary_tags,
            "allergens": item.allergens,
            "calories": item.calories,
            "customizations": item.customizations,
            "stock_quantity": item.stock_quantity,
            "display_order": item.display_order,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
        for item in items
    ]

@router.post("/items", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    item_data: MenuItemCreate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Create a new menu item."""
    # Verify category exists for this business
    category = db.query(MenuCategory).filter(
        MenuCategory.id == item_data.category_id,
        MenuCategory.business_id == current_business.id
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found for this business"
        )
    
    # Create menu item
    menu_item = MenuItem(
        business_id=current_business.id,
        name=item_data.name,
        description=item_data.description,
        base_price=item_data.base_price,
        category_id=item_data.category_id,
        image_url=item_data.image_url,
        is_available=item_data.is_available,
        preparation_time=item_data.preparation_time,
        dietary_tags=item_data.dietary_tags or [],
        allergens=item_data.allergens or [],
        calories=item_data.calories,
        customizations=item_data.customizations or [],
        stock_quantity=item_data.stock_quantity or 0
    )
    
    db.add(menu_item)
    db.commit()
    db.refresh(menu_item)
    
    return {
        "id": menu_item.id,
        "name": menu_item.name,
        "description": menu_item.description,
        "price": menu_item.price,
        "category_id": menu_item.category_id,
        "image_url": menu_item.image_url,
        "is_available": menu_item.is_available,
        "preparation_time": menu_item.preparation_time,
        "created_at": menu_item.created_at
    }

@router.put("/items/{item_id}", response_model=dict)
async def update_menu_item(
    item_id: int,
    item_data: MenuItemUpdate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Update a menu item (price, availability, etc.)."""
    # Find menu item for this business
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.business_id == current_business.id
    ).first()
    
    if not menu_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    
    # Update fields if provided
    update_data = item_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(menu_item, field, value)
    
    menu_item.updated_at = func.now()
    db.commit()
    db.refresh(menu_item)
    
    return {
        "id": menu_item.id,
        "name": menu_item.name,
        "description": menu_item.description,
        "base_price": menu_item.base_price,
        "category_id": menu_item.category_id,
        "image_url": menu_item.image_url,
        "is_available": menu_item.is_available,
        "preparation_time": menu_item.preparation_time,
        "dietary_tags": menu_item.dietary_tags,
        "allergens": menu_item.allergens,
        "calories": menu_item.calories,
        "customizations": menu_item.customizations,
        "stock_quantity": menu_item.stock_quantity,
        "display_order": menu_item.display_order,
        "updated_at": menu_item.updated_at
    }

@router.delete("/items/{item_id}", response_model=dict)
async def delete_menu_item(
    item_id: int,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Remove a menu item."""
    # Find menu item for this business
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.business_id == current_business.id
    ).first()
    
    if not menu_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    
    db.delete(menu_item)
    db.commit()
    
    return {
        "status": "success",
        "message": "Menu item deleted successfully"
    }

@router.get("/categories", response_model=List[dict])
async def get_menu_categories(
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all menu categories for the business."""
    categories = db.query(MenuCategory).filter(
        MenuCategory.business_id == current_business.id
    ).order_by(MenuCategory.created_at.desc()).all()
    
    return [
        {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "created_at": category.created_at,
            "updated_at": category.updated_at
        }
        for category in categories
    ]

@router.post("/categories", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_menu_category(
    category_data: MenuCategoryCreate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Create a new menu category."""
    # Check if category with same name already exists for this business
    existing_category = db.query(MenuCategory).filter(
        MenuCategory.name == category_data.name,
        MenuCategory.business_id == current_business.id
    ).first()
    
    if existing_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )
    
    # Create category
    category = MenuCategory(
        business_id=current_business.id,
        name=category_data.name,
        description=category_data.description
    )
    
    db.add(category)
    db.commit()
    db.refresh(category)
    
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "created_at": category.created_at
    }

@router.put("/categories/{category_id}", response_model=dict)
async def update_menu_category(
    category_id: int,
    category_data: MenuCategoryUpdate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Update a menu category."""
    # Find category for this business
    category = db.query(MenuCategory).filter(
        MenuCategory.id == category_id,
        MenuCategory.business_id == current_business.id
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Update fields if provided
    update_data = category_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    
    category.updated_at = func.now()
    db.commit()
    db.refresh(category)
    
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "updated_at": category.updated_at
    }

@router.delete("/categories/{category_id}", response_model=dict)
async def delete_menu_category(
    category_id: int,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Delete a menu category."""
    # Find category for this business
    category = db.query(MenuCategory).filter(
        MenuCategory.id == category_id,
        MenuCategory.business_id == current_business.id
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check if there are menu items in this category
    items_count = db.query(MenuItem).filter(
        MenuItem.category_id == category_id
    ).count()
    
    if items_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category with existing menu items"
        )
    
    db.delete(category)
    db.commit()
    
    return {
        "status": "success",
        "message": "Category deleted successfully"
    }

@router.put("/items/{item_id}/availability", response_model=dict)
async def toggle_item_availability(
    item_id: int,
    availability_data: MenuItemAvailabilityUpdate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Toggle item availability."""
    # Find menu item for this business
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.business_id == current_business.id
    ).first()
    
    if not menu_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    
    menu_item.is_available = availability_data.is_available
    menu_item.updated_at = func.now()
    db.commit()
    db.refresh(menu_item)
    
    return {
        "id": menu_item.id,
        "name": menu_item.name,
        "is_available": menu_item.is_available,
        "updated_at": menu_item.updated_at
    }
