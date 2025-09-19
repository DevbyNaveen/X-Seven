"""Food order management endpoints for AI integration."""
from typing import Any, List, Optional, Dict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

from app.config.database import get_supabase_client
from app.core.dependencies import get_current_business, get_current_user
from app.models import OrderStatus, Business, User, PaymentStatus, PaymentMethod
from app.services.websocket.connection_manager import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class OrderItem(BaseModel):
    """Order item schema."""
    menu_item_id: int
    name: str
    quantity: int = Field(gt=0, le=99)
    price: Decimal = Field(ge=0, decimal_places=2)
    special_instructions: Optional[str] = Field(None, max_length=500)


class OrderCreate(BaseModel):
    """Create new order."""
    table_id: Optional[int] = Field(None, description="Table ID for dine-in orders")
    customer_name: Optional[str] = Field(None, max_length=100)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_email: Optional[str] = Field(None, max_length=100)
    order_type: str = Field(default="dine-in", pattern="^(dine-in|takeout|delivery)$")
    items: List[OrderItem] = Field(min_items=1)
    special_instructions: Optional[str] = Field(None, max_length=500)
    payment_method: PaymentMethod = Field(default=PaymentMethod.CASH)

    @field_validator('items')
    @classmethod
    def validate_items(cls, v):
        if not v:
            raise ValueError('Order must contain at least one item')
        return v


class OrderUpdate(BaseModel):
    """Update order."""
    status: Optional[OrderStatus] = None
    payment_status: Optional[PaymentStatus] = None
    special_instructions: Optional[str] = Field(None, max_length=500)
    items: Optional[List[OrderItem]] = None


class OrderResponse(BaseModel):
    """Order response."""
    id: int
    business_id: int
    table_id: Optional[int]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    order_type: str
    items: List[Dict[str, Any]]
    subtotal: Decimal
    tax_amount: Decimal
    tip_amount: Decimal
    total_amount: Decimal
    status: OrderStatus
    payment_status: PaymentStatus
    payment_method: PaymentMethod
    special_instructions: Optional[str]
    created_at: datetime
    updated_at: datetime


@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    background_tasks: BackgroundTasks,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Create a new food order.
    """
    try:
        # Calculate totals
        subtotal = sum(item.quantity * item.price for item in order_data.items)
        tax_rate = Decimal('0.08')  # 8% tax
        tax_amount = subtotal * tax_rate
        tip_amount = Decimal('0.00')  # Default no tip
        total_amount = subtotal + tax_amount + tip_amount

        # Prepare order data
        order_dict = {
            'business_id': business.id,
            'table_id': order_data.table_id,
            'customer_name': order_data.customer_name,
            'customer_phone': order_data.customer_phone,
            'customer_email': order_data.customer_email,
            'order_type': order_data.order_type,
            'items': [item.dict() for item in order_data.items],
            'subtotal': float(subtotal),
            'tax_amount': float(tax_amount),
            'tip_amount': float(tip_amount),
            'total_amount': float(total_amount),
            'status': 'pending',
            'payment_status': 'pending',
            'payment_method': order_data.payment_method.value,
            'special_instructions': order_data.special_instructions,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        # Create order in database
        response = supabase.table('orders').insert(order_dict).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order"
            )

        order = response.data[0]

        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "new_order",
                "order_id": order['id'],
                "table_id": order_data.table_id,
                "order_type": order_data.order_type,
                "total_amount": float(total_amount),
                "customer_name": order_data.customer_name
            }
        )

        # Add background task for order processing
        background_tasks.add_task(process_new_order, order['id'], business.id, supabase)

        return order

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )


@router.get("/", response_model=List[OrderResponse])
async def get_orders(
    status: Optional[OrderStatus] = Query(None, description="Filter by order status"),
    order_type: Optional[str] = Query(None, description="Filter by order type"),
    table_id: Optional[int] = Query(None, description="Filter by table ID"),
    limit: int = Query(50, ge=1, le=100, description="Number of orders to return"),
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Get orders with optional filtering.
    """
    try:
        query = supabase.table('orders').select('*').eq('business_id', business.id)

        # Apply filters
        if status:
            query = query.eq('status', status.value)
        if order_type:
            query = query.eq('order_type', order_type)
        if table_id:
            query = query.eq('table_id', table_id)

        # Order by creation date (newest first)
        response = query.order('created_at', desc=True).limit(limit).execute()

        return response.data if response.data else []

    except Exception as e:
        logger.error(f"Error retrieving orders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve orders: {str(e)}"
        )


