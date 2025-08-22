"""
Simple business endpoints for dashboards/clients.
Provides lightweight data retrieval for businesses and menus.
"""
from __future__ import annotations

from typing import List, Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models import Business, MenuItem

router = APIRouter()


@router.get("/businesses")
async def get_businesses(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return all active businesses with basic info."""
    businesses = db.query(Business).filter(Business.is_active == True).all()  # noqa: E712
    return [
        {
            "id": biz.id,
            "name": biz.name,
            "category": str(biz.category) if biz.category is not None else None,
            "description": biz.description,
            "contact_info": biz.contact_info,
        }
        for biz in businesses
    ]


@router.get("/business/{business_id}/menu")
async def get_business_menu(business_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return available menu items for a given business."""
    items: List[MenuItem] = (
        db.query(MenuItem)
        .filter(MenuItem.business_id == business_id, MenuItem.is_available == True)  # noqa: E712
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "price": float(item.base_price or 0),
            "category": item.category.name if getattr(item, "category", None) else "Other",
        }
        for item in items
    ]


@router.get("/business/{business_id}/orders")
async def get_business_orders(business_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Placeholder for orders; implement when order model/views are finalized."""
    return []


@router.get("/business/{business_id}/bookings")
async def get_business_bookings(business_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Placeholder for bookings; implement when booking model/views are available."""
    return []
