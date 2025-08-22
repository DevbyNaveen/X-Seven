"""Customer management endpoints."""
from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import logging

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User, Order, Message, UserRole
from app.models.order import OrderStatus
from app.schemas.customer import (
    CustomerProfile, 
    CustomerCreate, 
    CustomerUpdate, 
    CustomerPreferences,
    CustomerAnalytics,
    CustomerOrderHistory
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[CustomerProfile])
async def get_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(name|email|phone_number|total_orders|last_order|created_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get all customers for the business with filtering and sorting.
    """
    query = db.query(User).filter(
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER
    )
    
    # Search functionality
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.name.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.phone_number.ilike(search_term))
        )
    
    # Sorting
    if sort_order == "desc":
        query = query.order_by(desc(getattr(User, sort_by)))
    else:
        query = query.order_by(getattr(User, sort_by))
    
    customers = query.offset(skip).limit(limit).all()
    
    # Enhance with order statistics
    customer_profiles = []
    for customer in customers:
        orders = db.query(Order).filter(
            Order.customer_id == customer.id,
            Order.business_id == business.id
        ).all()
        
        total_orders = len(orders)
        total_spent = sum(order.total_amount for order in orders)
        last_order = max(orders, key=lambda x: x.created_at).created_at if orders else None
        
        customer_profiles.append(CustomerProfile(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            phone_number=customer.phone_number,
            is_verified=customer.is_verified,
            preferences=customer.preferences,
            total_orders=total_orders,
            total_spent=total_spent,
            last_order=last_order,
            created_at=customer.created_at,
            is_active=customer.is_active
        ))
    
    return customer_profiles


@router.get("/{customer_id}", response_model=CustomerProfile)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get detailed customer profile with analytics.
    """
    customer = db.query(User).filter(
        User.id == customer_id,
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Get order statistics
    orders = db.query(Order).filter(
        Order.customer_id == customer.id,
        Order.business_id == business.id
    ).all()
    
    total_orders = len(orders)
    total_spent = sum(order.total_amount for order in orders)
    last_order = max(orders, key=lambda x: x.created_at).created_at if orders else None
    
    return CustomerProfile(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone_number=customer.phone_number,
        is_verified=customer.is_verified,
        preferences=customer.preferences,
        total_orders=total_orders,
        total_spent=total_spent,
        last_order=last_order,
        created_at=customer.created_at,
        is_active=customer.is_active
    )


@router.post("/", response_model=CustomerProfile)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Create a new customer profile.
    """
    # Check if customer already exists
    existing_customer = db.query(User).filter(
        User.email == customer_data.email,
        User.business_id == business.id
    ).first()
    
    if existing_customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer with this email already exists"
        )
    
    # Create new customer
    customer = User(
        name=customer_data.name,
        email=customer_data.email,
        phone_number=customer_data.phone_number,
        role=UserRole.CUSTOMER,
        business_id=business.id,
        preferences=customer_data.preferences or {}
    )
    
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    return CustomerProfile(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone_number=customer.phone_number,
        is_verified=customer.is_verified,
        preferences=customer.preferences,
        total_orders=0,
        total_spent=0,
        last_order=None,
        created_at=customer.created_at,
        is_active=customer.is_active
    )


@router.put("/{customer_id}", response_model=CustomerProfile)
async def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update customer profile.
    """
    customer = db.query(User).filter(
        User.id == customer_id,
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Update fields
    if customer_data.name is not None:
        customer.name = customer_data.name
    if customer_data.email is not None:
        customer.email = customer_data.email
    if customer_data.phone_number is not None:
        customer.phone_number = customer_data.phone_number
    if customer_data.is_active is not None:
        customer.is_active = customer_data.is_active
    
    db.commit()
    db.refresh(customer)
    
    # Get updated statistics
    orders = db.query(Order).filter(
        Order.customer_id == customer.id,
        Order.business_id == business.id
    ).all()
    
    total_orders = len(orders)
    total_spent = sum(order.total_amount for order in orders)
    last_order = max(orders, key=lambda x: x.created_at).created_at if orders else None
    
    return CustomerProfile(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone_number=customer.phone_number,
        is_verified=customer.is_verified,
        preferences=customer.preferences,
        total_orders=total_orders,
        total_spent=total_spent,
        last_order=last_order,
        created_at=customer.created_at,
        is_active=customer.is_active
    )


@router.put("/{customer_id}/preferences", response_model=CustomerPreferences)
async def update_customer_preferences(
    customer_id: int,
    preferences: CustomerPreferences,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update customer preferences.
    """
    customer = db.query(User).filter(
        User.id == customer_id,
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Update preferences
    customer.preferences.update(preferences.dict())
    db.commit()
    
    return CustomerPreferences(**customer.preferences)


@router.get("/{customer_id}/orders", response_model=List[CustomerOrderHistory])
async def get_customer_orders(
    customer_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get customer order history.
    """
    customer = db.query(User).filter(
        User.id == customer_id,
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    orders = db.query(Order).filter(
        Order.customer_id == customer.id,
        Order.business_id == business.id
    ).order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
    
    return [
        CustomerOrderHistory(
            id=order.id,
            items=order.items,
            total_amount=order.total_amount,
            status=order.status,
            payment_status=order.payment_status,
            created_at=order.created_at,
            completed_at=order.completed_at
        )
        for order in orders
    ]


@router.get("/{customer_id}/analytics", response_model=CustomerAnalytics)
async def get_customer_analytics(
    customer_id: int,
    time_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get customer analytics and behavior insights.
    """
    customer = db.query(User).filter(
        User.id == customer_id,
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Calculate time range
    end_date = datetime.utcnow()
    if time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    elif time_range == "90d":
        start_date = end_date - timedelta(days=90)
    else:  # 1y
        start_date = end_date - timedelta(days=365)
    
    # Get orders in time range
    orders = db.query(Order).filter(
        Order.customer_id == customer.id,
        Order.business_id == business.id,
        Order.created_at >= start_date,
        Order.created_at <= end_date
    ).all()
    
    # Calculate analytics
    total_orders = len(orders)
    total_spent = sum(order.total_amount for order in orders)
    avg_order_value = total_spent / total_orders if total_orders > 0 else 0
    
    # Most ordered items
    item_counts = {}
    for order in orders:
        for item in order.items:
            item_name = item.get("name", "Unknown")
            item_counts[item_name] = item_counts.get(item_name, 0) + item.get("quantity", 1)
    
    top_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Order frequency
    order_dates = [order.created_at.date() for order in orders]
    unique_days = len(set(order_dates))
    avg_orders_per_day = total_orders / unique_days if unique_days > 0 else 0
    
    # Preferred order times
    hour_counts = {}
    for order in orders:
        hour = order.created_at.hour
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    
    preferred_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return CustomerAnalytics(
        customer_id=customer_id,
        time_range=time_range,
        total_orders=total_orders,
        total_spent=total_spent,
        average_order_value=avg_order_value,
        order_frequency=avg_orders_per_day,
        top_ordered_items=top_items,
        preferred_order_hours=preferred_hours,
        last_order_date=max(order.created_at for order in orders) if orders else None,
        customer_since=customer.created_at
    )


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Delete customer (soft delete - marks as inactive).
    """
    customer = db.query(User).filter(
        User.id == customer_id,
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Soft delete - mark as inactive
    customer.is_active = False
    db.commit()
    
    return {"message": "Customer deleted successfully"}


@router.post("/{customer_id}/verify")
async def verify_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Mark customer as verified.
    """
    customer = db.query(User).filter(
        User.id == customer_id,
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    customer.is_verified = True
    db.commit()
    
    return {"message": "Customer verified successfully"}


@router.get("/analytics/overview")
async def get_customers_analytics_overview(
    time_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get overall customer analytics for the business.
    """
    # Calculate time range
    end_date = datetime.utcnow()
    if time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    elif time_range == "90d":
        start_date = end_date - timedelta(days=90)
    else:  # 1y
        start_date = end_date - timedelta(days=365)
    
    # Total customers
    total_customers = db.query(User).filter(
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER,
        User.is_active == True
    ).count()
    
    # New customers in time range
    new_customers = db.query(User).filter(
        User.business_id == business.id,
        User.role == UserRole.CUSTOMER,
        User.created_at >= start_date,
        User.created_at <= end_date
    ).count()
    
    # Active customers (placed orders in time range)
    active_customers = db.query(Order.customer_id).filter(
        Order.business_id == business.id,
        Order.created_at >= start_date,
        Order.created_at <= end_date
    ).distinct().count()
    
    # Customer retention rate
    previous_period_start = start_date - (end_date - start_date)
    previous_period_customers = db.query(Order.customer_id).filter(
        Order.business_id == business.id,
        Order.created_at >= previous_period_start,
        Order.created_at < start_date
    ).distinct().count()
    
    retention_rate = 0
    if previous_period_customers > 0:
        retained_customers = db.query(Order.customer_id).filter(
            Order.business_id == business.id,
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ).distinct().count()
        retention_rate = (retained_customers / previous_period_customers) * 100
    
    # Average customer lifetime value
    customer_lifetime_values = db.query(
        Order.customer_id,
        func.sum(Order.total_amount).label('total_spent')
    ).filter(
        Order.business_id == business.id
    ).group_by(Order.customer_id).all()
    
    avg_lifetime_value = sum(c.total_spent for c in customer_lifetime_values) / len(customer_lifetime_values) if customer_lifetime_values else 0
    
    return {
        "time_range": time_range,
        "total_customers": total_customers,
        "new_customers": new_customers,
        "active_customers": active_customers,
        "retention_rate": round(retention_rate, 2),
        "average_lifetime_value": round(avg_lifetime_value, 2),
        "customer_growth_rate": round((new_customers / total_customers * 100) if total_customers > 0 else 0, 2)
    }
