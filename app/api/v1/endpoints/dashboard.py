"""Admin dashboard endpoints."""
from typing import Any, List, Optional, Dict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, Order, Message, User, OrderStatus
from app.services.websocket.connection_manager import manager

router = APIRouter()


@router.get("/overview")
async def get_dashboard_overview(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """Get dashboard overview statistics."""
    today = datetime.utcnow().date()

    # Today's orders
    today_orders = db.query(Order).filter(
        Order.business_id == business.id,
        func.date(Order.created_at) == today
    ).all()

    # Calculate statistics
    total_orders = len(today_orders)
    total_revenue = sum(order.total_amount for order in today_orders)
    pending_orders = len([o for o in today_orders if o.status == OrderStatus.PENDING])
    completed_orders = len([o for o in today_orders if o.status == OrderStatus.COMPLETED])

    # Active conversations
    active_conversations = db.query(Message).filter(
        Message.business_id == business.id,
        Message.created_at >= datetime.utcnow() - timedelta(hours=1)
    ).distinct(Message.session_id).count()

    return {
        "today": {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "average_order_value": total_revenue / total_orders if total_orders > 0 else 0
        },
        "active_conversations": active_conversations,
        "business_status": "online" if business.is_active else "offline"
    }


@router.get("/conversations")
async def get_active_conversations(
    limit: int = 20,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> List[Dict[str, Any]]:
    """Get active customer conversations."""

    # Get recent messages grouped by session
    subquery = db.query(
        Message.session_id,
        func.max(Message.created_at).label('last_message_time')
    ).filter(
        Message.business_id == business.id
    ).group_by(Message.session_id).subquery()

    # Get conversation details
    conversations = db.query(Message).join(
        subquery,
        (Message.session_id == subquery.c.session_id) &
        (Message.created_at == subquery.c.last_message_time)
    ).filter(
        Message.business_id == business.id
    ).order_by(Message.created_at.desc()).limit(limit).all()

    result = []
    for conv in conversations:
        # Get message count for this session
        message_count = db.query(Message).filter(
            Message.session_id == conv.session_id
        ).count()

        result.append({
            "session_id": conv.session_id,
            "last_message": conv.content,
            "last_message_time": conv.created_at,
            "message_count": message_count,
            "status": "active" if (datetime.utcnow() - conv.created_at).seconds < 3600 else "idle"
        })

    return result


@router.post("/takeover/{session_id}")
async def takeover_conversation(
    session_id: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Take over a conversation from the bot."""

    # Verify session belongs to business
    message = db.query(Message).filter(
        Message.session_id == session_id,
        Message.business_id == business.id
    ).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Mark conversation as human-controlled
    # In production, store this in Redis or database
    await manager.send_to_session(
        session_id,
        {
            "type": "takeover",
            "message": f"Staff member {current_user.name} has joined the conversation",
            "staff_id": current_user.id
        }
    )

    return {
        "status": "success",
        "message": "Conversation takeover successful",
        "staff_name": current_user.name
    }


@router.websocket("/live/{session_id}")
async def dashboard_websocket(
    websocket: WebSocket,
    session_id: str,
    db: Session = Depends(get_db)
):
    """WebSocket for live dashboard updates."""
    await manager.connect(websocket, f"dashboard_{session_id}")

    try:
        while True:
            # Keep connection alive and send updates
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(f"dashboard_{session_id}")


@router.get("/orders/live")
async def get_live_orders(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> List[Dict[str, Any]]:
    """Get live order feed."""
    active_statuses = [
        OrderStatus.PENDING,
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.READY
    ]

    orders = db.query(Order).filter(
        Order.business_id == business.id,
        Order.status.in_(active_statuses)
    ).order_by(Order.created_at.desc()).all()

    return [
        {
            "id": order.id,
            "table_id": order.table_id,
            "items": order.items,
            "total": order.total_amount,
            "status": order.status,
            "created_at": order.created_at,
            "estimated_ready": order.estimated_ready_time,
            "special_instructions": order.special_instructions
        }
        for order in orders
    ]