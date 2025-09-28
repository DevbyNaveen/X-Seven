# app/services/analytics_service.py - Update business_id parameter types

"""Analytics Service for Dashboard Operations."""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.config.database import get_supabase_client
from app.models.order import OrderStatus

class AnalyticsService:
    """Service for handling analytics operations on orders and messages tables."""

    def __init__(self):
        self.supabase = get_supabase_client()

    async def get_orders_analytics(
        self,
        business_id: str,  # ← Changed from int to str for UUID
        period: str = "7d",
        status_filter: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive orders analytics."""

        # Determine date range
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()
            if period == "1d":
                start_dt = end_dt - timedelta(days=1)
            elif period == "30d":
                start_dt = end_dt - timedelta(days=30)
            else:  # Default to 7 days
                start_dt = end_dt - timedelta(days=7)

        start_date_iso = start_dt.isoformat()
        end_date_iso = end_dt.isoformat()

        # Build query - business_id is now a string UUID
        query = self.supabase.table('orders').select('*').eq('business_id', business_id).gte('created_at', start_date_iso).lte('created_at', end_date_iso)

        if status_filter:
            query = query.eq('status', status_filter)

        orders_response = query.execute()
        orders = orders_response.data if orders_response.data else []

        # Calculate analytics
        analytics = {
            "business_id": business_id,  # Include business_id in response
            "period": period,
            "start_date": start_date_iso,
            "end_date": end_date_iso,
            "summary": {
                "total_orders": len(orders),
                "total_revenue": sum(order.get('total_amount', 0) for order in orders),
                "average_order_value": 0
            },
            "orders": orders
        }

        # Calculate average order value
        if analytics["summary"]["total_orders"] > 0:
            analytics["summary"]["average_order_value"] = (
                analytics["summary"]["total_revenue"] / analytics["summary"]["total_orders"]
            )

        # Status distribution
        status_counts = {}
        for order in orders:
            status = order.get('status')
            if status:
                status_counts[status] = status_counts.get(status, 0) + 1

        analytics["summary"]["status_distribution"] = status_counts

        # Daily trends
        daily_trends = {}
        for order in orders:
            created_at = order.get('created_at')
            if created_at:
                date_str = created_at.split('T')[0]
                if date_str not in daily_trends:
                    daily_trends[date_str] = {"count": 0, "revenue": 0}
                daily_trends[date_str]["count"] += 1
                daily_trends[date_str]["revenue"] += order.get('total_amount', 0)

        analytics["daily_breakdown"] = daily_trends
        analytics["generated_at"] = datetime.utcnow().isoformat()

        return analytics

    async def get_messages_analytics(
        self,
        business_id: str,  # ← Changed from int to str for UUID
        period: str = "7d",
        session_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive messages analytics."""

        # Determine date range
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()
            if period == "1d":
                start_dt = end_dt - timedelta(days=1)
            elif period == "30d":
                start_dt = end_dt - timedelta(days=30)
            else:  # Default to 7 days
                start_dt = end_dt - timedelta(days=7)

        start_date_iso = start_dt.isoformat()
        end_date_iso = end_dt.isoformat()

        # Build query - business_id is now a string UUID
        query = self.supabase.table('messages').select('*').eq('business_id', business_id).gte('created_at', start_date_iso).lte('created_at', end_date_iso)

        if session_id:
            query = query.eq('session_id', session_id)

        messages_response = query.execute()
        messages = messages_response.data if messages_response.data else []

        # Session statistics
        sessions = {}
        for message in messages:
            session_id_msg = message.get('session_id')
            if session_id_msg:
                if session_id_msg not in sessions:
                    sessions[session_id_msg] = []
                sessions[session_id_msg].append(message)

        # Session summary
        session_summary = []
        for session_id_key, session_messages in sessions.items():
            session_summary.append({
                "session_id": session_id_key,
                "message_count": len(session_messages),
                "first_message": min(msg.get('created_at', '') for msg in session_messages),
                "last_message": max(msg.get('created_at', '') for msg in session_messages),
                "duration_minutes": self._calculate_session_duration(session_messages)
            })

        # Calculate analytics
        analytics = {
            "business_id": business_id,  # Include business_id in response
            "period": period,
            "start_date": start_date_iso,
            "end_date": end_date_iso,
            "summary": {
                "total_messages": len(messages),
                "total_sessions": len(session_summary),
                "average_messages_per_session": 0,
                "sender_distribution": {}
            },
            "messages": messages,
            "session_stats": {session["session_id"]: session for session in session_summary}
        }

        # Calculate average messages per session
        if analytics["summary"]["total_sessions"] > 0:
            analytics["summary"]["average_messages_per_session"] = (
                analytics["summary"]["total_messages"] / analytics["summary"]["total_sessions"]
            )

        # Sender distribution
        sender_counts = {}
        for message in messages:
            sender = message.get('sender', 'unknown')
            sender_counts[sender] = sender_counts.get(sender, 0) + 1
        analytics["summary"]["sender_distribution"] = sender_counts

        # Daily message trends
        daily_trends = {}
        for message in messages:
            created_at = message.get('created_at')
            if created_at:
                date_str = created_at.split('T')[0]
                daily_trends[date_str] = daily_trends.get(date_str, 0) + 1

        analytics["daily_breakdown"] = daily_trends
        analytics["generated_at"] = datetime.utcnow().isoformat()

        return analytics

    async def get_combined_analytics(
        self,
        business_id: str,  # ← Changed from int to str for UUID
        period: str = "7d"
    ) -> Dict[str, Any]:
        """Get combined analytics from both orders and messages."""

        orders_analytics = await self.get_orders_analytics(business_id, period)
        messages_analytics = await self.get_messages_analytics(business_id, period)

        # Calculate combined metrics
        combined = {
            "business_id": business_id,  # String UUID
            "period": period,
            "start_date": orders_analytics["start_date"],
            "end_date": orders_analytics["end_date"],
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_orders": orders_analytics["summary"]["total_orders"],
                "total_revenue": orders_analytics["summary"]["total_revenue"],
                "total_messages": messages_analytics["summary"]["total_messages"],
                "total_sessions": messages_analytics["summary"]["total_sessions"],
                "average_order_value": orders_analytics["summary"]["average_order_value"],
                "average_messages_per_session": messages_analytics["summary"]["average_messages_per_session"],
                "messages_per_order": (
                    messages_analytics["summary"]["total_messages"] / orders_analytics["summary"]["total_orders"]
                    if orders_analytics["summary"]["total_orders"] > 0 else 0
                )
            },
            "orders_analytics": orders_analytics,
            "messages_analytics": messages_analytics
        }

        return combined

    async def get_dashboard_summary(self, business_id: str) -> Dict[str, Any]:  # ← Changed parameter type
        """Get dashboard summary with key metrics for quick overview."""
        
        # Get analytics for different time periods
        today_analytics = await self.get_combined_analytics(business_id, "1d")
        week_analytics = await self.get_combined_analytics(business_id, "7d")
        month_analytics = await self.get_combined_analytics(business_id, "30d")
        
        return {
            "business_id": business_id,  # String UUID
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

    async def create_order_analytics_record(
        self,
        business_id: str,  # ← Changed from int to str
        order_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new order record for analytics."""

        # Add business_id and timestamps
        order_data["business_id"] = business_id  # String UUID
        order_data["created_at"] = datetime.utcnow().isoformat()
        order_data["updated_at"] = datetime.utcnow().isoformat()

        # Ensure status is valid
        if "status" not in order_data:
            order_data["status"] = OrderStatus.PENDING

        response = self.supabase.table('orders').insert(order_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order record"
            )

        return {
            "success": True,
            "order_id": response.data[0]["id"],
            "message": "Order analytics record created successfully"
        }

    # Update other methods similarly to accept string business_id...
    
    def _calculate_session_duration(self, messages: List[Dict[str, Any]]) -> float:
        """Calculate session duration in minutes."""
        if not messages:
            return 0

        timestamps = []
        for msg in messages:
            created_at = msg.get('created_at')
            if created_at:
                try:
                    # Parse ISO timestamp
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    timestamps.append(dt)
                except:
                    continue

        if len(timestamps) < 2:
            return 0

        earliest = min(timestamps)
        latest = max(timestamps)
        duration = latest - earliest

        return duration.total_seconds() / 60  # Convert to minutes