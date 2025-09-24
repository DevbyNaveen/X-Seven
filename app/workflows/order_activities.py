"""
Order Processing Activities for Temporal Workflows
Enhanced activities for comprehensive order management
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def validate_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate order data and business rules"""
    try:
        logger.info(f"Validating order {order_data.get('order_id', 'unknown')}")
        
        # Required fields validation
        required_fields = ["business_id", "user_id", "items"]
        missing_fields = [field for field in required_fields if not order_data.get(field)]
        
        if missing_fields:
            return {
                "valid": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }
        
        # Items validation
        items = order_data.get("items", [])
        if not items:
            return {
                "valid": False,
                "error": "Order must contain at least one item"
            }
        
        # Business hours validation (simplified)
        current_hour = datetime.now().hour
        if current_hour < 8 or current_hour > 22:  # 8 AM to 10 PM
            return {
                "valid": False,
                "error": "Orders can only be placed during business hours (8 AM - 10 PM)"
            }
        
        # Calculate total if not provided
        if "total_amount" not in order_data:
            total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
            order_data["total_amount"] = total
        
        logger.info(f"Order validation successful for {order_data.get('order_id')}")
        return {
            "valid": True,
            "validated_data": order_data,
            "validation_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Order validation error: {e}")
        return {
            "valid": False,
            "error": f"Validation failed: {str(e)}"
        }


