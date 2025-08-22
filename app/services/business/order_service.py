"""Order processing business logic."""
import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.models import Order, MenuItem, Table, OrderStatus, PaymentStatus, Business
from app.schemas.order import OrderCreate, OrderItemSchema
from app.services.notifications.notification_service import NotificationService

logger = logging.getLogger(__name__)


class OrderService:
    """Service for managing orders - Single source of truth for all order operations."""
    
    def __init__(self, db: Session):
        self.db = db
        # Inject notification service for comprehensive order management
        self.notification_service = NotificationService(db)
    
    async def create_order(
        self,
        business_id: int,
        order_data: OrderCreate,
        customer_id: Optional[int] = None
    ) -> Order:
        """
        Create a new order with validation and notifications.
        
        Args:
            business_id: Business ID
            order_data: Order creation data
            customer_id: Optional customer ID
            
        Returns:
            Created order
            
        Raises:
            ValueError: If validation fails
        """
        # Validate items exist and are available
        validated_items = []
        subtotal = 0.0
        
        for item_data in order_data.items:
            menu_item = self.db.query(MenuItem).filter(
                MenuItem.id == item_data.item_id,
                MenuItem.business_id == business_id
            ).first()
            
            if not menu_item:
                raise ValueError(f"Menu item {item_data.item_id} not found")
            
            if not menu_item.is_available:
                raise ValueError(f"{menu_item.name} is not available")
            
            # Calculate item total with customizations
            item_total = self._calculate_item_price(
                menu_item,
                item_data.customizations,
                item_data.quantity
            )
            
            validated_items.append({
                "item_id": menu_item.id,
                "name": menu_item.name,
                "quantity": item_data.quantity,
                "unit_price": item_data.unit_price,
                "customizations": item_data.customizations,
                "subtotal": item_total
            })
            
            subtotal += item_total
        
        # Calculate tax (8% for demo)
        tax_rate = 0.08
        tax_amount = round(subtotal * tax_rate, 2)
        total_amount = round(subtotal + tax_amount, 2)
        
        # Create order
        order = Order(
            business_id=business_id,
            customer_id=customer_id,
            customer_name=order_data.customer_name,
            customer_phone=order_data.customer_phone,
            customer_email=order_data.customer_email,
            table_id=order_data.table_id,
            order_type=order_data.order_type,
            items=validated_items,
            subtotal=subtotal,
            tax_amount=tax_amount,
            tip_amount=0,
            total_amount=total_amount,
            status=OrderStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            payment_method=order_data.payment_method,
            special_instructions=order_data.special_instructions,
            session_id=str(uuid.uuid4())  # Generate session ID
        )
        
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        
        # NEW: The service itself is now responsible for triggering notifications
        # This is more robust than having the endpoint do it.
        try:
            # Get business for notification context
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business and order.customer_phone:
                # Send order confirmation notification
                await self.notification_service.send_order_confirmation(
                    order=order,
                    business=business,
                    customer_phone=order.customer_phone,
                    customer_name=order.customer_name or "Guest"
                )
                
                # Send staff alert for new order
                await self.notification_service.send_staff_alert(
                    business=business,
                    alert_type="New Order",
                    message=f"New order #{order.id} received - ${order.total_amount:.2f}",
                    priority="normal"
                )
        except Exception as e:
            logger.error(f"Failed to send notifications for order {order.id}: {e}")
            # Don't fail the order creation if notifications fail
        
        return order
    
    # NEW: Add methods for all state transitions
    async def confirm_order(self, order_id: int, business_id: int) -> Order:
        """
        Confirm an order - transition from PENDING to CONFIRMED.
        
        Args:
            order_id: Order ID to confirm
            business_id: Business ID for validation
            
        Returns:
            Updated order
            
        Raises:
            ValueError: If order not found or invalid transition
        """
        order = self._get_order(order_id, business_id)
        
        if order.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot confirm order in {order.status} status")
        
        order.status = OrderStatus.CONFIRMED
        order.confirmed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(order)
        
        # Send confirmation notification
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business and order.customer_phone:
                await self.notification_service.send_order_status_update(
                    order=order,
                    business=business,
                    status=OrderStatus.CONFIRMED,
                    customer_phone=order.customer_phone
                )
        except Exception as e:
            logger.error(f"Failed to send confirmation notification for order {order.id}: {e}")
        
        return order
    
    async def start_preparation(self, order_id: int, business_id: int, estimated_minutes: int = 15) -> Order:
        """
        Start order preparation - transition from CONFIRMED to PREPARING.
        
        Args:
            order_id: Order ID to start preparation
            business_id: Business ID for validation
            estimated_minutes: Estimated preparation time
            
        Returns:
            Updated order
            
        Raises:
            ValueError: If order not found or invalid transition
        """
        order = self._get_order(order_id, business_id)
        
        if order.status != OrderStatus.CONFIRMED:
            raise ValueError(f"Cannot start preparation for order in {order.status} status")
        
        order.status = OrderStatus.PREPARING
        order.estimated_ready_time = datetime.utcnow() + timedelta(minutes=estimated_minutes)
        order.preparation_started_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(order)
        
        # Send preparation notification
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business and order.customer_phone:
                await self.notification_service.send_order_status_update(
                    order=order,
                    business=business,
                    status=OrderStatus.PREPARING,
                    customer_phone=order.customer_phone
                )
        except Exception as e:
            logger.error(f"Failed to send preparation notification for order {order.id}: {e}")
        
        return order
    
    async def mark_ready(self, order_id: int, business_id: int) -> Order:
        """
        Mark order as ready - transition from PREPARING to READY.
        
        Args:
            order_id: Order ID to mark ready
            business_id: Business ID for validation
            
        Returns:
            Updated order
            
        Raises:
            ValueError: If order not found or invalid transition
        """
        order = self._get_order(order_id, business_id)
        
        if order.status != OrderStatus.PREPARING:
            raise ValueError(f"Cannot mark order ready in {order.status} status")
        
        order.status = OrderStatus.READY
        order.ready_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(order)
        
        # Send ready notification
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business and order.customer_phone:
                await self.notification_service.send_order_status_update(
                    order=order,
                    business=business,
                    status=OrderStatus.READY,
                    customer_phone=order.customer_phone
                )
        except Exception as e:
            logger.error(f"Failed to send ready notification for order {order.id}: {e}")
        
        return order
    
    async def complete_order(self, order_id: int, business_id: int) -> Order:
        """
        Complete order - transition from READY to COMPLETED.
        
        Args:
            order_id: Order ID to complete
            business_id: Business ID for validation
            
        Returns:
            Updated order
            
        Raises:
            ValueError: If order not found or invalid transition
        """
        order = self._get_order(order_id, business_id)
        
        if order.status != OrderStatus.READY:
            raise ValueError(f"Cannot complete order in {order.status} status")
        
        order.status = OrderStatus.COMPLETED
        order.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(order)
        
        # Send completion notification
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business and order.customer_phone:
                await self.notification_service.send_order_status_update(
                    order=order,
                    business=business,
                    status=OrderStatus.COMPLETED,
                    customer_phone=order.customer_phone
                )
        except Exception as e:
            logger.error(f"Failed to send completion notification for order {order.id}: {e}")
        
        return order
    
    async def cancel_order(self, order_id: int, business_id: int, reason: str = "Customer request") -> Order:
        """
        Cancel order - can be done from any status except COMPLETED.
        
        Args:
            order_id: Order ID to cancel
            business_id: Business ID for validation
            reason: Reason for cancellation
            
        Returns:
            Updated order
            
        Raises:
            ValueError: If order not found or already completed
        """
        order = self._get_order(order_id, business_id)
        
        if order.status == OrderStatus.COMPLETED:
            raise ValueError("Cannot cancel completed order")
        
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.utcnow()
        order.cancellation_reason = reason
        
        self.db.commit()
        self.db.refresh(order)
        
        # Send cancellation notification
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business and order.customer_phone:
                await self.notification_service.send_order_status_update(
                    order=order,
                    business=business,
                    status=OrderStatus.CANCELLED,
                    customer_phone=order.customer_phone
                )
        except Exception as e:
            logger.error(f"Failed to send cancellation notification for order {order.id}: {e}")
        
        return order
    
    async def update_payment_status(self, order_id: int, business_id: int, payment_status: PaymentStatus, payment_method: str = None) -> Order:
        """
        Update payment status of an order.
        
        Args:
            order_id: Order ID to update
            business_id: Business ID for validation
            payment_status: New payment status
            payment_method: Payment method used
            
        Returns:
            Updated order
            
        Raises:
            ValueError: If order not found
        """
        order = self._get_order(order_id, business_id)
        
        order.payment_status = payment_status
        if payment_method:
            order.payment_method = payment_method
        
        if payment_status == PaymentStatus.PAID:
            order.paid_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(order)
        
        # Send payment notification
        try:
            business = self.db.query(Business).filter(Business.id == business_id).first()
            if business and order.customer_phone:
                await self.notification_service.send_payment_notification(
                    order=order,
                    business=business,
                    customer_phone=order.customer_phone,
                    payment_status=payment_status.value,
                    payment_method=payment_method or order.payment_method or "Unknown"
                )
        except Exception as e:
            logger.error(f"Failed to send payment notification for order {order.id}: {e}")
        
        return order
    
    def add_tip(self, order_id: int, business_id: int, tip_amount: float) -> Order:
        """
        Add tip to an order.
        
        Args:
            order_id: Order ID to add tip to
            business_id: Business ID for validation
            tip_amount: Tip amount to add
            
        Returns:
            Updated order
            
        Raises:
            ValueError: If order not found or tip amount invalid
        """
        if tip_amount < 0:
            raise ValueError("Tip amount cannot be negative")
        
        order = self._get_order(order_id, business_id)
        
        order.tip_amount = tip_amount
        order.total_amount = order.subtotal + order.tax_amount + tip_amount
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def get_order_summary(self, order_id: int, business_id: int) -> Dict[str, Any]:
        """
        Get comprehensive order summary including status and timing information.
        
        Args:
            order_id: Order ID to get summary for
            business_id: Business ID for validation
            
        Returns:
            Order summary dictionary
            
        Raises:
            ValueError: If order not found
        """
        order = self._get_order(order_id, business_id)
        
        # Calculate timing information
        timing_info = {}
        if order.confirmed_at:
            timing_info["confirmed_at"] = order.confirmed_at.isoformat()
        if order.preparation_started_at:
            timing_info["preparation_started_at"] = order.preparation_started_at.isoformat()
        if order.ready_at:
            timing_info["ready_at"] = order.ready_at.isoformat()
        if order.completed_at:
            timing_info["completed_at"] = order.completed_at.isoformat()
        if order.estimated_ready_time:
            timing_info["estimated_ready_time"] = order.estimated_ready_time.isoformat()
        
        return {
            "order_id": order.id,
            "status": order.status.value,
            "payment_status": order.payment_status.value,
            "items": order.items,
            "subtotal": order.subtotal,
            "tax_amount": order.tax_amount,
            "tip_amount": order.tip_amount,
            "total_amount": order.total_amount,
            "customer_name": order.customer_name,
            "table_id": order.table_id,
            "special_instructions": order.special_instructions,
            "timing": timing_info,
            "created_at": order.created_at.isoformat()
        }
    
    def get_active_orders(self, business_id: int) -> List[Order]:
        """
        Get all active orders for a business.
        
        Args:
            business_id: Business ID to get orders for
            
        Returns:
            List of active orders
        """
        active_statuses = [
            OrderStatus.PENDING,
            OrderStatus.CONFIRMED,
            OrderStatus.PREPARING,
            OrderStatus.READY
        ]
        
        return self.db.query(Order).filter(
            Order.business_id == business_id,
            Order.status.in_(active_statuses)
        ).order_by(Order.created_at).all()
    
    def get_orders_by_status(self, business_id: int, status: OrderStatus) -> List[Order]:
        """
        Get orders by status for a business.
        
        Args:
            business_id: Business ID to get orders for
            status: Order status to filter by
            
        Returns:
            List of orders with specified status
        """
        return self.db.query(Order).filter(
            Order.business_id == business_id,
            Order.status == status
        ).order_by(Order.created_at).all()
    
    def _get_order(self, order_id: int, business_id: int) -> Order:
        """
        Helper to get and validate an order.
        
        Args:
            order_id: Order ID to get
            business_id: Business ID for validation
            
        Returns:
            Order object
            
        Raises:
            ValueError: If order not found
        """
        order = self.db.query(Order).filter(
            Order.id == order_id,
            Order.business_id == business_id
        ).first()
        
        if not order:
            raise ValueError(f"Order {order_id} not found for business {business_id}")
        
        return order
    
    def _calculate_item_price(
        self,
        menu_item: MenuItem,
        customizations: Dict[str, Any],
        quantity: int
    ) -> float:
        """Calculate item price with customizations."""
        base_price = menu_item.base_price
        
        # Add customization costs
        for custom_type, selected_option in customizations.items():
            # Find matching customization in menu item
            for custom in menu_item.customizations:
                if custom.get("name") == custom_type:
                    options = custom.get("options", [])
                    price_diffs = custom.get("price_diff", [])
                    
                    if selected_option in options:
                        idx = options.index(selected_option)
                        if idx < len(price_diffs):
                            base_price += price_diffs[idx]
                    break
        
        return round(base_price * quantity, 2)
    
    def update_order_status(
        self,
        order_id: int,
        new_status: OrderStatus,
        estimated_minutes: Optional[int] = None
    ) -> Order:
        """Update order status with validation - Legacy method for backward compatibility."""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            raise ValueError("Order not found")
        
        # Validate status transition
        if not self._is_valid_status_transition(order.status, new_status):
            raise ValueError(f"Invalid status transition from {order.status} to {new_status}")
        
        order.status = new_status
        
        # Set estimated time if provided
        if estimated_minutes:
            order.estimated_ready_time = datetime.utcnow() + timedelta(minutes=estimated_minutes)
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def _is_valid_status_transition(
        self,
        current: OrderStatus,
        new: OrderStatus
    ) -> bool:
        """Check if status transition is valid."""
        # Can always cancel (except completed orders)
        if new == OrderStatus.CANCELLED:
            return current != OrderStatus.COMPLETED
        
        # Define valid transitions
        transitions = {
            OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
            OrderStatus.CONFIRMED: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
            OrderStatus.PREPARING: [OrderStatus.READY, OrderStatus.CANCELLED],
            OrderStatus.READY: [OrderStatus.COMPLETED, OrderStatus.CANCELLED],
            OrderStatus.COMPLETED: [],
            OrderStatus.CANCELLED: []
        }
        
        return new in transitions.get(current, [])