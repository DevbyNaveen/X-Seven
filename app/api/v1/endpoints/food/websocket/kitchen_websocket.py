"""Kitchen WebSocket endpoints for real-time food preparation updates."""
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business, Order
from app.services.websocket.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/kitchen/ws/{business_id}")
async def kitchen_websocket(
    websocket: WebSocket,
    business_id: int,
    db: Session = Depends(get_db)
):
    """
    Kitchen-specific WebSocket connection.
    
    Order queue changes, preparation time updates, staff notifications.
    """
    # Verify business exists
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        await websocket.close(code=4004, reason="Business not found")
        return
    
    # Accept the WebSocket connection
    await manager.connect(websocket, f"kitchen_{business_id}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
            elif message.get("type") == "kitchen_action":
                # Process kitchen actions and broadcast to relevant clients
                await handle_kitchen_action(message, business_id, db)
            elif message.get("type") == "staff_notification":
                # Process staff notifications
                await handle_staff_notification(message, business_id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"Kitchen WebSocket disconnected for business {business_id}")
    except Exception as e:
        logger.error(f"Kitchen WebSocket error for business {business_id}: {str(e)}")
        manager.disconnect(websocket)

async def handle_kitchen_action(message: Dict[str, Any], business_id: int, db: Session):
    """Handle kitchen actions and broadcast updates."""
    action = message.get("action")
    
    if action == "order_queue_update":
        # Update order queue
        order_id = message.get("order_id")
        new_status = message.get("status")
        
        order = db.query(Order).filter(Order.id == order_id, Order.business_id == business_id).first()
        if order:
            order.status = new_status
            db.commit()
            
            # Broadcast order queue update
            await manager.broadcast({
                "type": "order_queue_update",
                "order_id": order_id,
                "status": new_status,
                "timestamp": message.get("timestamp")
            }, f"kitchen_{business_id}")
    
    elif action == "preparation_time_update":
        # Update preparation time
        order_id = message.get("order_id")
        prep_time = message.get("prep_time")
        
        order = db.query(Order).filter(Order.id == order_id, Order.business_id == business_id).first()
        if order:
            # In a real implementation, you might store this in a separate field
            # For now, we'll just broadcast the update
            await manager.broadcast({
                "type": "preparation_time_update",
                "order_id": order_id,
                "prep_time": prep_time,
                "timestamp": message.get("timestamp")
            }, f"kitchen_{business_id}")

async def handle_staff_notification(message: Dict[str, Any], business_id: int):
    """Handle staff notifications."""
    notification_type = message.get("notification_type")
    content = message.get("content")
    
    # Broadcast staff notification
    await manager.broadcast({
        "type": "staff_notification",
        "notification_type": notification_type,
        "content": content,
        "timestamp": message.get("timestamp")
    }, f"kitchen_{business_id}")

# Additional helper functions for kitchen updates
async def send_order_to_kitchen(order_id: int, business_id: int, order_details: Dict[str, Any]):
    """Send new order to kitchen display."""
    await manager.broadcast({
        "type": "new_order",
        "order_id": order_id,
        "order_details": order_details
    }, f"kitchen_{business_id}")

async def send_preparation_update(order_id: int, business_id: int, status: str, message: str):
    """Send preparation status update."""
    await manager.broadcast({
        "type": "preparation_update",
        "order_id": order_id,
        "status": status,
        "message": message
    }, f"kitchen_{business_id}")
