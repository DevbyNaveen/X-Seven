"""Menu management endpoints."""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business, MenuCategory, MenuItem, SubscriptionPlan
from app.schemas.menu import (
    MenuCategoryCreate,
    MenuCategoryResponse,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate
)

router = APIRouter()


@router.post("/categories", response_model=MenuCategoryResponse)
async def create_menu_category(
    category_data: MenuCategoryCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Create a new menu category.
    """
    category = MenuCategory(
        name=category_data.name,
        description=category_data.description,
        business_id=business.id,
        display_order=category_data.display_order
    )
    
    db.add(category)
    db.commit()
    db.refresh(category)
    
    return category


@router.get("/categories", response_model=List[MenuCategoryResponse])
async def get_menu_categories(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get all menu categories for the business.
    """
    categories = db.query(MenuCategory).filter(
        MenuCategory.business_id == business.id
    ).order_by(MenuCategory.display_order).all()
    
    return categories


@router.post("/items", response_model=MenuItemResponse)
async def create_menu_item(
    item_data: MenuItemCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Create a new menu item.
    
    Validates subscription plan limits:
    - Basic plan: 50 menu items max
    - Pro/Enterprise: Unlimited menu items
    """
    # Check menu item limit based on subscription plan
    current_menu_items = db.query(MenuItem).filter(
        MenuItem.business_id == business.id
    ).count()
    
    menu_limit = business.get_usage_limit("menu_items")
    
    if menu_limit != -1 and current_menu_items >= menu_limit:  # -1 means unlimited
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "menu_limit_reached",
                "message": f"You have reached the limit of {menu_limit} menu items for your {business.subscription_plan} plan.",
                "current_count": current_menu_items,
                "limit": menu_limit,
                "required_plan": "pro" if business.subscription_plan == SubscriptionPlan.BASIC else None,
                "upgrade_url": "/api/v1/plans"
            }
        )
    
    # Validate category exists and belongs to business
    if item_data.category_id:
        category = db.query(MenuCategory).filter(
            MenuCategory.id == item_data.category_id,
            MenuCategory.business_id == business.id
        ).first()
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found or does not belong to this business"
            )
    
    item = MenuItem(
        name=item_data.name,
        description=item_data.description,
        base_price=item_data.base_price,
        category_id=item_data.category_id,
        business_id=business.id,
        preparation_time=item_data.preparation_time,
        dietary_tags=item_data.dietary_tags or [],
        allergens=item_data.allergens or [],
        calories=item_data.calories,
        image_url=item_data.image_url,
        display_order=item_data.display_order,
        customizations=item_data.customizations or []
    )
    
    db.add(item)
    db.commit()
    db.refresh(item)
    
    return item


@router.get("/items", response_model=List[MenuItemResponse])
async def get_menu_items(
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get menu items for the business, optionally filtered by category.
    """
    query = db.query(MenuItem).filter(MenuItem.business_id == business.id)
    
    if category_id:
        query = query.filter(MenuItem.category_id == category_id)
    
    items = query.order_by(MenuItem.display_order).all()
    return items


@router.get("/items/{item_id}", response_model=MenuItemResponse)
async def get_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get a specific menu item.
    """
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.business_id == business.id
    ).first()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    
    return item


@router.put("/items/{item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    item_id: int,
    item_data: MenuItemUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update a menu item.
    """
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.business_id == business.id
    ).first()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    
    # Update fields
    for field, value in item_data.dict(exclude_unset=True).items():
        setattr(item, field, value)
    
    db.commit()
    db.refresh(item)
    
    return item


@router.delete("/items/{item_id}")
async def delete_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Delete a menu item.
    """
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.business_id == business.id
    ).first()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    
    db.delete(item)
    db.commit()
    
    return {"message": "Menu item deleted successfully"}


@router.get("/usage")
async def get_menu_usage(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get menu usage statistics and limits.
    """
    total_items = db.query(MenuItem).filter(
        MenuItem.business_id == business.id
    ).count()
    
    available_items = db.query(MenuItem).filter(
        MenuItem.business_id == business.id,
        MenuItem.is_available == True
    ).count()
    
    menu_limit = business.get_usage_limit("menu_items")
    
    return {
        "total_items": total_items,
        "available_items": available_items,
        "limit": menu_limit,
        "unlimited": menu_limit == -1,
        "remaining": menu_limit - total_items if menu_limit != -1 else -1,
        "plan": business.subscription_plan,
        "can_add_more": menu_limit == -1 or total_items < menu_limit
    }