"""Dashboard WebSocket endpoints for real-time food service updates."""
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.core.dependencies import get_current_business
from app.models import Business, Order, Table
from app.services.websocket.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/dashboard/ws/{business_id}")
async def dashboard_websocket(
    websocket: WebSocket,
    business_id: int,
    db: Session = Depends(get_db)
):
    """
    Real-time dashboard WebSocket connection.
    
    Pushes live order notifications, table status changes, inventory alerts.
    Bidirectional communication for AI chat and dashboard actions.
    """
    # Verify business exists
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        await websocket.close(code=4004, reason="Business not found")
        return
    
    # Accept the WebSocket connection
    await manager.connect(websocket, f"dashboard_{business_id}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
            elif message.get("type") == "dashboard_action":
                # Process dashboard actions and broadcast to relevant clients
                await handle_dashboard_action(message, business_id, db)
            elif message.get("type") == "ai_chat":
                # Process AI chat messages
                response = await process_ai_chat_message(message, business_id)
                await manager.send_personal_message(response, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"Dashboard WebSocket disconnected for business {business_id}")
    except Exception as e:
        logger.error(f"Dashboard WebSocket error for business {business_id}: {str(e)}")
        manager.disconnect(websocket)

async def handle_dashboard_action(message: Dict[str, Any], business_id: int, db: Session):
    """Handle dashboard actions and broadcast updates."""
    action = message.get("action")
    
    if action == "order_status_update":
        # Update order status
        order_id = message.get("order_id")
        new_status = message.get("status")
        
        order = db.query(Order).filter(Order.id == order_id, Order.business_id == business_id).first()
        if order:
            order.status = new_status
            db.commit()
            
            # Broadcast order update
            await manager.broadcast({
                "type": "order_update",
                "order_id": order_id,
                "status": new_status,
                "timestamp": message.get("timestamp")
            }, f"dashboard_{business_id}")
    
    elif action == "table_status_update":
        # Update table status
        table_id = message.get("table_id")
        new_status = message.get("status")
        
        table = db.query(Table).filter(Table.id == table_id, Table.business_id == business_id).first()
        if table:
            table.status = new_status
            db.commit()
            
            # Broadcast table update
            await manager.broadcast({
                "type": "table_update",
                "table_id": table_id,
                "status": new_status,
                "timestamp": message.get("timestamp")
            }, f"dashboard_{business_id}")

async def process_ai_chat_message(message: Dict[str, Any], business_id: int) -> Dict[str, Any]:
    """Process AI chat messages and generate responses."""
    user_message = message.get("message", "")
    
    # This would integrate with an AI service in a real implementation
    # For now, we'll simulate a response
    ai_response = f"I received your message about business {business_id}: {user_message}"
    
    return {
        "type": "ai_chat_response",
        "message": ai_response,
        "timestamp": message.get("timestamp")
    }

# Additional helper functions for dashboard updates
async def send_order_notification(order_id: int, business_id: int, message: str):
    """Send order notification to dashboard."""
    await manager.broadcast({
        "type": "order_notification",
        "order_id": order_id,
        "message": message
    }, f"dashboard_{business_id}")

async def send_inventory_alert(item_id: int, business_id: int, alert_type: str, message: str):
    """Send inventory alert to dashboard."""
    await manager.broadcast({
        "type": "inventory_alert",
        "item_id": item_id,
        "alert_type": alert_type,
        "message": message
    }, f"dashboard_{business_id}")