@activity.defn
async def process_payment(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process payment for the order"""
    try:
        logger.info(f"Processing payment for order {order_data.get('order_id')}")
        
        payment_method = order_data.get("payment_method", "card")
        total_amount = order_data.get("total_amount", 0)
        
        if total_amount <= 0:
            return {
                "success": False,
                "error": "Invalid order amount"
            }
        
        # Simulate payment processing
        # In real implementation, this would integrate with Stripe, PayPal, etc.
        if payment_method == "card":
            # Simulate card processing
            card_info = order_data.get("card_info", {})
            if not card_info.get("number") or not card_info.get("cvv"):
                return {
                    "success": False,
                    "error": "Invalid card information"
                }
        
        # Simulate processing delay
        import asyncio
        await asyncio.sleep(2)
        
        # Generate transaction ID
        transaction_id = f"txn_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{order_data.get('order_id', 'unknown')}"
        
        logger.info(f"Payment processed successfully: {transaction_id}")
        return {
            "success": True,
            "transaction_id": transaction_id,
            "amount_charged": total_amount,
            "payment_method": payment_method,
            "processed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Payment processing error: {e}")
        return {
            "success": False,
            "error": f"Payment failed: {str(e)}"
        }


@activity.defn
async def prepare_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare order for fulfillment"""
    try:
        logger.info(f"Preparing order {order_data.get('order_id')}")
        
        items = order_data.get("items", [])
        business_id = order_data.get("business_id")
        
        # Simulate preparation time based on items
        preparation_time = len(items) * 5  # 5 minutes per item
        
        # Check inventory (simplified)
        for item in items:
            item_name = item.get("name", "Unknown item")
            quantity = item.get("quantity", 1)
            
            # Simulate inventory check
            if quantity > 10:  # Arbitrary limit
                return {
                    "status": "failed",
                    "error": f"Insufficient inventory for {item_name}"
                }
        
        # Simulate preparation process
        import asyncio
        await asyncio.sleep(min(preparation_time, 30))  # Cap at 30 seconds for demo
        
        estimated_ready_time = datetime.now() + timedelta(minutes=preparation_time)
        
        logger.info(f"Order preparation completed for {order_data.get('order_id')}")
        return {
            "status": "prepared",
            "preparation_time_minutes": preparation_time,
            "estimated_ready_time": estimated_ready_time.isoformat(),
            "prepared_at": datetime.now().isoformat(),
            "prepared_items": [item.get("name") for item in items]
        }
        
    except Exception as e:
        logger.error(f"Order preparation error: {e}")
        return {
            "status": "failed",
            "error": f"Preparation failed: {str(e)}"
        }


@activity.defn
async def schedule_delivery(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule delivery for the order"""
    try:
        logger.info(f"Scheduling delivery for order {order_data.get('order_id')}")
        
        delivery_address = order_data.get("delivery_address")
        if not delivery_address:
            return {
                "status": "failed",
                "error": "Delivery address is required"
            }
        
        # Calculate delivery time (simplified)
        base_delivery_time = 30  # 30 minutes base
        distance_factor = 1.5  # Assume 1.5x for distance
        
        estimated_delivery_minutes = int(base_delivery_time * distance_factor)
        estimated_delivery_time = datetime.now() + timedelta(minutes=estimated_delivery_minutes)
        
        # Generate delivery tracking ID
        tracking_id = f"del_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{order_data.get('order_id', 'unknown')}"
        
        # Simulate delivery assignment
        delivery_partner = "QuickDelivery"  # Would be determined by location/availability
        
        logger.info(f"Delivery scheduled for {order_data.get('order_id')}: {tracking_id}")
        return {
            "status": "scheduled",
            "tracking_id": tracking_id,
            "estimated_time": estimated_delivery_time.isoformat(),
            "delivery_partner": delivery_partner,
            "delivery_address": delivery_address,
            "scheduled_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Delivery scheduling error: {e}")
        return {
            "status": "failed",
            "error": f"Delivery scheduling failed: {str(e)}"
        }


@activity.defn
async def send_order_updates(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send order status updates to customer"""
    try:
        logger.info(f"Sending order updates for {order_data.get('order_id')}")
        
        user_id = order_data.get("user_id")
        order_id = order_data.get("order_id")
        
        # Prepare update messages
        updates = [
            {
                "type": "order_confirmed",
                "message": f"Your order #{order_id} has been confirmed and is being prepared.",
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        if order_data.get("delivery_required"):
            updates.append({
                "type": "preparation_started",
                "message": f"Your order #{order_id} is now being prepared. We'll notify you when it's ready for delivery.",
                "timestamp": (datetime.now() + timedelta(minutes=5)).isoformat()
            })
            
            updates.append({
                "type": "out_for_delivery",
                "message": f"Your order #{order_id} is out for delivery! Track your order with the link we sent.",
                "timestamp": (datetime.now() + timedelta(minutes=25)).isoformat()
            })
        else:
            updates.append({
                "type": "ready_for_pickup",
                "message": f"Your order #{order_id} is ready for pickup! Please come to the store.",
                "timestamp": (datetime.now() + timedelta(minutes=15)).isoformat()
            })
        
        # In a real implementation, these would be scheduled as separate activities
        # or sent to a notification service
        
        logger.info(f"Order updates scheduled for {order_id}")
        return {
            "status": "scheduled",
            "updates_count": len(updates),
            "updates": updates,
            "scheduled_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Order updates error: {e}")
        return {
            "status": "failed",
            "error": f"Failed to schedule updates: {str(e)}"
        }


@activity.defn
async def handle_order_cancellation(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle order cancellation"""
    try:
        logger.info(f"Processing cancellation for order {order_data.get('order_id')}")
        
        order_id = order_data.get("order_id")
        cancellation_reason = order_data.get("cancellation_reason", "Customer request")
        
        # Check if order can be cancelled
        order_status = order_data.get("status", "pending")
        if order_status in ["delivered", "completed"]:
            return {
                "success": False,
                "error": "Order cannot be cancelled as it has already been completed"
            }
        
        # Process refund if payment was made
        refund_amount = 0
        if order_data.get("payment_processed"):
            refund_amount = order_data.get("total_amount", 0)
            # Simulate refund processing
            import asyncio
            await asyncio.sleep(1)
        
        logger.info(f"Order {order_id} cancelled successfully")
        return {
            "success": True,
            "order_id": order_id,
            "cancellation_reason": cancellation_reason,
            "refund_amount": refund_amount,
            "cancelled_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Order cancellation error: {e}")
        return {
            "success": False,
            "error": f"Cancellation failed: {str(e)}"
        }


@activity.defn
async def update_inventory(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update inventory after order processing"""
    try:
        logger.info(f"Updating inventory for order {order_data.get('order_id')}")
        
        business_id = order_data.get("business_id")
        items = order_data.get("items", [])
        
        inventory_updates = []
        
        for item in items:
            item_id = item.get("id")
            quantity_ordered = item.get("quantity", 1)
            
            # Simulate inventory update
            inventory_updates.append({
                "item_id": item_id,
                "quantity_reduced": quantity_ordered,
                "updated_at": datetime.now().isoformat()
            })
        
        logger.info(f"Inventory updated for {len(items)} items")
        return {
            "success": True,
            "business_id": business_id,
            "updates": inventory_updates,
            "updated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Inventory update error: {e}")
        return {
            "success": False,
            "error": f"Inventory update failed: {str(e)}"
        }