@router.get("/active", response_model=List[OrderResponse])
async def get_active_orders(
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Get all active orders (pending, confirmed, preparing, ready).
    """
    try:
        active_statuses = ['pending', 'confirmed', 'preparing', 'ready']

        response = supabase.table('orders').select('*').eq('business_id', business.id).in_('status', active_statuses).order('created_at', desc=True).execute()

        return response.data if response.data else []

    except Exception as e:
        logger.error(f"Error retrieving active orders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve active orders: {str(e)}"
        )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Get a specific order by ID.
    """
    try:
        response = supabase.table('orders').select('*').eq('id', order_id).eq('business_id', business.id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving order {order_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order: {str(e)}"
        )


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    order_update: OrderUpdate,
    background_tasks: BackgroundTasks,
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Update an order.
    """
    try:
        # Get current order
        response = supabase.table('orders').select('*').eq('id', order_id).eq('business_id', business.id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        current_order = response.data[0]
        old_status = current_order['status']

        # Prepare update data
        update_data = {'updated_at': datetime.utcnow().isoformat()}

        if order_update.status:
            update_data['status'] = order_update.status.value
        if order_update.payment_status:
            update_data['payment_status'] = order_update.payment_status.value
        if order_update.special_instructions is not None:
            update_data['special_instructions'] = order_update.special_instructions
        if order_update.items:
            # Recalculate totals if items changed
            subtotal = sum(item.quantity * item.price for item in order_update.items)
            tax_rate = Decimal('0.08')
            tax_amount = subtotal * tax_rate
            tip_amount = Decimal(str(current_order.get('tip_amount', 0)))
            total_amount = subtotal + tax_amount + tip_amount

            update_data.update({
                'items': [item.dict() for item in order_update.items],
                'subtotal': float(subtotal),
                'tax_amount': float(tax_amount),
                'total_amount': float(total_amount)
            })

        # Update order
        update_response = supabase.table('orders').update(update_data).eq('id', order_id).eq('business_id', business.id).execute()

        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update order"
            )

        updated_order = update_response.data[0]

        # Send WebSocket notification if status changed
        if order_update.status and order_update.status.value != old_status:
            await manager.broadcast_to_business(
                business_id=business.id,
                message={
                    "type": "order_status_update",
                    "order_id": order_id,
                    "old_status": old_status,
                    "new_status": order_update.status.value,
                    "table_id": current_order.get('table_id')
                }
            )

        # Add background task for order processing if status changed
        if order_update.status:
            background_tasks.add_task(process_order_status_change, order_id, order_update.status.value, business.id, supabase)

        return updated_order

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order {order_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update order: {str(e)}"
        )


@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    reason: Optional[str] = Query(None, max_length=500, description="Cancellation reason"),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Cancel an order.
    """
    try:
        # Get current order
        response = supabase.table('orders').select('*').eq('id', order_id).eq('business_id', business.id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        current_order = response.data[0]

        # Check if order can be cancelled
        if current_order['status'] in ['completed', 'cancelled']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel order with status: {current_order['status']}"
            )

        # Update order status to cancelled
        update_data = {
            'status': 'cancelled',
            'updated_at': datetime.utcnow().isoformat(),
            'cancellation_reason': reason,
            'cancelled_by': current_user.id,
            'cancelled_at': datetime.utcnow().isoformat()
        }

        update_response = supabase.table('orders').update(update_data).eq('id', order_id).eq('business_id', business.id).execute()

        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel order"
            )

        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "order_cancelled",
                "order_id": order_id,
                "table_id": current_order.get('table_id'),
                "reason": reason
            }
        )

        return {"message": f"Order {order_id} cancelled successfully", "order_id": order_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )


