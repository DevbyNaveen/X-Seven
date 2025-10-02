"""Menu management endpoints compatible with User object from dependencies."""
from typing import List, Optional, Dict, Any, Union, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from app.core.dependencies import get_current_user, get_current_business, get_supabase_with_auth_context
from app.models.user import User
from app.models.business import Business
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class MenuItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category_id: str  # UUID as string
    image_url: Optional[str] = None
    is_available: bool = True
    preparation_time: Optional[int] = None
    sort_order: int = 0

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[str] = None  # UUID as string
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    preparation_time: Optional[int] = None
    sort_order: Optional[int] = None

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
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> List[dict]:
    """Get all menu items with filtering options."""
    try:
        # Start building the query
        query = supabase.table("menu_items").select("*").eq("business_id", str(current_business.id))

        # Apply filters
        if category_id is not None:
            query = query.eq("category_id", category_id)

        if is_available is not None:
            query = query.eq("is_available", is_available)

        if search:
            # Use ilike for case-insensitive search
            query = query.or_(f"name.ilike.%{search}%,description.ilike.%{search}%")

        # Execute query and order by created_at desc
        response = query.order("created_at", desc=True).execute()

        if response.data:
            logger.info(f"Found {len(response.data)} menu items for business {current_business.id}")
            return response.data
        else:
            logger.info(f"No menu items found for business {current_business.id}")
            return []

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching menu items: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch menu items: {str(e)}"
        )

@router.post("/items", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    item_data: MenuItemCreate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> dict:
    """Create a new menu item."""
    try:
        # Verify category exists for this business
        category_response = supabase.table("menu_categories").select("id").eq(
            "id", item_data.category_id
        ).eq("business_id", str(current_business.id)).execute()

        if not category_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found for this business"
            )

        # Prepare data for insertion
        menu_item_data = {
            "business_id": str(current_business.id),
            "name": item_data.name,
            "description": item_data.description,
            "price": item_data.price,
            "category_id": item_data.category_id,
            "image_url": item_data.image_url,
            "is_available": item_data.is_available,
            "preparation_time": item_data.preparation_time,
            "sort_order": item_data.sort_order
        }

        # Insert the menu item
        response = supabase.table("menu_items").insert(menu_item_data).execute()

        if response.data:
            logger.info(f"Created menu item: {item_data.name} for business {current_business.id}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create menu item"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating menu item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create menu item: {str(e)}"
        )

@router.put("/items/{item_id}", response_model=dict)
async def update_menu_item(
    item_id: str,  # UUID as string
    item_data: MenuItemUpdate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> dict:
    """Update a menu item (price, availability, etc.)."""
    try:
        # Verify menu item exists and belongs to this business
        existing_item = supabase.table("menu_items").select("*").eq(
            "id", item_id
        ).eq("business_id", str(current_business.id)).execute()

        if not existing_item.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )

        # Prepare update data
        update_data = {}
        for field in ["name", "description", "price", "category_id", "image_url", "is_available", "preparation_time", "sort_order"]:
            value = getattr(item_data, field)
            if value is not None:
                update_data[field] = value

        if not update_data:
            # Return existing item if no updates
            return existing_item.data[0]

        # Update the menu item
        response = supabase.table("menu_items").update(update_data).eq(
            "id", item_id
        ).eq("business_id", str(current_business.id)).execute()

        if response.data:
            logger.info(f"Updated menu item {item_id} for business {current_business.id}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update menu item"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating menu item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update menu item: {str(e)}"
        )

@router.delete("/items/{item_id}", response_model=dict)
async def delete_menu_item(
    item_id: str,  # UUID as string
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> dict:
    """Remove a menu item."""
    try:
        # Verify menu item exists and belongs to this business
        existing_item = supabase.table("menu_items").select("id").eq(
            "id", item_id
        ).eq("business_id", str(current_business.id)).execute()

        if not existing_item.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )

        # Delete the menu item
        response = supabase.table("menu_items").delete().eq(
            "id", item_id
        ).eq("business_id", str(current_business.id)).execute()

        logger.info(f"Deleted menu item {item_id} for business {current_business.id}")
        return {
            "status": "success",
            "message": "Menu item deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting menu item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete menu item: {str(e)}"
        )

