import logging
from datetime import datetime, timedelta

from temporalio import activity

from app.config.database import get_supabase_client
from app.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

@activity.defn
async def cleanup_expired_orders_activity():
    """Cleans up expired orders (orders that were never confirmed)."""
    try:
        with get_supabase_client() as db:
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            expired_orders = (
                db.query(Order)
                .filter(
                    Order.status == OrderStatus.PENDING,
                    Order.created_at < cutoff_time,
                )
                .all()
            )

            for order in expired_orders:
                order.status = OrderStatus.CANCELLED
                logger.info(f"Cancelled expired order {order.id}")

            db.commit()
            logger.info(f"Cleaned up {len(expired_orders)} expired orders")
            return True
    except Exception as e:
        logger.error(f"Error cleaning up expired orders: {e}")
        raise
