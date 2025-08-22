"""Order management endpoints."""
from typing import Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user_optional    
from app.models import Order, OrderStatus, PaymentStatus, Business, User, MenuItem, PaymentMethod
from app.schemas.order import (
    OrderCreate,
    OrderUpdate,
    OrderResponse,
    OrderStatusUpdate
)
from app.services.business.order_service import OrderService
from app.services.notifications.notification_service import NotificationService
from app.services.websocket.connection_manager import manager

router = APIRouter()


@router.get("/", response_model=List[OrderResponse])
async def get_orders(
    status: Optional[OrderStatus] = None,
    table_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get orders for the business with optional filters.
    
    Query parameters:
    - status: Filter by order status
    - table_id: Filter by table
    - limit: Maximum number of orders to return
    - offset: Number of orders to skip
    """
    order_service = OrderService(db)
    
    if status:
        # Use the business service to get orders by status
        orders = order_service.get_orders_by_status(business.id, status)
    else:
        # Get all orders with basic filtering
        query = db.query(Order).filter(Order.business_id == business.id)
        
        if table_id:
            query = query.filter(Order.table_id == table_id)
        
        # Order by most recent first
        orders = query.order_by(Order.created_at.desc()).limit(limit).offset(offset).all()
    
    return orders


@router.get("/active", response_model=List[OrderResponse])
async def get_active_orders(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Get all active orders (not completed or cancelled)."""
    order_service = OrderService(db)
    return order_service.get_active_orders(business.id)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Get specific order details."""
    order_service = OrderService(db)
    
    try:
        # Use the business service to get order summary
        order_summary = order_service.get_order_summary(order_id, business.id)
        
        # Get the full order object for the response
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.business_id == business.id
        ).first()
        
        if not order:
            raise ValueError("Order not found")
        
        return order
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
    current_user: Optional[User] = Depends(get_current_user_optional)  # Optional for guest orders
) -> Any:
    """
    Create a new order.
    
    This endpoint now delegates all business logic to the OrderService.
    The service handles validation, creation, and notifications.
    """
    order_service = OrderService(db)
    
    try:
        # Create order using the authoritative business service
        # All validation, notifications, and business logic are handled here
        order = order_service.create_order(
            business_id=business.id,
            order_data=order_data,
            customer_id=current_user.id if current_user else None
        )
        
        # Send WebSocket notification to kitchen dashboard
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "new_order",
                "order_id": order.id,
                "table_id": order.table_id,
                "items": order.items,
                "total": order.total_amount
            }
        )
        
        return order
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update order status using the authoritative OrderService.
    
    Status flow:
    PENDING -> CONFIRMED -> PREPARING -> READY -> COMPLETED
    Any status can go to CANCELLED
    """
    order_service = OrderService(db)
    
    try:
        # Use the appropriate business service method based on status
        if status_update.status == OrderStatus.CONFIRMED:
            order = order_service.confirm_order(order_id, business.id)
        elif status_update.status == OrderStatus.PREPARING:
            estimated_minutes = getattr(status_update, 'estimated_minutes', 15)
            order = order_service.start_preparation(order_id, business.id, estimated_minutes)
        elif status_update.status == OrderStatus.READY:
            order = order_service.mark_ready(order_id, business.id)
        elif status_update.status == OrderStatus.COMPLETED:
            order = order_service.complete_order(order_id, business.id)
        elif status_update.status == OrderStatus.CANCELLED:
            reason = getattr(status_update, 'reason', 'Staff request')
            order = order_service.cancel_order(order_id, business.id, reason)
        else:
            # Fallback to legacy method for other statuses
            order = order_service.update_order_status(
                order_id, 
                status_update.status,
                getattr(status_update, 'estimated_minutes', None)
            )
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "order_status_update",
                "order_id": order.id,
                "status": order.status.value,
                "table_id": order.table_id
            }
        )
        
        return order
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{order_id}/payment", response_model=OrderResponse)
async def update_payment_status(
    order_id: int,
    payment_status: PaymentStatus,
    payment_method: Optional[str] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update payment status using the authoritative OrderService.
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.update_payment_status(
            order_id, 
            business.id, 
            payment_status, 
            payment_method
        )
        
        return order
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{order_id}/tip", response_model=OrderResponse)
async def add_tip(
    order_id: int,
    tip_amount: float,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Add tip to an order using the authoritative OrderService.
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.add_tip(order_id, business.id, tip_amount)
        
        return order
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{order_id}/summary")
async def get_order_summary(
    order_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get comprehensive order summary including status and timing information.
    """
    order_service = OrderService(db)
    
    try:
        summary = order_service.get_order_summary(order_id, business.id)
        return summary
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order(
    order_id: int,
    reason: str = "Customer request",
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> None:
    """
    Cancel an order using the authoritative OrderService.
    """
    order_service = OrderService(db)
    
    try:
        await order_service.cancel_order(order_id, business.id, reason)
        
        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "order_cancelled",
                "order_id": order_id,
                "reason": reason
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/table/{table_id}", response_model=List[OrderResponse])
async def get_orders_by_table(
    table_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get all orders for a specific table.
    """
    orders = db.query(Order).filter(
        Order.business_id == business.id,
        Order.table_id == table_id
    ).order_by(Order.created_at.desc()).all()
    
    return orders


@router.get("/stats/summary")
async def get_order_stats(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get order statistics for the business.
    """
    order_service = OrderService(db)
    
    # Get orders by status
    pending_orders = order_service.get_orders_by_status(business.id, OrderStatus.PENDING)
    confirmed_orders = order_service.get_orders_by_status(business.id, OrderStatus.CONFIRMED)
    preparing_orders = order_service.get_orders_by_status(business.id, OrderStatus.PREPARING)
    ready_orders = order_service.get_orders_by_status(business.id, OrderStatus.READY)
    
    # Calculate totals
    total_pending = sum(order.total_amount for order in pending_orders)
    total_confirmed = sum(order.total_amount for order in confirmed_orders)
    total_preparing = sum(order.total_amount for order in preparing_orders)
    total_ready = sum(order.total_amount for order in ready_orders)
    
    return {
        "pending": {
            "count": len(pending_orders),
            "total_amount": total_pending
        },
        "confirmed": {
            "count": len(confirmed_orders),
            "total_amount": total_confirmed
        },
        "preparing": {
            "count": len(preparing_orders),
            "total_amount": total_preparing
        },
        "ready": {
            "count": len(ready_orders),
            "total_amount": total_ready
        },
        "total_active": {
            "count": len(pending_orders) + len(confirmed_orders) + len(preparing_orders) + len(ready_orders),
            "total_amount": total_pending + total_confirmed + total_preparing + total_ready
        }
    }