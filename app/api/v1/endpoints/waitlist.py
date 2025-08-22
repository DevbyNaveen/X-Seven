"""Waitlist management endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_business
from app.models import Business, WaitlistEntry
from app.schemas.waitlist import (
    WaitlistEntryCreate,
    WaitlistEntryUpdate,
    WaitlistEntryResponse,
    WaitlistSummary
)
from app.services.ai.booking_system import BookingSystem
from app.services.notifications.notification_service import NotificationService

router = APIRouter()


@router.post("/", response_model=WaitlistEntryResponse)
async def add_to_waitlist(
    waitlist_data: WaitlistEntryCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Add customer to waitlist."""
    try:
        booking_system = BookingSystem(db)
        
        # Create booking details for waitlist
        booking_details = {
            "party_size": waitlist_data.party_size,
            "date": None,  # Waitlist is for immediate seating
            "time": None,
            "special_requests": waitlist_data.special_requests
        }
        
        # Add to waitlist
        waitlist_result = await booking_system.add_to_waitlist(
            business_id=business.id,
            booking_details=booking_details,
            customer_phone=waitlist_data.customer_phone,
            customer_name=waitlist_data.customer_name,
            session_id=waitlist_data.session_id,
            preferences=waitlist_data.preferences
        )
        
        # Get the created waitlist entry
        waitlist_entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.id == waitlist_result["id"]
        ).first()
        
        if not waitlist_entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        
        return WaitlistEntryResponse(
            id=waitlist_entry.id,
            business_id=waitlist_entry.business_id,
            customer_name=waitlist_entry.customer_name,
            customer_phone=waitlist_entry.customer_phone,
            customer_email=waitlist_entry.customer_email,
            party_size=waitlist_entry.party_size,
            estimated_wait_time=waitlist_entry.estimated_wait_time,
            actual_wait_time=waitlist_entry.actual_wait_time,
            priority_score=waitlist_entry.priority_score,
            is_active=waitlist_entry.is_active,
            is_notified=waitlist_entry.is_notified,
            is_seated=waitlist_entry.is_seated,
            joined_at=waitlist_entry.joined_at,
            notified_at=waitlist_entry.notified_at,
            seated_at=waitlist_entry.seated_at,
            special_requests=waitlist_entry.special_requests,
            source=waitlist_entry.source,
            session_id=waitlist_entry.session_id,
            preferences=waitlist_entry.preferences,
            wait_duration=waitlist_entry.wait_duration,
            is_overdue=waitlist_entry.is_overdue
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add to waitlist: {str(e)}")


@router.get("/", response_model=List[WaitlistEntryResponse])
async def get_waitlist(
    active_only: bool = Query(True, description="Show only active entries"),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get current waitlist."""
    try:
        query = db.query(WaitlistEntry).filter(
            WaitlistEntry.business_id == business.id
        )
        
        if active_only:
            query = query.filter(WaitlistEntry.is_active == True)
        
        waitlist_entries = query.order_by(WaitlistEntry.joined_at).all()
        
        return [
            WaitlistEntryResponse(
                id=entry.id,
                business_id=entry.business_id,
                customer_name=entry.customer_name,
                customer_phone=entry.customer_phone,
                customer_email=entry.customer_email,
                party_size=entry.party_size,
                estimated_wait_time=entry.estimated_wait_time,
                actual_wait_time=entry.actual_wait_time,
                priority_score=entry.priority_score,
                is_active=entry.is_active,
                is_notified=entry.is_notified,
                is_seated=entry.is_seated,
                joined_at=entry.joined_at,
                notified_at=entry.notified_at,
                seated_at=entry.seated_at,
                special_requests=entry.special_requests,
                source=entry.source,
                session_id=entry.session_id,
                preferences=entry.preferences,
                wait_duration=entry.wait_duration,
                is_overdue=entry.is_overdue
            )
            for entry in waitlist_entries
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get waitlist: {str(e)}")


@router.get("/summary", response_model=WaitlistSummary)
async def get_waitlist_summary(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Get waitlist summary statistics."""
    try:
        booking_system = BookingSystem(db)
        summary = booking_system.get_waitlist_summary(business.id)
        
        return WaitlistSummary(**summary)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get waitlist summary: {str(e)}")


@router.put("/{waitlist_id}", response_model=WaitlistEntryResponse)
async def update_waitlist_entry(
    waitlist_id: int,
    update_data: WaitlistEntryUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Update waitlist entry."""
    try:
        waitlist_entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.id == waitlist_id,
            WaitlistEntry.business_id == business.id
        ).first()
        
        if not waitlist_entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        
        # Update fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(waitlist_entry, field, value)
        
        db.commit()
        db.refresh(waitlist_entry)
        
        return WaitlistEntryResponse(
            id=waitlist_entry.id,
            business_id=waitlist_entry.business_id,
            customer_name=waitlist_entry.customer_name,
            customer_phone=waitlist_entry.customer_phone,
            customer_email=waitlist_entry.customer_email,
            party_size=waitlist_entry.party_size,
            estimated_wait_time=waitlist_entry.estimated_wait_time,
            actual_wait_time=waitlist_entry.actual_wait_time,
            priority_score=waitlist_entry.priority_score,
            is_active=waitlist_entry.is_active,
            is_notified=waitlist_entry.is_notified,
            is_seated=waitlist_entry.is_seated,
            joined_at=waitlist_entry.joined_at,
            notified_at=waitlist_entry.notified_at,
            seated_at=waitlist_entry.seated_at,
            special_requests=waitlist_entry.special_requests,
            source=waitlist_entry.source,
            session_id=waitlist_entry.session_id,
            preferences=waitlist_entry.preferences,
            wait_duration=waitlist_entry.wait_duration,
            is_overdue=waitlist_entry.is_overdue
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update waitlist entry: {str(e)}")


@router.post("/{waitlist_id}/notify")
async def notify_customer(
    waitlist_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Notify customer that their table is ready."""
    try:
        waitlist_entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.id == waitlist_id,
            WaitlistEntry.business_id == business.id
        ).first()
        
        if not waitlist_entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        
        if not waitlist_entry.is_active:
            raise HTTPException(status_code=400, detail="Customer is no longer on waitlist")
        
        # Mark as notified
        waitlist_entry.mark_notified()
        db.commit()
        
        # Send notification
        notification_service = NotificationService(db)
        success = await notification_service.send_table_ready_notification(
            customer_phone=waitlist_entry.customer_phone,
            customer_name=waitlist_entry.customer_name,
            wait_time=waitlist_entry.wait_duration,
            business_name=business.name
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send notification")
        
        return {"message": "Customer notified successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to notify customer: {str(e)}")


@router.post("/{waitlist_id}/seat")
async def mark_customer_seated(
    waitlist_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Mark customer as seated and remove from waitlist."""
    try:
        booking_system = BookingSystem(db)
        success = await booking_system.mark_customer_seated(waitlist_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        
        return {"message": "Customer marked as seated"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark customer as seated: {str(e)}")


@router.delete("/{waitlist_id}")
async def remove_from_waitlist(
    waitlist_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business)
):
    """Remove customer from waitlist."""
    try:
        waitlist_entry = db.query(WaitlistEntry).filter(
            WaitlistEntry.id == waitlist_id,
            WaitlistEntry.business_id == business.id
        ).first()
        
        if not waitlist_entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        
        # Mark as inactive
        waitlist_entry.is_active = False
        db.commit()
        
        return {"message": "Customer removed from waitlist"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove from waitlist: {str(e)}")
