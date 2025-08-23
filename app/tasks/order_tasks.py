"""Background tasks for order processing and scheduling."""
from datetime import datetime, timedelta
import asyncio
import logging

from app.config.database import get_db
from app.tasks.app import celery_app
from app.models import Order, MenuItem, OrderStatus
from app.services.business.order_service import OrderService
from app.services.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)


@celery_app.task
def process_scheduled_order(order_id: int) -> bool:
    """
    Process a scheduled order when its time comes.
    This task is scheduled to run at the order's scheduled_time.
    """
    try:
        db = next(get_db())
        notification_service = NotificationService(db)
        order_service = OrderService(db)
        
        # Get the order
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            logger.error(f"Scheduled order {order_id} not found")
            return False
        
        # Check if order is still valid
        if order.status != OrderStatus.PENDING:
            logger.info(f"Order {order_id} is no longer pending, skipping")
            return False
        
        # Transition order status to confirmed at scheduled time
        try:
            asyncio.run(order_service.confirm_order(order_id=order_id, business_id=order.business_id))
        except Exception as e:
            logger.error(f"Failed to confirm scheduled order {order_id}: {e}")
            return False
        
        # Send notification to customer
        if order.customer_phone:
            asyncio.run(notification_service.send_order_confirmation(
                customer_phone=order.customer_phone,
                order_id=order.id,
                business_name=order.business.name,
                estimated_time=order.estimated_ready_time
            ))
        
        logger.info(f"Successfully processed scheduled order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing scheduled order {order_id}: {e}")
        return False
    finally:
        db.close()


@celery_app.task
def process_delivery_order(order_id: int) -> bool:
    """
    Process a delivery order.
    This includes coordinating with delivery service and tracking.
    """
    try:
        db = next(get_db())
        notification_service = NotificationService(db)
        
        # Get the order
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            logger.error(f"Delivery order {order_id} not found")
            return False
        
        # Send delivery notification
        if order.customer_phone:
            asyncio.run(notification_service.send_delivery_notification(
                customer_phone=order.customer_phone,
                order_id=order.id,
                delivery_address=order.delivery_address,
                estimated_delivery_time=None
            ))
        
        logger.info(f"Successfully processed delivery order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing delivery order {order_id}: {e}")
        return False
    finally:
        db.close()


@celery_app.task
def update_inventory_after_order(order_id: int) -> bool:
    """
    Update inventory levels after an order is placed.
    """
    try:
        db = next(get_db())
        notification_service = NotificationService(db)
        
        # Get the order
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            logger.error(f"Order {order_id} not found for inventory update")
            return False
        
        # Update inventory for each item
        for item_data in order.items:
            item_id = item_data.get("item_id")
            quantity = item_data.get("quantity", 1)
            
            if item_id:
                menu_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
                if menu_item and menu_item.stock_quantity > 0:
                    # Decrement stock
                    menu_item.stock_quantity = max(0, menu_item.stock_quantity - quantity)
                    
                    # Check if stock is low
                    if menu_item.stock_quantity <= menu_item.min_stock_threshold:
                        # Send low stock alert (run async method safely in sync task)
                        asyncio.run(notification_service.send_low_stock_alert(
                            business_id=order.business_id,
                            item_name=menu_item.name,
                            current_stock=menu_item.stock_quantity,
                            threshold=menu_item.min_stock_threshold
                        ))
        
        db.commit()
        logger.info(f"Successfully updated inventory for order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating inventory for order {order_id}: {e}")
        return False
    finally:
        db.close()


