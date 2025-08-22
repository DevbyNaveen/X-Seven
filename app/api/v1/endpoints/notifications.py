"""Real-time notification system endpoints."""
from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User, Order, Message
from app.models.order import OrderStatus
from app.services.websocket.connection_manager import manager
from app.services.notifications.notification_service import NotificationService
from app.schemas.notifications import (
    NotificationCreate,
    NotificationResponse,
    NotificationSettings,
    NotificationTemplate,
    NotificationHistory
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/{business_id}")
async def notification_websocket(
    websocket: WebSocket,
    business_id: int,
    user_id: Optional[int] = None
):
    """
    WebSocket endpoint for real-time notifications.
    """
    await manager.connect(websocket, f"notifications_{business_id}_{user_id or 'anonymous'}")
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to notification system",
            "business_id": business_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(f"notifications_{business_id}_{user_id or 'anonymous'}")


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    notification: NotificationCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Send a notification to customers or staff.
    """
    notification_service = NotificationService(db)
    
    try:
        result = await notification_service.send_notification(
            business_id=business.id,
            notification_type=notification.type,
            recipients=notification.recipients,
            message=notification.message,
            channels=notification.channels,
            metadata=notification.metadata
        )
        
        return NotificationResponse(
            id=result["id"],
            type=notification.type,
            message=notification.message,
            channels=notification.channels,
            status="sent",
            sent_at=datetime.utcnow(),
            recipients_count=len(notification.recipients)
        )
        
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending notification: {str(e)}"
        )


@router.get("/history", response_model=List[NotificationHistory])
async def get_notification_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    notification_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get notification history for the business.
    """
    # This would query a notifications table in a real implementation
    # For now, return mock data
    notifications = [
        {
            "id": 1,
            "type": "order_confirmation",
            "message": "Order #1234 confirmed",
            "channels": ["email", "sms"],
            "status": "sent",
            "sent_at": datetime.utcnow() - timedelta(hours=2),
            "recipients_count": 1,
            "delivery_status": {
                "email": "delivered",
                "sms": "delivered"
            }
        },
        {
            "id": 2,
            "type": "order_ready",
            "message": "Order #1234 is ready for pickup",
            "channels": ["sms", "whatsapp"],
            "status": "sent",
            "sent_at": datetime.utcnow() - timedelta(hours=1),
            "recipients_count": 1,
            "delivery_status": {
                "sms": "delivered",
                "whatsapp": "read"
            }
        }
    ]
    
    # Filter by type and status if provided
    if notification_type:
        notifications = [n for n in notifications if n["type"] == notification_type]
    if status:
        notifications = [n for n in notifications if n["status"] == status]
    
    return notifications[skip:skip + limit]


@router.get("/settings", response_model=NotificationSettings)
async def get_notification_settings(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get notification settings for the business.
    """
    # Get settings from business model
    settings = business.settings.get("notifications", {})
    
    return NotificationSettings(
        order_notifications=settings.get("order_notifications", True),
        payment_notifications=settings.get("payment_notifications", True),
        system_notifications=settings.get("system_notifications", True),
        marketing_notifications=settings.get("marketing_notifications", False),
        email_enabled=settings.get("email_enabled", True),
        sms_enabled=settings.get("sms_enabled", True),
        whatsapp_enabled=settings.get("whatsapp_enabled", False),
        push_enabled=settings.get("push_enabled", True),
        quiet_hours_start=settings.get("quiet_hours_start", "22:00"),
        quiet_hours_end=settings.get("quiet_hours_end", "08:00"),
        timezone=settings.get("timezone", "UTC")
    )


@router.put("/settings", response_model=NotificationSettings)
async def update_notification_settings(
    settings: NotificationSettings,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update notification settings for the business.
    """
    # Update settings in business model
    if not business.settings:
        business.settings = {}
    
    business.settings["notifications"] = settings.dict()
    db.commit()
    
    return settings


@router.get("/templates", response_model=List[NotificationTemplate])
async def get_notification_templates(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get available notification templates.
    """
    templates = [
        NotificationTemplate(
            id="order_confirmation",
            name="Order Confirmation",
            description="Sent when an order is confirmed",
            subject="Order Confirmed - {business_name}",
            body="Hi {customer_name}, your order #{order_number} has been confirmed and is being prepared. Total: ${total_amount}",
            variables=["customer_name", "order_number", "total_amount", "business_name"],
            channels=["email", "sms"]
        ),
        NotificationTemplate(
            id="order_ready",
            name="Order Ready",
            description="Sent when an order is ready for pickup",
            subject="Order Ready - {business_name}",
            body="Hi {customer_name}, your order #{order_number} is ready for pickup!",
            variables=["customer_name", "order_number", "business_name"],
            channels=["sms", "whatsapp"]
        ),
        NotificationTemplate(
            id="payment_success",
            name="Payment Success",
            description="Sent when payment is successful",
            subject="Payment Confirmed - {business_name}",
            body="Thank you! Your payment of ${amount} has been confirmed.",
            variables=["amount", "business_name"],
            channels=["email", "sms"]
        ),
        NotificationTemplate(
            id="booking_confirmation",
            name="Booking Confirmation",
            description="Sent when a table booking is confirmed",
            subject="Booking Confirmed - {business_name}",
            body="Hi {customer_name}, your booking for {date} at {time} has been confirmed.",
            variables=["customer_name", "date", "time", "business_name"],
            channels=["email", "sms"]
        )
    ]
    
    return templates


@router.post("/test")
async def send_test_notification(
    channel: str = Query(..., regex="^(email|sms|whatsapp|push)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Send a test notification to verify settings.
    """
    notification_service = NotificationService(db)
    
    try:
        result = await notification_service.send_test_notification(
            business_id=business.id,
            channel=channel
        )
        
        return {
            "success": True,
            "message": f"Test notification sent via {channel}",
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending test notification: {str(e)}"
        )


@router.post("/broadcast")
async def broadcast_notification(
    message: str,
    channels: List[str] = ["email", "sms"],
    customer_segment: Optional[str] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Broadcast notification to all customers or a segment.
    """
    notification_service = NotificationService(db)
    
    try:
        result = await notification_service.broadcast_notification(
            business_id=business.id,
            message=message,
            channels=channels,
            customer_segment=customer_segment
        )
        
        return {
            "success": True,
            "message": "Broadcast notification sent",
            "recipients_count": result.get("recipients_count", 0),
            "channels": channels
        }
        
    except Exception as e:
        logger.error(f"Error broadcasting notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error broadcasting notification: {str(e)}"
        )


@router.get("/stats")
async def get_notification_stats(
    time_range: str = Query("7d", regex="^(1d|7d|30d|90d)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get notification statistics.
    """
    # Calculate date range
    end_date = datetime.utcnow()
    if time_range == "1d":
        start_date = end_date - timedelta(days=1)
    elif time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    else:  # 90d
        start_date = end_date - timedelta(days=90)
    
    # Mock statistics - in real implementation, query notification logs
    stats = {
        "total_notifications": 150,
        "delivered": 142,
        "failed": 8,
        "delivery_rate": 94.7,
        "by_channel": {
            "email": {"sent": 80, "delivered": 76, "failed": 4},
            "sms": {"sent": 50, "delivered": 48, "failed": 2},
            "whatsapp": {"sent": 20, "delivered": 18, "failed": 2}
        },
        "by_type": {
            "order_confirmation": 60,
            "order_ready": 40,
            "payment_success": 30,
            "system": 20
        },
        "time_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }
    
    return stats


@router.post("/schedule")
async def schedule_notification(
    notification: NotificationCreate,
    scheduled_at: datetime,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Schedule a notification for later delivery.
    """
    notification_service = NotificationService(db)
    
    try:
        result = await notification_service.schedule_notification(
            business_id=business.id,
            notification=notification,
            scheduled_at=scheduled_at
        )
        
        return {
            "success": True,
            "message": "Notification scheduled successfully",
            "scheduled_at": scheduled_at.isoformat(),
            "job_id": result.get("job_id")
        }
        
    except Exception as e:
        logger.error(f"Error scheduling notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scheduling notification: {str(e)}"
        )


@router.delete("/cancel/{job_id}")
async def cancel_scheduled_notification(
    job_id: str,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Cancel a scheduled notification.
    """
    notification_service = NotificationService(db)
    
    try:
        result = await notification_service.cancel_scheduled_notification(job_id)
        
        return {
            "success": True,
            "message": "Scheduled notification cancelled",
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error(f"Error cancelling scheduled notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling scheduled notification: {str(e)}"
        )


@router.get("/unread")
async def get_unread_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get unread notifications for the current user.
    """
    # Mock unread notifications - in real implementation, query user notifications
    unread_notifications = [
        {
            "id": 1,
            "type": "order_update",
            "title": "Order Status Update",
            "message": "Order #1234 is now being prepared",
            "created_at": datetime.utcnow() - timedelta(minutes=5),
            "read": False
        },
        {
            "id": 2,
            "type": "system",
            "title": "System Maintenance",
            "message": "Scheduled maintenance in 2 hours",
            "created_at": datetime.utcnow() - timedelta(hours=1),
            "read": False
        }
    ]
    
    return {
        "unread_count": len(unread_notifications),
        "notifications": unread_notifications
    }


@router.post("/mark-read/{notification_id}")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Mark a notification as read.
    """
    # In real implementation, update notification read status
    return {
        "success": True,
        "message": "Notification marked as read",
        "notification_id": notification_id
    }


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Mark all notifications as read.
    """
    # In real implementation, update all user notifications
    return {
        "success": True,
        "message": "All notifications marked as read"
    }
