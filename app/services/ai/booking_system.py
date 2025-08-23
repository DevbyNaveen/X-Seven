"""Stub BookingSystem for booking and waitlist endpoints.

Provides minimal async methods with safe defaults to unblock server startup.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session


class AttrDict(dict):
    """Dict that allows attribute-style access for convenience in stubs."""
    def __getattr__(self, item):
        return self.get(item)


@dataclass
class StubBooking:
    id: int
    customer_name: str
    customer_phone: str
    customer_email: Optional[str]
    party_size: int
    booking_time: datetime
    duration: int
    table_id: Optional[int]
    status: str
    special_requests: Optional[str]
    source: str
    created_at: datetime


class BookingSystem:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Booking operations ---
    async def check_availability(
        self,
        *,
        business_id: int,
        party_size: int,
        booking_time: datetime,
        duration: int,
    ) -> List[Any]:
        """Check if tables are available for the given parameters.
        
        Returns a list of available tables or empty list if none available.
        """
        # Get all appointments for this business on the same day
        from app.models.appointment import Appointment
        from sqlalchemy import and_, or_
        import random
        
        # Get the date part of booking_time for date comparison
        booking_date = booking_time.date()
        
        # Query existing appointments for this business on this date
        existing_appointments = self.db.query(Appointment).filter(
            Appointment.business_id == business_id,
            Appointment.scheduled_date.cast('date') == booking_date,
            Appointment.status.in_(['scheduled', 'confirmed', 'in_progress']),
        ).all()
        
        # Get all tables for this business
        from app.models.table import Table
        tables = self.db.query(Table).filter(
            Table.business_id == business_id,
            Table.is_active == True,
            Table.capacity >= party_size,
        ).all()
        
        if not tables:
            # No tables exist or none with sufficient capacity
            return []
            
        # Calculate end time for requested booking
        booking_end_time = booking_time + datetime.timedelta(minutes=duration)
        
        # Filter out tables that have conflicting appointments
        available_tables = []
        for table in tables:
            is_available = True
            
            # Check if table has any conflicting appointments
            for appt in existing_appointments:
                if appt.table_id == table.id:
                    appt_start = appt.start_time
                    appt_end = appt.end_time
                    
                    # Check for overlap
                    if (booking_time < appt_end and booking_end_time > appt_start):
                        is_available = False
                        break
            
            if is_available:
                available_tables.append({
                    "table_id": table.id,
                    "name": table.name,
                    "capacity": table.capacity,
                })
        
        # For demo purposes, randomly make some times unavailable
        # Remove this in production for real availability
        hour = booking_time.hour
        if hour in [12, 13, 19, 20]:  # Peak hours
            # 80% chance of being fully booked during peak hours
            if random.random() < 0.8:
                return []
        elif hour in [11, 14, 18, 21]:  # Busy hours
            # 50% chance of being fully booked during busy hours
            if random.random() < 0.5:
                return []
        
        return available_tables

    async def get_daily_availability(
        self,
        *,
        business_id: int,
        date: date,
        party_size: int,
        duration: int,
    ) -> List[Dict[str, Any]]:
        """Get availability for an entire day.
        
        Returns a list of available time slots with available tables.
        """
        from datetime import datetime, timedelta
        import pytz
        
        # Get business opening hours (default to 9 AM - 10 PM if not specified)
        # In a real implementation, this would come from business settings
        opening_hour = 9  # 9 AM
        closing_hour = 22  # 10 PM
        
        # Create a list of time slots to check (hourly for simplicity)
        time_slots = []
        for hour in range(opening_hour, closing_hour):
            # Create datetime for this hour on the specified date
            slot_time = datetime.combine(date, datetime.min.time())
            slot_time = slot_time.replace(hour=hour, tzinfo=pytz.UTC)
            
            # Check availability for this time slot
            available_tables = await self.check_availability(
                business_id=business_id,
                party_size=party_size,
                booking_time=slot_time,
                duration=duration
            )
            
            if available_tables:
                time_slots.append({
                    "time": slot_time.strftime("%H:%M"),
                    "available": True,
                    "available_tables": len(available_tables),
                    "tables": available_tables
                })
            else:
                time_slots.append({
                    "time": slot_time.strftime("%H:%M"),
                    "available": False,
                    "available_tables": 0,
                    "tables": []
                })
        
        return time_slots

    async def create_booking(
        self,
        *,
        business_id: int,
        customer_name: str,
        customer_phone: str,
        customer_email: Optional[str] = None,
        party_size: int,
        booking_time: datetime,
        duration: int = 120,
        table_id: Optional[int] = None,
        special_requests: Optional[str] = None,
        source: Any = "website",
    ) -> StubBooking:
        """Return a stub booking object. Not persisted."""
        now = datetime.utcnow()
        return StubBooking(
            id=0,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            party_size=party_size,
            booking_time=booking_time,
            duration=duration,
            table_id=table_id,
            status="confirmed",
            special_requests=special_requests,
            source=str(source),
            created_at=now,
        )

    async def get_bookings(
        self,
        *,
        business_id: int,
        status: Optional[str] = None,
        date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StubBooking]:
        """Return empty list by default."""
        return []

    async def get_booking(self, booking_id: int, business_id: int) -> Optional[StubBooking]:
        """Return None to indicate not found by default."""
        return None

    async def update_booking_status(self, *, booking_id: int, business_id: int, status: str) -> bool:
        """Pretend to update booking status and succeed."""
        return True

    async def cancel_booking(self, *, booking_id: int, business_id: int, reason: Optional[str] = None) -> bool:
        """Pretend to cancel a booking and succeed."""
        return True

    async def get_analytics(
        self,
        *,
        business_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Return safe default analytics structure."""
        return {
            "total_bookings": 0,
            "confirmed_bookings": 0,
            "cancelled_bookings": 0,
            "no_shows": 0,
            "average_party_size": 0.0,
            "peak_hours": [],
            "popular_tables": [],
            "booking_sources": {},
            "conversion_rate": 0.0,
        }

    async def get_calendar_view(self, *, business_id: int, date: date) -> List[Dict[str, Any]]:
        """Return empty calendar view."""
        return []

    async def send_reminder(self, *, booking_id: int, business_id: int, reminder_type: str) -> bool:
        """Pretend to send a reminder and succeed."""
        return True

    # --- Waitlist operations ---
    async def get_waitlist(self, business_id: int) -> List[Dict[str, Any]]:
        """Return empty waitlist by default."""
        return []

    async def add_to_waitlist(
        self,
        *,
        business_id: int,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        party_size: Optional[int] = None,
        estimated_wait: Optional[int] = None,
        booking_details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> AttrDict:
        """Support both bookings and waitlist endpoints.

        Returns an AttrDict that can be used as both dict (for ["id"]) and via
        attribute access (for .position, .estimated_wait).
        """
        return AttrDict({
            "id": 0,
            "position": 1,
            "estimated_wait": estimated_wait if estimated_wait is not None else 15,
        })

    async def mark_customer_seated(self, waitlist_id: int) -> bool:
        """Pretend to mark a customer as seated and succeed."""
        return True

    # Sync method used by waitlist endpoints
    def get_waitlist_summary(self, business_id: int) -> Dict[str, Any]:
        """Return minimal summary information."""
        return {
            "total_waiting": 0,
            "average_wait_time": 0,
            "estimated_wait_time": 0,
            "longest_wait": 0,
            "priority_customers": 0,
        }
