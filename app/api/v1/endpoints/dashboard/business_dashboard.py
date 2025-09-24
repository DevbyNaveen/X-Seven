"""Business dashboard endpoints for AI integration."""
from typing import Any, Dict, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket

from app.config.database import get_supabase_client
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, Order, Message, User
from app.models.order import OrderStatus
from app.services.websocket.connection_manager import manager
from app.core.supabase_auth import refresh_jwks_cache
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/{business_id}", response_model=dict)
async def get_business_details(
    business_id: int,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
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
async def get_dashboard_overview(
    business_id: int,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
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
    today_start = datetime.combine(today, datetime.min.time()).isoformat()
    today_end = datetime.combine(today, datetime.max.time()).isoformat()

    # Today's orders using Supabase
    orders_response = supabase.table('orders').select('*').eq('business_id', business_id).gte('created_at', today_start).lte('created_at', today_end).execute()
    today_orders = orders_response.data if orders_response.data else []

    # Calculate statistics
    total_orders = len(today_orders)
    total_revenue = sum(order.get('total_amount', 0) for order in today_orders)
    pending_orders = len([o for o in today_orders if o.get('status') == OrderStatus.PENDING])
    completed_orders = len([o for o in today_orders if o.get('status') == OrderStatus.DELIVERED])

    # Active conversations using Supabase
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    messages_response = supabase.table('messages').select('session_id').eq('business_id', business_id).gte('created_at', one_hour_ago).execute()
    active_sessions = set()
    if messages_response.data:
        active_sessions = {msg['session_id'] for msg in messages_response.data}
    active_conversations = len(active_sessions)

    # Recent orders (last 7 days) using Supabase
    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    recent_orders_response = supabase.table('orders').select('*').eq('business_id', business_id).gte('created_at', seven_days_ago).order('created_at', desc=True).limit(10).execute()
    recent_orders = recent_orders_response.data if recent_orders_response.data else []

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
                "id": order.get("id"),
                "table_id": order.get("table_id"),
                "total_amount": order.get("total_amount"),
                "status": order.get("status"),
                "created_at": order.get("created_at")
            }
            for order in recent_orders
        ]
    }