@router.get("/categories", response_model=List[dict])
async def get_menu_categories(
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> List[dict]:
    """Get all menu categories for the business."""
    try:
        response = supabase.table("menu_categories").select("*").eq(
            "business_id", str(current_business.id)
        ).order("created_at", desc=True).execute()

        if response.data:
            logger.info(f"Found {len(response.data)} categories for business {current_business.id}")
            return response.data
        else:
            logger.info(f"No categories found for business {current_business.id}")
            return []

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch menu categories: {str(e)}"
        )

@router.post("/categories", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_menu_category(
    category_data: MenuCategoryCreate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> dict:
    """Create a new menu category."""
    try:
        # Check if category with same name already exists for this business
        existing_response = supabase.table("menu_categories").select("id").eq(
            "name", category_data.name
        ).eq("business_id", str(current_business.id)).execute()

        if existing_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category with this name already exists"
            )

        # Prepare data for insertion
        category_data_dict = {
            "business_id": str(current_business.id),
            "name": category_data.name,
            "description": category_data.description,
            "sort_order": 0,
            "is_active": True
        }

        # Insert the category
        response = supabase.table("menu_categories").insert(category_data_dict).execute()

        if response.data:
            logger.info(f"Created category: {category_data.name} for business {current_business.id}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create menu category"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create menu category: {str(e)}"
        )

@router.put("/categories/{category_id}", response_model=dict)
async def update_menu_category(
    category_id: str,  # UUID as string
    category_data: MenuCategoryUpdate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> dict:
    """Update a menu category."""
    try:
        # Verify category exists and belongs to this business
        existing_category = supabase.table("menu_categories").select("*").eq(
            "id", category_id
        ).eq("business_id", str(current_business.id)).execute()

        if not existing_category.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        # Prepare update data
        update_data = {}
        for field in ["name", "description"]:
            value = getattr(category_data, field)
            if value is not None:
                update_data[field] = value

        if not update_data:
            # Return existing category if no updates
            return existing_category.data[0]

        # Update the category
        response = supabase.table("menu_categories").update(update_data).eq(
            "id", category_id
        ).eq("business_id", str(current_business.id)).execute()

        if response.data:
            logger.info(f"Updated category {category_id} for business {current_business.id}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update menu category"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating category: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update menu category: {str(e)}"
        )

@router.delete("/categories/{category_id}", response_model=dict)
async def delete_menu_category(
    category_id: str,  # UUID as string
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> dict:
    """Delete a menu category."""
    try:
        # Verify category exists and belongs to this business
        existing_category = supabase.table("menu_categories").select("*").eq(
            "id", category_id
        ).eq("business_id", str(current_business.id)).execute()

        if not existing_category.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        # Check if there are menu items in this category
        items_count_response = supabase.table("menu_items").select("id", count="exact").eq(
            "category_id", category_id
        ).execute()

        if items_count_response.count and items_count_response.count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete category with existing menu items"
            )

        # Delete the category
        response = supabase.table("menu_categories").delete().eq(
            "id", category_id
        ).eq("business_id", str(current_business.id)).execute()

        logger.info(f"Deleted category {category_id} for business {current_business.id}")
        return {
            "status": "success",
            "message": "Category deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting category: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete menu category: {str(e)}"
        )

@router.put("/items/{item_id}/availability", response_model=dict)
async def toggle_item_availability(
    item_id: str,  # UUID as string
    availability_data: MenuItemAvailabilityUpdate,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_with_auth_context)
) -> dict:
    """Toggle item availability."""
    try:
        # Verify menu item exists and belongs to this business
        existing_item = supabase.table("menu_items").select("*").eq(
            "id", item_id
        ).eq("business_id", str(current_business.id)).execute()

        if not existing_item.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Menu item not found"
            )

        # Update availability
        update_data = {"is_available": availability_data.is_available}
        response = supabase.table("menu_items").update(update_data).eq(
            "id", item_id
        ).eq("business_id", str(current_business.id)).execute()

        if response.data:
            logger.info(f"Updated availability for item {item_id} to {availability_data.is_available}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update item availability"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle item availability: {str(e)}"
        )