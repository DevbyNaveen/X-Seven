# app/services/ai/dashboard_actions/order_manager.py
"""
Order Management for Dashboard AI
Handles natural language requests for orders
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.models import Order, OrderStatus
import logging

logger = logging.getLogger(__name__)

class OrderManager:
    def __init__(self, db: Session):
        self.db = db

    async def handle_order_request(self, business_id: int, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle all order-related requests based on AI intent"""
        action = intent.get("action", "")
        
        try:
            if action == "list_orders":
                status = intent.get("status")
                return await self.list_orders(business_id, status)
            elif action == "view_order":
                return await self.view_order(business_id, intent.get("order_id"))
            elif action == "update_order_status":
                return await self.update_order_status(
                    business_id,
                    intent.get("order_id"),
                    intent.get("status")
                )
            elif action == "cancel_order":
                return await self.cancel_order(business_id, intent.get("order_id"))
            else:
                return {"success": False, "message": "I don't understand that order action."}
        except Exception as e:
            logger.error(f"Error handling order request: {str(e)}")
            return {"success": False, "message": f"Error processing order request: {str(e)}"}

    async def list_orders(self, business_id: int, status: Optional[str] = None) -> Dict[str, Any]:
        """List orders, optionally filtered by status"""
        try:
            query = self.db.query(Order).filter(Order.business_id == business_id)
            
            if status:
                # Map friendly status names to enum values
                status_map = {
                    "pending": OrderStatus.PENDING,
                    "preparing": OrderStatus.PREPARING,
                    "ready": OrderStatus.READY,
                    "completed": OrderStatus.COMPLETED,
                    "cancelled": OrderStatus.CANCELLED
                }
                
                if status.lower() in status_map:
                    query = query.filter(Order.status == status_map[status.lower()])
                else:
                    return {"success": False, "message": f"Unknown status: {status}"}
            
            # Get recent orders (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            orders = query.filter(Order.created_at >= week_ago)\
                         .order_by(Order.created_at.desc())\
                         .limit(20).all()
            
            if not orders:
                if status:
                    return {
                        "success": True,
                        "message": f"You don't have any {status} orders right now.",
                        "orders": []
                    }
                else:
                    return {
                        "success": True,
                        "message": "You don't have any recent orders.",
                        "orders": []
                    }
            
            order_list = []
            response_text = f"I found {len(orders)} recent orders"
            if status:
                response_text += f" with status '{status}'"
            response_text += ":\n\n"
            
            for order in orders:
                # Get order items from JSON field
                items_json = order.items or []
                # Build a concise items summary (first 3 items)
                parts = []
                for it in items_json[:3]:
                    qty = it.get("quantity", 1)
                    name = it.get("name") or f"Item #{it.get('item_id', '?')}"
                    parts.append(f"{qty}x {name}")
                item_summary = ", ".join(parts)
                if len(items_json) > 3:
                    item_summary += f" and {len(items_json) - 3} more"
                
                order_list.append({
                    "id": order.id,
                    "order_number": order.id,  # Using ID as order number
                    "status": order.status.value if order.status else "unknown",
                    "total_amount": float(order.total_amount or 0),
                    "customer_name": order.customer_name or "Anonymous",
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "items_summary": item_summary
                })
                
                response_text += f"**Order #{order.id}** - {order.status.value if order.status else 'Unknown'}\n"
                response_text += f"Customer: {order.customer_name or 'Anonymous'}\n"
                response_text += f"Total: ${float(order.total_amount or 0):.2f}\n"
                response_text += f"Items: {item_summary}\n"
                response_text += f"Placed: {order.created_at.strftime('%m/%d %H:%M') if order.created_at else 'Unknown'}\n\n"
            
            return {
                "success": True,
                "message": response_text,
                "orders": order_list
            }
        except Exception as e:
            return {"success": False, "message": f"Error listing orders: {str(e)}"}

    async def view_order(self, business_id: int, order_id: Optional[int]) -> Dict[str, Any]:
        """View details of a specific order"""
        try:
            if not order_id:
                return {"success": False, "message": "Please specify which order you'd like to view."}
            
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.business_id == business_id
            ).first()
            
            if not order:
                return {"success": False, "message": f"I couldn't find order #{order_id}."}
            
            # Get order items from JSON field
            order_items = order.items or []
            
            response_text = f"**Order Details - #{order.id}**\n"
            response_text += f"Status: **{order.status.value if order.status else 'Unknown'}**\n"
            response_text += f"Customer: {order.customer_name or 'Anonymous'}\n"
            response_text += f"Phone: {order.customer_phone or 'Not provided'}\n"
            response_text += f"Email: {order.customer_email or 'Not provided'}\n"
            response_text += f"Total: **${float(order.total_amount or 0):.2f}**\n"
            response_text += f"Placed: {order.created_at.strftime('%Y-%m-%d %H:%M') if order.created_at else 'Unknown'}\n\n"
            
            response_text += "**Items:**\n"
            for it in order_items:
                qty = it.get("quantity", 1)
                name = it.get("name") or f"Item #{it.get('item_id', '?')}"
                unit_price = float(it.get("unit_price") or it.get("price") or 0)
                response_text += f"• {qty}x {name} - ${unit_price * qty:.2f}\n"
            
            if order.special_instructions:
                response_text += f"\n**Special Instructions:**\n{order.special_instructions}\n"
            
            return {
                "success": True,
                "message": response_text,
                "order": {
                    "id": order.id,
                    "order_number": order.id,
                    "status": order.status.value if order.status else "unknown",
                    "customer_name": order.customer_name,
                    "customer_phone": order.customer_phone,
                    "customer_email": order.customer_email,
                    "total_amount": float(order.total_amount or 0),
                    "special_instructions": order.special_instructions,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "items": [{
                        "name": it.get("name") or f"Item #{it.get('item_id', '?')}",
                        "quantity": it.get("quantity", 1),
                        "price": float(it.get("unit_price") or it.get("price") or 0)
                    } for it in order_items]
                }
            }
        except Exception as e:
            return {"success": False, "message": f"Error viewing order: {str(e)}"}

    async def update_order_status(self, business_id: int, order_id: Optional[int], 
                                status: str) -> Dict[str, Any]:
        """Update the status of an order"""
        try:
            if not order_id:
                return {"success": False, "message": "Please specify which order to update."}
            
            if not status:
                return {"success": False, "message": "Please specify the new status."}
            
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.business_id == business_id
            ).first()
            
            if not order:
                return {"success": False, "message": f"I couldn't find order #{order_id}."}
            
            # Map friendly status names to enum values
            status_map = {
                "pending": OrderStatus.PENDING,
                "preparing": OrderStatus.PREPARING,
                "ready": OrderStatus.READY,
                "completed": OrderStatus.COMPLETED,
                "cancelled": OrderStatus.CANCELLED
            }
            
            if status.lower() not in status_map:
                return {"success": False, "message": f"Unknown status: {status}"}
            
            new_status = status_map[status.lower()]
            old_status = order.status
            
            if old_status == new_status:
                return {
                    "success": True,
                    "message": f"Order #{order.id} is already marked as {status}."
                }
            
            order.status = new_status
            self.db.commit()
            
            status_labels = {
                OrderStatus.PENDING: "Pending",
                OrderStatus.PREPARING: "Preparing",
                OrderStatus.READY: "Ready",
                OrderStatus.COMPLETED: "Completed",
                OrderStatus.CANCELLED: "Cancelled"
            }
            
            return {
                "success": True,
                "message": f"✅ I've updated order #{order.id} from '{status_labels.get(old_status, 'Unknown')}' "
                          f"to '**{status_labels.get(new_status, status)}**'."
            }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to update order status: {str(e)}"}

    async def cancel_order(self, business_id: int, order_id: Optional[int]) -> Dict[str, Any]:
        """Cancel an order"""
        try:
            if not order_id:
                return {"success": False, "message": "Please specify which order to cancel."}
            
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.business_id == business_id
            ).first()
            
            if not order:
                return {"success": False, "message": f"I couldn't find order #{order_id}."}
            
            if order.status == OrderStatus.CANCELLED:
                return {
                    "success": True,
                    "message": f"Order #{order.id} is already cancelled."
                }
            
            if order.status == OrderStatus.COMPLETED:
                return {
                    "success": False,
                    "message": f"Order #{order.id} is already completed and cannot be cancelled."
                }
            
            old_status = order.status
            order.status = OrderStatus.CANCELLED
            self.db.commit()
            
            status_labels = {
                OrderStatus.PENDING: "Pending",
                OrderStatus.PREPARING: "Preparing",
                OrderStatus.READY: "Ready",
                OrderStatus.COMPLETED: "Completed",
                OrderStatus.CANCELLED: "Cancelled"
            }
            
            return {
                "success": True,
                "message": f"✅ I've cancelled order #{order.id} (previously '{status_labels.get(old_status, 'Unknown')}')."
            }
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": f"Failed to cancel order: {str(e)}"}