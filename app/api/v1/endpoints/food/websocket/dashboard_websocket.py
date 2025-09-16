"""Dashboard WebSocket endpoints for real-time food service updates."""
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db as get_supabase_client
from app.core.supabase_auth import verify_supabase_token
from app.models import Business, Order, Table
from app.services.websocket.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/dashboard/ws/{business_id}")
async def dashboard_websocket(
    websocket: WebSocket,
    business_id: int
):
    """
    Real-time dashboard WebSocket connection.
    
    Pushes live order notifications, table status changes, inventory alerts.
    Bidirectional communication for AI chat and dashboard actions.
    
    Requires JWT token authentication via query parameter "token".
    """
    # Get token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4003, reason="Authentication token required")
        return
    
    # Verify JWT token
    try:
        payload = await verify_supabase_token(token)
        if not payload:
            await websocket.close(code=4003, reason="Invalid authentication token")
            return
            
        # Extract business_id from token payload with multiple possible locations
        token_business_id = None
        
        # Check for business_id in different possible locations in the token
        if "business_id" in payload:
            token_business_id = payload.get("business_id")
        elif "app_metadata" in payload and isinstance(payload.get("app_metadata"), dict):
            # Check app_metadata for business_id
            app_metadata = payload.get("app_metadata", {})
            token_business_id = app_metadata.get("business_id")
        elif "user_metadata" in payload and isinstance(payload.get("user_metadata"), dict):
            # Check user_metadata for business_id
            user_metadata = payload.get("user_metadata", {})
            token_business_id = user_metadata.get("business_id")
        
        if not token_business_id:
            await websocket.close(code=4003, reason="Token does not contain business context")
            return
            
        # Ensure the user is accessing their own business
        try:
            token_business_id_int = int(token_business_id)
            if token_business_id_int != business_id:
                await websocket.close(code=4003, reason="Unauthorized access to business")
                return
        except (ValueError, TypeError):
            await websocket.close(code=4003, reason="Invalid business_id format in token")
            return
            
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        await websocket.close(code=4003, reason="Token validation failed")
        return
    
    # Get Supabase client for database operations
    supabase = get_supabase_client()
    if not supabase:
        await websocket.close(code=5001, reason="Database connection failed")
        return
    
    try:
        # Verify business exists using Supabase
        business_response = supabase.table('businesses').select('*').eq('id', business_id).execute()
        if not business_response.data:
            await websocket.close(code=4004, reason="Business not found")
            return
        
        business = business_response.data[0]
        
        # Accept the WebSocket connection
        session_id = f"dashboard_{business_id}"
        await manager.connect(websocket, session_id)
        manager.add_to_business(session_id, business_id)
    
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message.get("type") == "dashboard_action":
                    # Process dashboard actions and broadcast to relevant clients
                    await handle_dashboard_action(message, business_id, supabase)
                elif message.get("type") == "ai_chat":
                    # Process AI chat messages
                    response = await process_ai_chat_message(message, business_id, supabase)
                    await websocket.send_json(response)
                
        except WebSocketDisconnect:
            manager.disconnect(session_id)
            logger.info(f"Dashboard WebSocket disconnected for business {business_id}")
        except Exception as e:
            logger.error(f"Dashboard WebSocket error for business {business_id}: {str(e)}")
            manager.disconnect(session_id)
    finally:
        pass

async def handle_dashboard_action(message: Dict[str, Any], business_id: int, supabase):
    """Handle dashboard actions and broadcast updates."""
    action = message.get("action")
    
    if action == "order_status_update":
        # Update order status
        order_id = message.get("order_id")
        new_status = message.get("status")
        
        # Update order status using Supabase
        order_response = supabase.table('orders').update({'status': new_status}).eq('id', order_id).eq('business_id', business_id).execute()
        if order_response.data:
            # Broadcast order update
            await manager.broadcast_to_business(business_id, {
                "type": "order_update",
                "order_id": order_id,
                "status": new_status,
                "timestamp": message.get("timestamp")
            })
    
    elif action == "table_status_update":
        # Update table status
        table_id = message.get("table_id")
        new_status = message.get("status")
        
        # Update table status using Supabase
        table_response = supabase.table('tables').update({'status': new_status}).eq('id', table_id).eq('business_id', business_id).execute()
        if table_response.data:
            # Broadcast table update
            await manager.broadcast_to_business(business_id, {
                "type": "table_update",
                "table_id": table_id,
                "status": new_status,
                "timestamp": message.get("timestamp")
            })

async def process_ai_chat_message(message: Dict[str, Any], business_id: int, supabase) -> Dict[str, Any]:
    """Process AI chat messages and generate responses using Dashboard AI Handler."""
    from app.services.ai.dashboardAI.dashboard_ai_handler import DashboardAIHandler
    
    user_message = message.get("message", "")
    session_id = message.get("session_id", "dashboard_default")
    
    try:
        # Initialize dashboard AI handler with the provided session
        dashboard_handler = DashboardAIHandler(supabase)
        
        # Get recent orders for context
        recent_orders_response = supabase.table('orders').select('*').eq('business_id', business_id).order('created_at', desc=True).limit(5).execute()
        recent_orders = recent_orders_response.data if recent_orders_response.data else []
        
        # Get table status
        tables_response = supabase.table('tables').select('*').eq('business_id', business_id).execute()
        tables = tables_response.data if tables_response.data else []
        
        # Process the message through the AI handler
        result = await dashboard_handler.handle_dashboard_request(
            message=user_message,
            session_id=session_id,
            business_id=business_id,
            recent_orders=recent_orders,
            tables=tables
        )
        
        return {
            "type": "ai_chat_response",
            "message": result.get("message", "I'm having trouble processing your request."),
            "success": result.get("success", True),
            "timestamp": message.get("timestamp")
        }
    except Exception as e:
        logger.error(f"Error processing AI chat message: {str(e)}")
        return {
            "type": "ai_chat_response",
            "message": "I'm having trouble processing your request. Please try again.",
            "success": False,
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