@router.get("/{business_id}/stats", response_model=dict)
async def get_business_stats(
    business_id: int,
    period: str = "7d",  # 1d, 7d, 30d
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get comprehensive business statistics using analytics service."""

    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business"
        )

    # Use the comprehensive analytics service
    analytics_service = AnalyticsService()
    return await analytics_service.get_orders_analytics(
        business_id=business_id,
        period=period
    )


@router.put("/{business_id}/config", response_model=dict)
async def update_business_config(
    business_id: int,
    config_data: Dict[str, Any],
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
) -> Any:
    """Update business configuration."""
    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this business"
        )

    # Update business configuration using Supabase
    updated_fields = []
    update_data = {}

    if "settings" in config_data:
        update_data["settings"] = config_data["settings"]
        updated_fields.append("settings")

    if "branding_config" in config_data:
        update_data["branding_config"] = config_data["branding_config"]
        updated_fields.append("branding_config")

    if "contact_info" in config_data:
        update_data["contact_info"] = config_data["contact_info"]
        updated_fields.append("contact_info")

    if "description" in config_data:
        update_data["description"] = config_data["description"]
        updated_fields.append("description")

    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow().isoformat()

    if update_data:
        # Update using Supabase
        update_response = supabase.table('businesses').update(update_data).eq('id', business_id).execute()

        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update business configuration"
            )

    return {
        "status": "success",
        "message": f"Successfully updated {', '.join(updated_fields) if updated_fields else 'no'} fields",
        "updated_fields": updated_fields,
        "business": {
            "id": current_business.id,
            "name": current_business.name,
            "updated_at": update_data.get("updated_at")
        }
    }


@router.get("/overview")
async def get_dashboard_overview(
    supabase = Depends(get_supabase_client),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get dashboard overview statistics."""
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time()).isoformat()
    today_end = datetime.combine(today, datetime.max.time()).isoformat()

    # Today's orders using Supabase
    orders_response = supabase.table('orders').select('*').eq('business_id', business.id).gte('created_at', today_start).lte('created_at', today_end).execute()
    today_orders = orders_response.data if orders_response.data else []

    # Calculate statistics
    total_orders = len(today_orders)
    total_revenue = sum(order.get('total_amount', 0) for order in today_orders)
    pending_orders = len([o for o in today_orders if o.get('status') == OrderStatus.PENDING])
    completed_orders = len([o for o in today_orders if o.get('status') == OrderStatus.DELIVERED])

    # Active conversations using Supabase
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    messages_response = supabase.table('messages').select('session_id').eq('business_id', business.id).gte('created_at', one_hour_ago).execute()
    active_sessions = set()
    if messages_response.data:
        active_sessions = {msg['session_id'] for msg in messages_response.data}
    active_conversations = len(active_sessions)

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
    supabase = Depends(get_supabase_client),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get active customer conversations."""

    # Get recent messages grouped by session using Supabase
    # We'll get all messages for the business and group them by session_id
    messages_response = supabase.table('messages').select('*').eq('business_id', business.id).order('created_at', desc=True).limit(limit * 2).execute()
    messages = messages_response.data if messages_response.data else []

    # Group messages by session_id and get the latest message for each session
    sessions = {}
    for message in messages:
        session_id = message.get('session_id')
        if session_id not in sessions:
            sessions[session_id] = message
        elif message.get('created_at', '') > sessions[session_id].get('created_at', ''):
            sessions[session_id] = message

    # Limit to the requested number
    conversations = list(sessions.values())[:limit]

    result = []
    for conv in conversations:
        session_id = conv.get('session_id')

        # Get message count for this session using Supabase
        count_response = supabase.table('messages').select('*', count='exact').eq('session_id', session_id).execute()
        message_count = count_response.count if hasattr(count_response, 'count') else len(count_response.data or [])

        # Calculate time difference
        created_at = conv.get('created_at')
        if created_at:
            # Parse ISO datetime string
            from datetime import datetime
            try:
                msg_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_diff = datetime.utcnow().replace(tzinfo=msg_time.tzinfo) - msg_time
                is_active = time_diff.seconds < 3600
            except:
                is_active = False
        else:
            is_active = False

        result.append({
            "session_id": session_id,
            "last_message": conv.get('content', ''),
            "last_message_time": created_at,
            "message_count": message_count,
            "status": "active" if is_active else "idle"
        })

    return result


@router.post("/takeover/{session_id}")
async def takeover_conversation(
    session_id: str,
    supabase = Depends(get_supabase_client),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Take over a conversation from the bot."""

    # Verify session belongs to business using Supabase
    messages_response = supabase.table('messages').select('*').eq('session_id', session_id).eq('business_id', business.id).limit(1).execute()

    if not messages_response.data:
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
    supabase = Depends(get_supabase_client)
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
    supabase = Depends(get_supabase_client),
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

    # Query orders using Supabase with status filter
    orders_response = supabase.table('orders').select('*').eq('business_id', business.id).in_('status', active_statuses).order('created_at', desc=True).execute()
    orders = orders_response.data if orders_response.data else []

    return [
        {
            "id": order.get("id"),
            "table_id": order.get("table_id"),
            "items": order.get("items", []),
            "total": order.get("total_amount", 0),
            "status": order.get("status"),
            "created_at": order.get("created_at"),
            "estimated_ready": order.get("estimated_ready_time"),
            "special_instructions": order.get("special_instructions")
        }
        for order in orders
    ]


@router.post("/test-refresh-jwks")
async def test_refresh_jwks():
    """Test endpoint to manually refresh JWKS cache."""
    success = refresh_jwks_cache()
    return {"success": success, "message": "JWKS cache refreshed" if success else "Failed to refresh JWKS cache"}


