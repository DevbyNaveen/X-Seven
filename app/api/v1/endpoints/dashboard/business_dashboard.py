"""Business dashboard endpoints for AI integration."""
from typing import Any, Dict, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, Order, Message, User, OrderStatus
from app.services.websocket.connection_manager import manager

router = APIRouter()


@router.get("/{business_id}", response_model=dict)
async def get_business_details(
    business_id: int,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get current business details."""
    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business"
        )
    
    # Return comprehensive business details
    return {
        "id": current_business.id,
        "name": current_business.name,
        "slug": current_business.slug,
        "description": current_business.description,
        "category": current_business.category,
        "subscription_plan": current_business.subscription_plan,
        "subscription_status": current_business.subscription_status,
        "is_active": current_business.is_active,
        "phone_config": current_business.phone_config,
        "custom_phone_number": current_business.custom_phone_number,
        "custom_whatsapp_number": current_business.custom_whatsapp_number,
        "settings": current_business.settings,
        "branding_config": current_business.branding_config,
        "contact_info": current_business.contact_info,
        "created_at": current_business.created_at,
        "updated_at": current_business.updated_at
    }


@router.get("/{business_id}/dashboard", response_model=dict)
async def get_business_dashboard(
    business_id: int,
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get dashboard overview data."""
    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business"
        )
    
    # Get today's date
    today = datetime.utcnow().date()
    
    # Today's orders
    today_orders = db.query(Order).filter(
        Order.business_id == business_id,
        func.date(Order.created_at) == today
    ).all()
    
    # Calculate statistics
    total_orders = len(today_orders)
    total_revenue = sum(order.total_amount for order in today_orders)
    pending_orders = len([o for o in today_orders if o.status == OrderStatus.PENDING])
    completed_orders = len([o for o in today_orders if o.status == OrderStatus.COMPLETED])
    
    # Active conversations
    active_conversations = db.query(Message).filter(
        Message.business_id == business_id,
        Message.created_at >= datetime.utcnow() - timedelta(hours=1)
    ).distinct(Message.session_id).count()
    
    # Recent orders (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_orders = db.query(Order).filter(
        Order.business_id == business_id,
        Order.created_at >= seven_days_ago
    ).order_by(Order.created_at.desc()).limit(10).all()
    
    return {
        "business": {
            "id": current_business.id,
            "name": current_business.name,
            "category": current_business.category,
            "subscription_plan": current_business.subscription_plan,
            "is_active": current_business.is_active
        },
        "today": {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "average_order_value": total_revenue / total_orders if total_orders > 0 else 0
        },
        "active_conversations": active_conversations,
        "business_status": "online" if current_business.is_active else "offline",
        "recent_orders": [
            {
                "id": order.id,
                "table_id": order.table_id,
                "total_amount": order.total_amount,
                "status": order.status,
                "created_at": order.created_at
            }
            for order in recent_orders
        ]
    }


@router.get("/{business_id}/stats", response_model=dict)
async def get_business_stats(
    business_id: int,
    period: str = "7d",  # 1d, 7d, 30d
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get real-time business statistics."""
    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business"
        )
    
    # Determine date range based on period
    if period == "1d":
        start_date = datetime.utcnow() - timedelta(days=1)
    elif period == "30d":
        start_date = datetime.utcnow() - timedelta(days=30)
    else:  # Default to 7 days
        start_date = datetime.utcnow() - timedelta(days=7)
    
    # Orders statistics
    orders = db.query(Order).filter(
        Order.business_id == business_id,
        Order.created_at >= start_date
    ).all()
    
    # Group orders by date
    orders_by_date = {}
    for order in orders:
        date_key = order.created_at.date().isoformat()
        if date_key not in orders_by_date:
            orders_by_date[date_key] = {"count": 0, "revenue": 0}
        orders_by_date[date_key]["count"] += 1
        orders_by_date[date_key]["revenue"] += order.total_amount
    
    # Conversation statistics
    messages = db.query(Message).filter(
        Message.business_id == business_id,
        Message.created_at >= start_date
    ).all()
    
    # Group messages by date
    messages_by_date = {}
    for message in messages:
        date_key = message.created_at.date().isoformat()
        if date_key not in messages_by_date:
            messages_by_date[date_key] = 0
        messages_by_date[date_key] += 1
    
    # Status distribution
    status_counts = {}
    for order in orders:
        status = order.status
        if status not in status_counts:
            status_counts[status] = 0
        status_counts[status] += 1
    
    return {
        "period": period,
        "orders_over_time": orders_by_date,
        "messages_over_time": messages_by_date,
        "status_distribution": status_counts,
        "total_orders": len(orders),
        "total_revenue": sum(order.total_amount for order in orders),
        "total_messages": len(messages),
        "average_order_value": sum(order.total_amount for order in orders) / len(orders) if orders else 0
    }


@router.put("/{business_id}/config", response_model=dict)
async def update_business_config(
    business_id: int,
    config_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update business configuration."""
    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this business"
        )
    
    # Update business configuration
    # We'll update specific fields based on what's provided
    updated_fields = []
    
    if "settings" in config_data:
        current_business.settings = config_data["settings"]
        updated_fields.append("settings")
    
    if "branding_config" in config_data:
        current_business.branding_config = config_data["branding_config"]
        updated_fields.append("branding_config")
    
    if "contact_info" in config_data:
        current_business.contact_info = config_data["contact_info"]
        updated_fields.append("contact_info")
    
    if "description" in config_data:
        current_business.description = config_data["description"]
        updated_fields.append("description")
    
    # Commit changes
    db.commit()
    db.refresh(current_business)
    
    return {
        "status": "success",
        "message": f"Successfully updated {', '.join(updated_fields) if updated_fields else 'no'} fields",
        "updated_fields": updated_fields,
        "business": {
            "id": current_business.id,
            "name": current_business.name,
            "updated_at": current_business.updated_at
        }
    }


@router.get("/overview")
async def get_dashboard_overview(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
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
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
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
    except Exception:
        manager.disconnect(f"dashboard_{session_id}")


@router.get("/orders/live")
async def get_live_orders(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
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
