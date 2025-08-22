"""Kitchen display and management endpoints."""
from typing import Any, List, Dict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business, Order, OrderStatus
from app.services.websocket.connection_manager import manager

router = APIRouter()


@router.get("/orders/pending")
async def get_pending_kitchen_orders(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> List[Dict[str, Any]]:
    """Get pending orders for kitchen display."""
    orders = db.query(Order).filter(
        Order.business_id == business.id,
        Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.PREPARING])
    ).order_by(Order.created_at).all()

    return [
        {
            "id": order.id,
            "order_number": f"#{order.id:04d}",
            "table": f"Table {order.table_id}" if order.table_id else "Takeout",
            "items": order.items,
            "status": order.status,
            "time_elapsed": (datetime.utcnow() - order.created_at).seconds // 60,
            "special_instructions": order.special_instructions,
            "priority": "high" if (datetime.utcnow() - order.created_at).seconds > 900 else "normal"
        }
        for order in orders
    ]


@router.put("/orders/{order_id}/start")
async def start_preparing_order(
    order_id: int,
    estimated_minutes: int = 15,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Mark order as being prepared."""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.business_id == business.id
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    order.status = OrderStatus.PREPARING
    order.estimated_ready_time = datetime.utcnow() + timedelta(minutes=estimated_minutes)
    db.commit()

    # Notify customer via WebSocket
    await manager.send_to_session(
        order.session_id,
        {
            "type": "order_update",
            "status": "preparing",
            "message": f"Your order is being prepared! Estimated time: {estimated_minutes} minutes"
        }
    )

    return {"status": "success", "estimated_ready": order.estimated_ready_time}


@router.put("/orders/{order_id}/complete")
async def complete_order(
    order_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Mark order as ready for pickup/delivery."""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.business_id == business.id
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    order.status = OrderStatus.READY
    db.commit()

    # Notify customer
    await manager.send_to_session(
        order.session_id,
        {
            "type": "order_ready",
            "message": "Your order is ready! Please collect it from the counter."
        }
    )

    return {"status": "success", "message": "Order marked as ready"}


@router.post("/notify")
async def send_kitchen_notification(
    message: str,
    priority: str = "normal",
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Send notification to kitchen staff."""
    await manager.broadcast_to_business(
        business.id,
        {
            "type": "kitchen_notification",
            "message": message,
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

    return {"status": "notification_sent"}