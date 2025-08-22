"""Booking system endpoints."""
from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.config.database import get_db
from app.core.dependencies import get_current_business, get_current_user
from app.models import Business, User, Table, Order
from app.services.ai.booking_system import BookingSystem
from app.schemas.bookings import (
    BookingCreate,
    BookingResponse,
    BookingStatus,
    BookingHistory,
    BookingAnalytics,
    BookingSettings,
    TableAvailability
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/create", response_model=BookingResponse)
async def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Create a new table booking.
    """
    booking_system = BookingSystem(db)
    
    try:
        # Validate booking data
        if booking_data.party_size <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Party size must be greater than 0"
            )
        
        if booking_data.booking_time < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking time cannot be in the past"
            )
        
        # Check table availability
        available_tables = await booking_system.check_availability(
            business_id=business.id,
            party_size=booking_data.party_size,
            booking_time=booking_data.booking_time,
            duration=booking_data.duration
        )
        
        if not available_tables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No tables available for the requested time and party size"
            )
        
        # Create booking
        booking = await booking_system.create_booking(
            business_id=business.id,
            customer_name=booking_data.customer_name,
            customer_phone=booking_data.customer_phone,
            customer_email=booking_data.customer_email,
            party_size=booking_data.party_size,
            booking_time=booking_data.booking_time,
            duration=booking_data.duration,
            table_id=available_tables[0].id,  # Assign first available table
            special_requests=booking_data.special_requests,
            source=booking_data.source
        )
        
        return BookingResponse(
            id=booking.id,
            customer_name=booking.customer_name,
            customer_phone=booking.customer_phone,
            customer_email=booking.customer_email,
            party_size=booking.party_size,
            booking_time=booking.booking_time,
            duration=booking.duration,
            table_id=booking.table_id,
            status=BookingStatus.CONFIRMED,
            special_requests=booking.special_requests,
            source=booking.source,
            created_at=booking.created_at,
            business_id=business.id
        )
        
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating booking: {str(e)}"
        )


@router.get("/availability", response_model=List[TableAvailability])
async def check_availability(
    date: datetime,
    party_size: int = Query(..., ge=1, le=20),
    duration: int = Query(120, ge=30, le=480),  # minutes
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Check table availability for a specific date and party size.
    """
    booking_system = BookingSystem(db)
    
    try:
        # Get available time slots for the day
        availability = await booking_system.get_daily_availability(
            business_id=business.id,
            date=date.date(),
            party_size=party_size,
            duration=duration
        )
        
        return availability
        
    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking availability: {str(e)}"
        )


@router.get("/", response_model=List[BookingResponse])
async def get_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[BookingStatus] = None,
    date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get all bookings for the business with filtering.
    """
    booking_system = BookingSystem(db)
    
    try:
        bookings = await booking_system.get_bookings(
            business_id=business.id,
            status=status.value if status else None,
            date=date,
            skip=skip,
            limit=limit
        )
        
        return [
            BookingResponse(
                id=booking.id,
                customer_name=booking.customer_name,
                customer_phone=booking.customer_phone,
                customer_email=booking.customer_email,
                party_size=booking.party_size,
                booking_time=booking.booking_time,
                duration=booking.duration,
                table_id=booking.table_id,
                status=BookingStatus(booking.status),
                special_requests=booking.special_requests,
                source=booking.source,
                created_at=booking.created_at,
                business_id=business.id
            )
            for booking in bookings
        ]
        
    except Exception as e:
        logger.error(f"Error getting bookings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting bookings: {str(e)}"
        )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get detailed information about a specific booking.
    """
    booking_system = BookingSystem(db)
    
    try:
        booking = await booking_system.get_booking(booking_id, business.id)
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        return BookingResponse(
            id=booking.id,
            customer_name=booking.customer_name,
            customer_phone=booking.customer_phone,
            customer_email=booking.customer_email,
            party_size=booking.party_size,
            booking_time=booking.booking_time,
            duration=booking.duration,
            table_id=booking.table_id,
            status=BookingStatus(booking.status),
            special_requests=booking.special_requests,
            source=booking.source,
            created_at=booking.created_at,
            business_id=business.id
        )
        
    except Exception as e:
        logger.error(f"Error getting booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting booking: {str(e)}"
        )


