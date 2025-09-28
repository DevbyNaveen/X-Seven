"""Analytics Endpoints for Dashboard Operations."""
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.config.database import get_supabase_client
from app.core.dependencies import get_current_business, get_current_user
from app.services.analytics_service import AnalyticsService
from app.models import Business, User

router = APIRouter(tags=["Analytics"])


@router.get("/orders/{business_id}", response_model=Dict[str, Any])
async def get_orders_analytics(
    business_id: str,
    period: str = Query("7d", description="Time period: 1d, 7d, 30d"),
    status_filter: Optional[str] = Query(None, description="Filter by order status"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get comprehensive orders analytics with filtering options."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business analytics"
        )

    analytics_service = AnalyticsService()
    return await analytics_service.get_orders_analytics(
        business_id=business_id,
        period=period,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/messages/{business_id}", response_model=Dict[str, Any])
async def get_messages_analytics(
    business_id: str,
    period: str = Query("7d", description="Time period: 1d, 7d, 30d"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get comprehensive messages analytics with filtering options."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business analytics"
        )

    analytics_service = AnalyticsService()
    return await analytics_service.get_messages_analytics(
        business_id=business_id,
        period=period,
        session_id=session_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/combined/{business_id}", response_model=Dict[str, Any])
async def get_combined_analytics(
    business_id: str,
    period: str = Query("7d", description="Time period: 1d, 7d, 30d"),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get combined analytics from both orders and messages."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business analytics"
        )

    analytics_service = AnalyticsService()
    return await analytics_service.get_combined_analytics(
        business_id=business_id,
        period=period
    )


@router.post("/orders/{business_id}", response_model=Dict[str, Any])
async def create_order_record(
    business_id: str,
    order_data: Dict[str, Any],
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create a new order record for analytics tracking."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create orders for this business"
        )

    analytics_service = AnalyticsService()
    return await analytics_service.create_order_analytics_record(
        business_id=business_id,
        order_data=order_data
    )


@router.put("/orders/{business_id}/{order_id}/status", response_model=Dict[str, Any])
async def update_order_status(
    business_id: str,
    order_id: str,
    status_update: Dict[str, Any],
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update order status for analytics tracking."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update orders for this business"
        )

    if "status" not in status_update:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status field is required"
        )

    analytics_service = AnalyticsService()
    return await analytics_service.update_order_status(
        business_id=business_id,
        order_id=order_id,
        new_status=status_update["status"],
        additional_data=status_update.get("additional_data")
    )


@router.post("/messages/{business_id}", response_model=Dict[str, Any])
async def create_message_record(
    business_id: str,
    message_data: Dict[str, Any],
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create a new message record for analytics tracking."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create messages for this business"
        )

    # Validate required fields
    required_fields = ["session_id", "content"]
    for field in required_fields:
        if field not in message_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} field is required"
            )

    analytics_service = AnalyticsService()
    return await analytics_service.create_message_analytics_record(
        business_id=business_id,
        message_data=message_data
    )


@router.get("/dashboard/{business_id}/summary", response_model=Dict[str, Any])
async def get_dashboard_summary(
    business_id: str,
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get dashboard summary with key metrics for quick overview."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this business analytics"
        )

    analytics_service = AnalyticsService()

    # Get today's analytics
    today_analytics = await analytics_service.get_combined_analytics(business_id, "1d")

    # Get this week's analytics
    week_analytics = await analytics_service.get_combined_analytics(business_id, "7d")

    # Get this month's analytics
    month_analytics = await analytics_service.get_combined_analytics(business_id, "30d")

    return {
        "business_id": business_id,
        "generated_at": datetime.utcnow().isoformat(),
        "today": {
            "orders": today_analytics["summary"]["total_orders"],
            "revenue": today_analytics["summary"]["total_revenue"],
            "messages": today_analytics["summary"]["total_messages"],
            "sessions": today_analytics["summary"]["total_sessions"]
        },
        "this_week": {
            "orders": week_analytics["summary"]["total_orders"],
            "revenue": week_analytics["summary"]["total_revenue"],
            "messages": week_analytics["summary"]["total_messages"],
            "sessions": week_analytics["summary"]["total_sessions"]
        },
        "this_month": {
            "orders": month_analytics["summary"]["total_orders"],
            "revenue": month_analytics["summary"]["total_revenue"],
            "messages": month_analytics["summary"]["total_messages"],
            "sessions": month_analytics["summary"]["total_sessions"]
        },
        "averages": {
            "order_value_today": today_analytics["summary"]["average_order_value"],
            "messages_per_session_today": today_analytics["summary"]["average_messages_per_session"],
            "order_value_week": week_analytics["summary"]["average_order_value"],
            "messages_per_session_week": week_analytics["summary"]["average_messages_per_session"]
        }
    }


@router.get("/orders/{business_id}/export", response_model=Dict[str, Any])
async def export_orders_data(
    business_id: str,
    period: str = Query("30d", description="Time period to export"),
    format: str = Query("json", description="Export format: json, csv"),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Export orders data for external analysis."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to export data for this business"
        )

    analytics_service = AnalyticsService()
    orders_analytics = await analytics_service.get_orders_analytics(business_id, period)

    return {
        "export_info": {
            "business_id": business_id,
            "period": period,
            "format": format,
            "total_records": len(orders_analytics["orders"]),
            "generated_at": datetime.utcnow().isoformat()
        },
        "data": orders_analytics["orders"]
    }


@router.get("/messages/{business_id}/export", response_model=Dict[str, Any])
async def export_messages_data(
    business_id: str,
    period: str = Query("30d", description="Time period to export"),
    format: str = Query("json", description="Export format: json, csv"),
    current_business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Export messages data for external analysis."""

    # Verify business access
    if str(current_business.id) != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to export data for this business"
        )

    analytics_service = AnalyticsService()
    messages_analytics = await analytics_service.get_messages_analytics(business_id, period)

    return {
        "export_info": {
            "business_id": business_id,
            "period": period,
            "format": format,
            "total_records": len(messages_analytics["messages"]),
            "generated_at": datetime.utcnow().isoformat()
        },
        "data": messages_analytics["messages"]
    }
