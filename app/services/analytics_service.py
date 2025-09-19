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
        business_id: int,
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

        # Build query
        query = self.supabase.table('orders').select('*').eq('business_id', business_id).gte('created_at', start_date_iso).lte('created_at', end_date_iso)

        if status_filter:
            query = query.eq('status', status_filter)

        orders_response = query.execute()
        orders = orders_response.data if orders_response.data else []

        # Calculate analytics
        analytics = {
            "period": period,
            "start_date": start_date_iso,
            "end_date": end_date_iso,
            "total_orders": len(orders),
            "total_revenue": sum(order.get('total_amount', 0) for order in orders),
            "orders": orders
        }

        # Status distribution
        status_counts = {}
        for order in orders:
            status = order.get('status')
            if status:
                status_counts[status] = status_counts.get(status, 0) + 1

        analytics["status_distribution"] = status_counts

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

        analytics["daily_trends"] = daily_trends

        # Average order value
        analytics["average_order_value"] = (
            analytics["total_revenue"] / analytics["total_orders"]
            if analytics["total_orders"] > 0 else 0
        )

        return analytics

    async def get_messages_analytics(
        self,
        business_id: int,
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

        # Build query
        query = self.supabase.table('messages').select('*').eq('business_id', business_id).gte('created_at', start_date_iso).lte('created_at', end_date_iso)

        if session_id:
            query = query.eq('session_id', session_id)

        messages_response = query.execute()
        messages = messages_response.data if messages_response.data else []

        # Calculate analytics
        analytics = {
            "period": period,
            "start_date": start_date_iso,
            "end_date": end_date_iso,
            "total_messages": len(messages),
            "messages": messages
        }

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

        analytics["sessions"] = session_summary
        analytics["total_sessions"] = len(session_summary)

        # Daily message trends
        daily_trends = {}
        for message in messages:
            created_at = message.get('created_at')
            if created_at:
                date_str = created_at.split('T')[0]
                daily_trends[date_str] = daily_trends.get(date_str, 0) + 1

        analytics["daily_trends"] = daily_trends

        # Average messages per session
        analytics["average_messages_per_session"] = (
            analytics["total_messages"] / analytics["total_sessions"]
            if analytics["total_sessions"] > 0 else 0
        )

        return analytics

    async def create_order_analytics_record(
        self,
        business_id: int,
        order_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new order record for analytics."""

        # Add business_id and timestamps
        order_data["business_id"] = business_id
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

        return response.data[0]

    async def update_order_status(
        self,
        business_id: int,
        order_id: str,
        new_status: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update order status for analytics tracking."""

        update_data = {
            "status": new_status,
            "updated_at": datetime.utcnow().isoformat()
        }

        if additional_data:
            update_data.update(additional_data)

        response = self.supabase.table('orders').update(update_data).eq('id', order_id).eq('business_id', business_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or update failed"
            )

        return response.data[0]

    async def create_message_analytics_record(
        self,
        business_id: int,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new message record for analytics."""

        # Add business_id and timestamp
        message_data["business_id"] = business_id
        message_data["created_at"] = datetime.utcnow().isoformat()

        response = self.supabase.table('messages').insert(message_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create message record"
            )

        return response.data[0]

    async def get_combined_analytics(
        self,
        business_id: int,
        period: str = "7d"
    ) -> Dict[str, Any]:
        """Get combined analytics from both orders and messages."""

        orders_analytics = await self.get_orders_analytics(business_id, period)
        messages_analytics = await self.get_messages_analytics(business_id, period)

        # Calculate combined metrics
        combined = {
            "period": period,
            "business_id": business_id,
            "generated_at": datetime.utcnow().isoformat(),
            "orders": orders_analytics,
            "messages": messages_analytics,
            "summary": {
                "total_orders": orders_analytics["total_orders"],
                "total_revenue": orders_analytics["total_revenue"],
                "total_messages": messages_analytics["total_messages"],
                "total_sessions": messages_analytics["total_sessions"],
                "average_order_value": orders_analytics["average_order_value"],
                "average_messages_per_session": messages_analytics["average_messages_per_session"],
                "messages_per_order": (
                    messages_analytics["total_messages"] / orders_analytics["total_orders"]
                    if orders_analytics["total_orders"] > 0 else 0
                )
            }
        }

        return combined

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
