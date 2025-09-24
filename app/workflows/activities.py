import asyncio
from datetime import datetime
import logging

from temporalio import activity

from app.config.database import get_supabase_client
from app.models import Order, MenuItem, OrderStatus
from app.services.business.order_service import OrderService
from app.services.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)

@activity.defn
async def confirm_order(order_id: int, business_id: int) -> bool:
    """Confirms an order."""
    try:
        with get_supabase_client() as db:
            order_service = OrderService(db)
            await order_service.confirm_order(order_id=order_id, business_id=business_id)
            return True
    except Exception as e:
        logger.error(f"Failed to confirm order {order_id}: {e}")
        return False

@activity.defn
async def send_order_confirmation(order_id: int) -> bool:
    """Sends an order confirmation notification."""
    try:
        with get_supabase_client() as db:
            notification_service = NotificationService(db)
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                logger.error(f"Order {order_id} not found for confirmation notification")
                return False

            if order.customer_phone:
                await notification_service.send_order_confirmation(
                    customer_phone=order.customer_phone,
                    order_id=order.id,
                    business_name=order.business.name,
                    estimated_time=order.estimated_ready_time
                )
            return True
    except Exception as e:
        logger.error(f"Error sending order confirmation for {order_id}: {e}")
        return False

@activity.defn
async def process_delivery(order_id: int) -> bool:
    """Processes a delivery order."""
    try:
        with get_supabase_client() as db:
            notification_service = NotificationService(db)
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                logger.error(f"Delivery order {order_id} not found")
                return False

            if order.customer_phone:
                await notification_service.send_delivery_notification(
                    customer_phone=order.customer_phone,
                    order_id=order.id,
                    delivery_address=order.delivery_address,
                    estimated_delivery_time=None
                )
            return True
    except Exception as e:
        logger.error(f"Error processing delivery for order {order_id}: {e}")
        return False

@activity.defn
async def update_inventory(order_id: int) -> bool:
    """Updates inventory after an order is placed."""
    try:
        with get_supabase_client() as db:
            notification_service = NotificationService(db)
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                logger.error(f"Order {order_id} not found for inventory update")
                return False

            for item_data in order.items:
                item_id = item_data.get("item_id")
                quantity = item_data.get("quantity", 1)

                if item_id:
                    menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
                    if menu_item and menu_item.stock_quantity > 0:
                        menu_item.stock_quantity = max(0, menu_item.stock_quantity - quantity)

                        if menu_item.stock_quantity <= menu_item.min_stock_threshold:
                            await notification_service.send_low_stock_alert(
                                business_id=order.business_id,
                                item_name=menu_item.name,
                                current_stock=menu_item.stock_quantity,
                                threshold=menu_item.min_stock_threshold
                            )
            db.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating inventory for order {order_id}: {e}")
        return False