@router.put("/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    status: BookingStatus,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update booking status.
    """
    booking_system = BookingSystem(db)
    
    try:
        result = await booking_system.update_booking_status(
            booking_id=booking_id,
            business_id=business.id,
            status=status.value
        )
        
        return {
            "success": True,
            "message": f"Booking status updated to {status.value}",
            "booking_id": booking_id,
            "new_status": status.value
        }
        
    except Exception as e:
        logger.error(f"Error updating booking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating booking status: {str(e)}"
        )


@router.delete("/{booking_id}")
async def cancel_booking(
    booking_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Cancel a booking.
    """
    booking_system = BookingSystem(db)
    
    try:
        result = await booking_system.cancel_booking(
            booking_id=booking_id,
            business_id=business.id,
            reason=reason
        )
        
        return {
            "success": True,
            "message": "Booking cancelled successfully",
            "booking_id": booking_id
        }
        
    except Exception as e:
        logger.error(f"Error cancelling booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling booking: {str(e)}"
        )


@router.get("/analytics", response_model=BookingAnalytics)
async def get_booking_analytics(
    time_range: str = Query("30d", regex="^(7d|30d|90d|1y)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get booking analytics and insights.
    """
    # Calculate date range
    end_date = datetime.utcnow()
    if time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    elif time_range == "90d":
        start_date = end_date - timedelta(days=90)
    else:  # 1y
        start_date = end_date - timedelta(days=365)
    
    booking_system = BookingSystem(db)
    
    try:
        analytics = await booking_system.get_analytics(
            business_id=business.id,
            start_date=start_date,
            end_date=end_date
        )
        
        return BookingAnalytics(
            time_range=time_range,
            total_bookings=analytics.get("total_bookings", 0),
            confirmed_bookings=analytics.get("confirmed_bookings", 0),
            cancelled_bookings=analytics.get("cancelled_bookings", 0),
            no_shows=analytics.get("no_shows", 0),
            average_party_size=analytics.get("average_party_size", 0),
            peak_hours=analytics.get("peak_hours", []),
            popular_tables=analytics.get("popular_tables", []),
            booking_sources=analytics.get("booking_sources", {}),
            conversion_rate=analytics.get("conversion_rate", 0.0)
        )
        
    except Exception as e:
        logger.error(f"Error getting booking analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting booking analytics: {str(e)}"
        )


@router.get("/settings", response_model=BookingSettings)
async def get_booking_settings(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get booking settings for the business.
    """
    settings = business.settings.get("booking", {})
    
    return BookingSettings(
        booking_enabled=settings.get("booking_enabled", True),
        advance_booking_days=settings.get("advance_booking_days", 30),
        max_party_size=settings.get("max_party_size", 20),
        min_party_size=settings.get("min_party_size", 1),
        booking_duration=settings.get("booking_duration", 120),  # minutes
        auto_confirm=settings.get("auto_confirm", True),
        require_confirmation=settings.get("require_confirmation", False),
        cancellation_policy=settings.get("cancellation_policy", "24h"),
        deposit_required=settings.get("deposit_required", False),
        deposit_amount=settings.get("deposit_amount", 0.0),
        business_hours_start=settings.get("business_hours_start", "09:00"),
        business_hours_end=settings.get("business_hours_end", "22:00"),
        timezone=settings.get("timezone", "UTC")
    )


@router.put("/settings", response_model=BookingSettings)
async def update_booking_settings(
    settings: BookingSettings,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Update booking settings for the business.
    """
    if not business.settings:
        business.settings = {}
    
    business.settings["booking"] = settings.dict()
    db.commit()
    
    return settings


@router.post("/bulk-import")
async def bulk_import_bookings(
    bookings: List[BookingCreate],
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Bulk import bookings from external systems.
    """
    booking_system = BookingSystem(db)
    
    try:
        results = []
        for booking_data in bookings:
            try:
                booking = await booking_system.create_booking(
                    business_id=business.id,
                    customer_name=booking_data.customer_name,
                    customer_phone=booking_data.customer_phone,
                    customer_email=booking_data.customer_email,
                    party_size=booking_data.party_size,
                    booking_time=booking_data.booking_time,
                    duration=booking_data.duration,
                    table_id=None,  # Will be assigned automatically
                    special_requests=booking_data.special_requests,
                    source=booking_data.source
                )
                results.append({
                    "status": "success",
                    "booking_id": booking.id,
                    "customer_name": booking.customer_name
                })
            except Exception as e:
                results.append({
                    "status": "failed",
                    "customer_name": booking_data.customer_name,
                    "error": str(e)
                })
        
        return {
            "total_bookings": len(bookings),
            "successful": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error bulk importing bookings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error bulk importing bookings: {str(e)}"
        )


@router.get("/calendar/{date}")
async def get_calendar_view(
    date: datetime,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get calendar view of bookings for a specific date.
    """
    booking_system = BookingSystem(db)
    
    try:
        calendar_data = await booking_system.get_calendar_view(
            business_id=business.id,
            date=date.date()
        )
        
        return {
            "date": date.date().isoformat(),
            "total_bookings": len(calendar_data),
            "bookings": calendar_data,
            "time_slots": [
                "09:00", "10:00", "11:00", "12:00", "13:00", "14:00",
                "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting calendar view: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting calendar view: {str(e)}"
        )


@router.post("/{booking_id}/reminder")
async def send_booking_reminder(
    booking_id: int,
    reminder_type: str = Query("24h", regex="^(1h|24h|1d)$"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Send booking reminder to customer.
    """
    booking_system = BookingSystem(db)
    
    try:
        result = await booking_system.send_reminder(
            booking_id=booking_id,
            business_id=business.id,
            reminder_type=reminder_type
        )
        
        return {
            "success": True,
            "message": f"Booking reminder sent ({reminder_type})",
            "booking_id": booking_id,
            "reminder_type": reminder_type
        }
        
    except Exception as e:
        logger.error(f"Error sending booking reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending booking reminder: {str(e)}"
        )


@router.get("/waitlist")
async def get_waitlist(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Get current waitlist for the business.
    """
    booking_system = BookingSystem(db)
    
    try:
        waitlist = await booking_system.get_waitlist(business.id)
        
        return {
            "total_waiting": len(waitlist),
            "waitlist": waitlist
        }
        
    except Exception as e:
        logger.error(f"Error getting waitlist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting waitlist: {str(e)}"
        )


@router.post("/waitlist/add")
async def add_to_waitlist(
    customer_name: str,
    customer_phone: str,
    party_size: int,
    estimated_wait: Optional[int] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
) -> Any:
    """
    Add customer to waitlist.
    """
    booking_system = BookingSystem(db)
    
    try:
        waitlist_entry = await booking_system.add_to_waitlist(
            business_id=business.id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            party_size=party_size,
            estimated_wait=estimated_wait
        )
        
        return {
            "success": True,
            "message": "Added to waitlist successfully",
            "position": waitlist_entry.position,
            "estimated_wait": waitlist_entry.estimated_wait
        }
        
    except Exception as e:
        logger.error(f"Error adding to waitlist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding to waitlist: {str(e)}"
        )