# Enhanced Analytics Endpoints using Analytics Service
@router.get("/{business_id}/analytics/overview", response_model=dict)
async def get_analytics_overview(
    business_id: int,
    period: str = "7d",
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get comprehensive analytics overview using analytics service."""

    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business analytics"
        )

    analytics_service = AnalyticsService()
    return await analytics_service.get_combined_analytics(
        business_id=business_id,
        period=period
    )


@router.get("/{business_id}/analytics/realtime", response_model=dict)
async def get_realtime_analytics(
    business_id: int,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get real-time analytics for the last hour."""

    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business analytics"
        )

    analytics_service = AnalyticsService()

    # Get last hour analytics
    orders_analytics = await analytics_service.get_orders_analytics(business_id, "1d")
    messages_analytics = await analytics_service.get_messages_analytics(business_id, "1d")

    # Calculate real-time metrics
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)

    # Filter for last hour only
    recent_orders = [
        order for order in orders_analytics["orders"]
        if order.get('created_at') and
        datetime.fromisoformat(order['created_at'].replace('Z', '+00:00')) > one_hour_ago
    ]

    recent_messages = [
        msg for msg in messages_analytics["messages"]
        if msg.get('created_at') and
        datetime.fromisoformat(msg['created_at'].replace('Z', '+00:00')) > one_hour_ago
    ]

    return {
        "business_id": business_id,
        "time_window": "last_hour",
        "generated_at": now.isoformat(),
        "orders": {
            "count": len(recent_orders),
            "revenue": sum(order.get('total_amount', 0) for order in recent_orders),
            "orders": recent_orders[:10]  # Last 10 orders
        },
        "messages": {
            "count": len(recent_messages),
            "active_sessions": len(set(msg.get('session_id') for msg in recent_messages if msg.get('session_id'))),
            "messages": recent_messages[:20]  # Last 20 messages
        },
        "performance": {
            "orders_per_hour": len(recent_orders),
            "messages_per_hour": len(recent_messages),
            "revenue_per_hour": sum(order.get('total_amount', 0) for order in recent_orders)
        }
    }


@router.get("/{business_id}/analytics/performance", response_model=dict)
async def get_performance_analytics(
    business_id: int,
    period: str = "30d",
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get performance analytics with trends and KPIs."""

    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business analytics"
        )

    analytics_service = AnalyticsService()

    # Get analytics for different periods for comparison
    current_period = await analytics_service.get_combined_analytics(business_id, period)

    # Calculate previous period for comparison
    if period == "7d":
        prev_period = "30d"  # Compare with month
    elif period == "30d":
        prev_period = "90d"  # Compare with quarter
    else:
        prev_period = "7d"   # Default comparison

    previous_period = await analytics_service.get_combined_analytics(business_id, prev_period)

    # Calculate growth rates
    def calculate_growth(current, previous):
        if previous == 0:
            return 0 if current == 0 else 100
        return ((current - previous) / previous) * 100

    return {
        "business_id": business_id,
        "analysis_period": period,
        "comparison_period": prev_period,
        "generated_at": datetime.utcnow().isoformat(),
        "kpis": {
            "orders": {
                "current": current_period["summary"]["total_orders"],
                "previous": previous_period["summary"]["total_orders"],
                "growth_rate": calculate_growth(
                    current_period["summary"]["total_orders"],
                    previous_period["summary"]["total_orders"]
                )
            },
            "revenue": {
                "current": current_period["summary"]["total_revenue"],
                "previous": previous_period["summary"]["total_revenue"],
                "growth_rate": calculate_growth(
                    current_period["summary"]["total_revenue"],
                    previous_period["summary"]["total_revenue"]
                )
            },
            "messages": {
                "current": current_period["summary"]["total_messages"],
                "previous": previous_period["summary"]["total_messages"],
                "growth_rate": calculate_growth(
                    current_period["summary"]["total_messages"],
                    previous_period["summary"]["total_messages"]
                )
            },
            "average_order_value": {
                "current": current_period["summary"]["average_order_value"],
                "previous": previous_period["summary"]["average_order_value"],
                "growth_rate": calculate_growth(
                    current_period["summary"]["average_order_value"],
                    previous_period["summary"]["average_order_value"]
                )
            }
        },
        "trends": {
            "orders_over_time": current_period["orders"]["daily_trends"],
            "messages_over_time": current_period["messages"]["daily_trends"]
        },
        "status_distribution": current_period["orders"]["status_distribution"]
    }


@router.post("/{business_id}/analytics/order", response_model=dict)
async def create_order_via_analytics(
    business_id: int,
    order_data: Dict[str, Any],
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create a new order record via analytics service."""

    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create orders for this business"
        )

    analytics_service = AnalyticsService()
    return await analytics_service.create_order_analytics_record(
        business_id=business_id,
        order_data=order_data
    )


@router.post("/{business_id}/analytics/message", response_model=dict)
async def create_message_via_analytics(
    business_id: int,
    message_data: Dict[str, Any],
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create a new message record via analytics service."""

    # Verify business access
    if current_business.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create messages for this business"
        )

    analytics_service = AnalyticsService()
    return await analytics_service.create_message_analytics_record(
        business_id=business_id,
        message_data=message_data
    )
