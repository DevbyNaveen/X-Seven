"""Stub BookingSystem for booking and waitlist endpoints.

Provides minimal async methods with safe defaults to unblock server startup.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
import pytz

from app.models.table import Table
from app.models.business import Business


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
        # Simple stub implementation: return capacity-suitable Table ORM objects.
        # Note: The current Appointment model does not link to tables, thus we
        # avoid table-level conflict checks and apply demo-time randomization.
        import random

        tables = (
            self.db.query(Table)
            .filter(
                Table.business_id == business_id,
                Table.capacity >= party_size,
            )
            .all()
        )

        if not tables:
            return []

        # Demo randomization: sometimes mark peak/busy hours as unavailable
        hour = booking_time.hour
        if hour in [12, 13, 19, 20]:  # Peak hours
            if random.random() < 0.8:
                return []
        elif hour in [11, 14, 18, 21]:  # Busy hours
            if random.random() < 0.5:
                return []

        return tables

    async def get_daily_availability(
        self,
        *,
        business_id: int,
        date: date,
        party_size: int,
        duration: int,
    ) -> List[Dict[str, Any]]:
        """Get availability for an entire day grouped by table.
        
        Returns a list of items compatible with TableAvailability schema:
        [{
            "table_id": int,
            "table_number": str,
            "capacity": int,
            "available_times": List[str],  # e.g., ["09:00", "10:00", ...]
            "is_available": bool
        }]
        """
        # Load business settings for hours and timezone
        business: Optional[Business] = (
            self.db.query(Business).filter(Business.id == business_id).first()
        )
        booking_settings: Dict[str, Any] = {}
        if business and isinstance(business.settings, dict):
            booking_settings = business.settings.get("booking", {}) or {}

        start_str = booking_settings.get("business_hours_start", "09:00")
        end_str = booking_settings.get("business_hours_end", "22:00")
        tz_name = booking_settings.get("timezone", "UTC")

        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.UTC

        def parse_hhmm(s: str) -> int:
            """Return hour integer from HH:MM string; defaults to 0 on error."""
            try:
                return int(s.split(":")[0])
            except Exception:
                return 0

        opening_hour = parse_hhmm(start_str)
        closing_hour = parse_hhmm(end_str)
        if closing_hour <= opening_hour:
            # Fallback to defaults if misconfigured
            opening_hour, closing_hour = 9, 22

        # Initialize per-table availability map
        tables = (
            self.db.query(Table)
            .filter(Table.business_id == business_id, Table.capacity >= party_size)
            .all()
        )

        if not tables:
            return []

        table_map: Dict[int, Dict[str, Any]] = {
            t.id: {
                "table_id": t.id,
                "table_number": t.table_number,
                "capacity": t.capacity,
                "available_times": [],
                "is_available": False,
            }
            for t in tables
        }

        # Iterate through each hour in business hours and collect availability
        base_day = datetime.combine(date, datetime.min.time())
        for hour in range(opening_hour, closing_hour):
            local_dt = tz.localize(base_day.replace(hour=hour, minute=0, second=0, microsecond=0))

            available_at_slot = await self.check_availability(
                business_id=business_id,
                party_size=party_size,
                booking_time=local_dt,
                duration=duration,
            )

            if not available_at_slot:
                continue

            time_label = local_dt.strftime("%H:%M")
            # available_at_slot returns Table ORM objects
            for tbl in available_at_slot:
                if tbl.id in table_map:
                    table_map[tbl.id]["available_times"].append(time_label)
                    table_map[tbl.id]["is_available"] = True

        # Return list of table availability entries
        return list(table_map.values())

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