@router.put("/{order_id}/payment", response_model=OrderResponse)
async def process_payment(
    order_id: int,
    payment_amount: Decimal = Query(..., gt=0, description="Payment amount"),
    payment_method: PaymentMethod = Query(..., description="Payment method"),
    business: Business = Depends(get_current_business),
    current_user: User = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Process payment for an order.
    """
    try:
        # Get current order
        response = supabase.table('orders').select('*').eq('id', order_id).eq('business_id', business.id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        current_order = response.data[0]

        # Check if order is already paid
        if current_order['payment_status'] == 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already paid"
            )

        # Validate payment amount
        order_total = Decimal(str(current_order['total_amount']))
        if payment_amount != order_total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment amount {payment_amount} does not match order total {order_total}"
            )

        # Update payment status
        update_data = {
            'payment_status': 'completed',
            'payment_method': payment_method.value,
            'paid_amount': float(payment_amount),
            'paid_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        update_response = supabase.table('orders').update(update_data).eq('id', order_id).eq('business_id', business.id).execute()

        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process payment"
            )

        updated_order = update_response.data[0]

        # Send WebSocket notification
        await manager.broadcast_to_business(
            business_id=business.id,
            message={
                "type": "payment_completed",
                "order_id": order_id,
                "amount": float(payment_amount),
                "payment_method": payment_method.value,
                "table_id": current_order.get('table_id')
            }
        )

        return updated_order

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing payment for order {order_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process payment: {str(e)}"
        )


@router.get("/stats/summary")
async def get_order_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    business: Business = Depends(get_current_business),
    supabase = Depends(get_supabase_client)
) -> Any:
    """
    Get order statistics summary.
    """
    try:
        # Calculate date range
        start_date = datetime.now() - timedelta(days=days)

        # Get orders for the period
        response = supabase.table('orders').select('*').eq('business_id', business.id).gte('created_at', start_date.isoformat()).execute()

        orders = response.data if response.data else []

        # Calculate statistics
        total_orders = len(orders)
        completed_orders = len([o for o in orders if o['status'] == 'completed'])
        total_revenue = sum(o['total_amount'] for o in orders if o['status'] == 'completed')
        avg_order_value = total_revenue / completed_orders if completed_orders > 0 else 0

        # Order status breakdown
        status_counts = {}
        for order in orders:
            status_counts[order['status']] = status_counts.get(order['status'], 0) + 1

        # Daily order counts
        daily_orders = {}
        for order in orders:
            date_key = order['created_at'][:10]  # YYYY-MM-DD
            daily_orders[date_key] = daily_orders.get(date_key, 0) + 1

        return {
            "period_days": days,
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "completion_rate": round(completed_orders / total_orders * 100, 2) if total_orders > 0 else 0,
            "total_revenue": round(total_revenue, 2),
            "average_order_value": round(avg_order_value, 2),
            "status_breakdown": status_counts,
            "daily_order_counts": daily_orders
        }

    except Exception as e:
        logger.error(f"Error retrieving order stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order statistics: {str(e)}"
        )


# Background task functions
async def process_new_order(order_id: int, business_id: int, supabase):
    """Process a new order (send notifications, update inventory, etc.)"""
    try:
        logger.info(f"Processing new order {order_id} for business {business_id}")
        # Add order processing logic here
        # - Send notifications to kitchen staff
        # - Update inventory levels
        # - Trigger automated workflows
    except Exception as e:
        logger.error(f"Error processing new order {order_id}: {str(e)}")


async def process_order_status_change(order_id: int, new_status: str, business_id: int, supabase):
    """Process order status changes"""
    try:
        logger.info(f"Processing status change for order {order_id} to {new_status}")
        # Add status change processing logic here
        # - Send notifications to relevant staff
        # - Update kitchen display systems
        # - Trigger delivery notifications
    except Exception as e:
        logger.error(f"Error processing status change for order {order_id}: {str(e)}")
