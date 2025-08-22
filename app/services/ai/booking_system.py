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
        """Return empty list to indicate no tables available by default."""
        return []

    async def get_daily_availability(
        self,
        *,
        business_id: int,
        date: date,
        party_size: int,
        duration: int,
    ) -> List[Dict[str, Any]]:
        """Return empty availability list by default."""
        return []

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
