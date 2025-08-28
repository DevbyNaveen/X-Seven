"""Food order management endpoints for AI integration."""
from typing import Any, List, Optional, Dict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Order, OrderStatus, Business, User, MenuItem
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate
from app.services.business.order_service import OrderService
from app.services.websocket.connection_manager import manager

router = APIRouter()


@router.get("/active", response_model=List[OrderResponse])
async def get_active_orders(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get live pending/preparing orders for food service.
    """
    # Get active orders (PENDING, CONFIRMED, PREPARING, READY)
    active_statuses = [
        OrderStatus.PENDING,
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.READY
    ]
    
    orders = db.query(Order).filter(
        and_(
            Order.business_id == business.id,
            Order.status.in_(active_statuses)
        )
    ).order_by(Order.created_at.desc()).all()
    
    return orders


@router.get("/history", response_model=List[OrderResponse])
async def get_order_history(
    status: Optional[OrderStatus] = Query(None, description="Filter by order status"),
    start_date: Optional[datetime] = Query(None, description="Filter orders after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter orders before this date"),
    limit: int = Query(50, description="Maximum number of orders to return"),
    offset: int = Query(0, description="Number of orders to skip"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get order history with filters.
    """
    query = db.query(Order).filter(Order.business_id == business.id)
    
    # Apply filters
    if status:
        query = query.filter(Order.status == status)
    
    if start_date:
        query = query.filter(Order.created_at >= start_date)
    
    if end_date:
        query = query.filter(Order.created_at <= end_date)
    
    # Order by most recent first
    orders = query.order_by(Order.created_at.desc()).limit(limit).offset(offset).all()
    
    return orders


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_food_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Create new food order.
    """
    order_service = OrderService(db)
    
    try:
        # Create order using the business service
        order = order_service.create_order(
            business_id=business.id,
            order_data=order_data,
            customer_id=current_user.id if current_user else None
        )
        
        # Send WebSocket notification to kitchen
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "new_food_order",
                "order_id": order.id,
                "table_id": order.table_id,
                "items": order.items,
                "total": order.total_amount,
                "customer_name": order.customer_name
            }
        )
        
        return order
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_food_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update food order status.
    """
    order_service = OrderService(db)
    
    try:
        # Verify order belongs to business
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.business_id == business.id
        ).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Update order status
        updated_order = order_service.update_order_status(
            order_id, 
            status_update.status,
            getattr(status_update, 'estimated_time', None)
        )
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "food_order_status_update",
                "order_id": order_id,
                "status": status_update.status.value,
                "table_id": order.table_id
            }
        )
        
        return updated_order
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/stats", response_model=Dict[str, Any])
async def get_food_order_stats(
    period: str = Query("7d", description="Period for stats: 1d, 7d, 30d"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get food order statistics.
    """
    # Determine date range based on period
    if period == "1d":
        start_date = datetime.utcnow() - timedelta(days=1)
    elif period == "30d":
        start_date = datetime.utcnow() - timedelta(days=30)
    else:  # Default to 7 days
        start_date = datetime.utcnow() - timedelta(days=7)
    
    # Get orders in the period
    orders = db.query(Order).filter(
        and_(
            Order.business_id == business.id,
            Order.created_at >= start_date
        )
    ).all()
    
    # Group by status
    status_counts = {}
    total_revenue = 0
    
    for order in orders:
        status = order.status.value
        if status not in status_counts:
            status_counts[status] = {"count": 0, "revenue": 0}
        status_counts[status]["count"] += 1
        status_counts[status]["revenue"] += order.total_amount
        total_revenue += order.total_amount
    
    # Calculate average order value
    avg_order_value = total_revenue / len(orders) if orders else 0
    
    return {
        "period": period,
        "total_orders": len(orders),
        "total_revenue": total_revenue,
        "average_order_value": avg_order_value,
        "status_breakdown": status_counts
    }


@router.get("/kitchen-queue", response_model=List[OrderResponse])
async def get_kitchen_queue(
    status: OrderStatus = Query(OrderStatus.PREPARING, description="Filter by order status"),
    limit: int = Query(20, description="Maximum number of orders to return"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Kitchen-specific order view.
    """
    # Get orders for kitchen queue (typically PREPARING status)
    orders = db.query(Order).filter(
        and_(
            Order.business_id == business.id,
            Order.status == status
        )
    ).order_by(Order.created_at.asc()).limit(limit).all()  # Oldest first for FIFO
    
    return orders