@celery_app.task
def send_low_stock_alert(menu_item_id: int, business_id: int) -> bool:
    """
    Send low stock alert to business staff.
    """
    try:
        db = next(get_db())
        notification_service = NotificationService(db)
        
        # Load item and send alert
        menu_item = db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
        if menu_item:
            asyncio.run(notification_service.send_low_stock_alert(
                business_id=business_id,
                item_name=menu_item.name,
                current_stock=menu_item.stock_quantity,
                threshold=menu_item.min_stock_threshold
            ))
            logger.info(f"Sent low stock alert for {menu_item.name}")
            return True
        
        logger.warning(f"Menu item {menu_item_id} not found for low stock alert")
        return False
        
    except Exception as e:
        logger.error(f"Error sending low stock alert: {e}")
        return False
    finally:
        db.close()


@celery_app.task
def cleanup_expired_orders() -> bool:
    """
    Clean up expired orders (orders that were never confirmed).
    """
    try:
        db = next(get_db())
        
        # Find orders that are pending and older than 1 hour
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        expired_orders = db.query(Order).filter(
            Order.status == OrderStatus.PENDING,
            Order.created_at < cutoff_time
        ).all()
        
        for order in expired_orders:
            order.status = OrderStatus.CANCELLED
            logger.info(f"Cancelled expired order {order.id}")
        
        db.commit()
        logger.info(f"Cleaned up {len(expired_orders)} expired orders")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning up expired orders: {e}")
        return False
    finally:
        db.close()


@celery_app.task
def process_waitlist_notifications() -> bool:
    """
    Process waitlist notifications and send updates to customers.
    """
    try:
        db = next(get_db())
        notification_service = NotificationService(db)
        
        # Get customers who have been waiting longer than estimated time
        from app.models import WaitlistEntry
        
        overdue_customers = db.query(WaitlistEntry).filter(
            WaitlistEntry.is_active == True,
            WaitlistEntry.is_overdue == True,
            WaitlistEntry.is_notified == False
        ).all()
        
        for customer in overdue_customers:
            # Send update notification
            asyncio.run(notification_service.send_waitlist_update(
                customer_phone=customer.customer_phone,
                customer_name=customer.customer_name,
                current_wait_time=customer.wait_duration,
                estimated_wait_time=customer.estimated_wait_time
            ))
            
            # Mark as notified
            customer.is_notified = True
            db.commit()
        
        logger.info(f"Processed waitlist notifications for {len(overdue_customers)} customers")
        return True
        
    except Exception as e:
        logger.error(f"Error processing waitlist notifications: {e}")
        return False
    finally:
        db.close()


# Schedule periodic tasks
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Set up periodic tasks."""
    # Clean up expired orders every 30 minutes
    sender.add_periodic_task(
        30 * 60,  # 30 minutes
        cleanup_expired_orders.s(),
        name='cleanup-expired-orders'
    )
    
    # Process waitlist notifications every 15 minutes
    sender.add_periodic_task(
        15 * 60,  # 15 minutes
        process_waitlist_notifications.s(),
        name='process-waitlist-notifications'
    )


def schedule_order_processing(order_id: int, scheduled_time: datetime) -> str:
    """
    Schedule an order to be processed at a specific time.
    Returns the task ID.
    """
    # Calculate delay until scheduled time
    now = datetime.utcnow()
    delay_seconds = (scheduled_time - now).total_seconds()
    
    if delay_seconds <= 0:
        # Process immediately if scheduled time has passed
        result = process_scheduled_order.delay(order_id)
        return result.id
    else:
        # Schedule for later
        result = process_scheduled_order.apply_async(
            args=[order_id],
            countdown=int(delay_seconds)
        )
        return result.id


def schedule_delivery_processing(order_id: int, delivery_time: datetime) -> str:
    """
    Schedule a delivery order to be processed.
    Returns the task ID.
    """
    # Calculate delay until delivery time
    now = datetime.utcnow()
    delay_seconds = (delivery_time - now).total_seconds()
    
    if delay_seconds <= 0:
        # Process immediately if delivery time has passed
        result = process_delivery_order.delay(order_id)
        return result.id
    else:
        # Schedule for later
        result = process_delivery_order.apply_async(
            args=[order_id],
            countdown=int(delay_seconds)
        )
        return result.id
