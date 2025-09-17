"""
Context builders for different chat contexts
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from app.config.settings import settings
from app.core.ai.types import RichContext, ChatContext

logger = logging.getLogger(__name__)


async def build_global_context(context: RichContext) -> RichContext:
    """Build context for global business discovery"""
    try:
        logger.info("Starting to build global context...")
        
        # Use the supabase client from the context (passed from handler)
        supabase = context.db
        
        # Load active businesses
        logger.info("Querying businesses...")
        response = supabase.table('businesses').select('*').eq('is_active', True).limit(20).execute()
        businesses = response.data if response.data else []
        logger.info(f"Found {len(businesses)} businesses")
        
        # Enhance with sample menu items
        enhanced_businesses = []
        for business in businesses:
            try:
                menu_response = supabase.table('menu_items').select('*').eq('business_id', business['id']).eq('is_available', True).limit(3).execute()
                menu_items = menu_response.data if menu_response.data else []
                
                enhanced_businesses.append({
                    "id": business['id'],
                    "name": business['name'],
                    "category": business['category'],
                    "description": business['description'],
                    "is_active": business['is_active'],
                    "sample_menu": [
                        {
                            "name": item['name'],
                            "description": item['description'],
                            "price": float(item['base_price'] or 0)
                        } for item in menu_items
                    ]
                })
            except Exception as e:
                logger.error(f"Error processing business {business.get('id')}: {e}")
                continue
        
        context.all_businesses = enhanced_businesses
        context.request_metadata["context_type"] = "business_discovery"
        logger.info(f"Successfully loaded {len(enhanced_businesses)} businesses")
        
    except Exception as e:
        logger.error("Failed to load global context: %s", e)
        logger.exception("Full traceback:")
    
    return context


async def build_dedicated_context(context: RichContext, business_id: int) -> RichContext:
    """Build context for dedicated business chat"""
    try:
        from supabase import create_client
        api_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
        supabase = create_client(settings.SUPABASE_URL, api_key)
        
        # Load business
        business_response = supabase.table('businesses').select('*').eq('id', business_id).execute()
        if business_response.data:
            business = business_response.data[0]
            
            # Load menu
            menu_response = supabase.table('menu_items').select('*').eq('business_id', business_id).eq('is_available', True).execute()
            menu_items = menu_response.data if menu_response.data else []
            
            enhanced_business = {
                "id": business['id'],
                "name": business['name'],
                "category": business['category'],
                "description": business['description'],
                "is_active": business['is_active']
            }
            
            enhanced_menu = [
                {
                    "id": item['id'],
                    "name": item['name'],
                    "description": item['description'],
                    "price": float(item['base_price'] or 0),
                    "category": item.get('category_id'),
                    "available": item['is_available']
                } for item in menu_items
            ]
            
            context.current_business = enhanced_business
            context.business_menu = enhanced_menu
            context.request_metadata["context_type"] = "business_specific"
            
    except Exception as e:
        logger.error("Failed to load dedicated context: %s", e)
    
    return context


async def build_dashboard_context(context: RichContext, business_id: int) -> RichContext:
    """Build comprehensive dashboard context"""
    try:
        dashboard_data = {}
        
        # Load live orders
        from app.models import Order, OrderStatus
        live_orders = context.db.query(Order).filter(
            Order.business_id == business_id,
            Order.status.in_([OrderStatus.PENDING, OrderStatus.PREPARING, OrderStatus.READY])
        ).order_by(Order.created_at.desc()).limit(10).all()
        
        dashboard_data["live_orders"] = [{
            "id": order.id,
            "status": str(order.status),
            "total_amount": float(order.total_amount or 0),
            "customer_name": order.customer_name,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "items_count": len(order.items) if hasattr(order, 'items') else 0
        } for order in live_orders]
        
        # Load inventory data
        from app.models import MenuItem
        inventory_items = context.db.query(MenuItem).filter(MenuItem.business_id == business_id).all()
        
        low_stock_items = []
        for item in inventory_items:
            stock_qty = int(item.stock_quantity or 0)
            min_threshold = int(item.min_stock_threshold or 0)
            if stock_qty <= min_threshold:
                low_stock_items.append({
                    "id": item.id,
                    "name": item.name,
                    "stock_quantity": stock_qty,
                    "min_stock_threshold": min_threshold,
                    "needs_reorder": True
                })
        
        dashboard_data["inventory_status"] = {
            "total_items": len(inventory_items),
            "low_stock_items": low_stock_items,
            "low_stock_count": len(low_stock_items)
        }
        
        # Load categories
        from app.models import MenuCategory
        categories = context.db.query(MenuCategory).filter(MenuCategory.business_id == business_id).all()
        context.business_categories = [{
            "id": cat.id,
            "name": cat.name,
            "description": cat.description
        } for cat in categories]
        
        context.live_orders = dashboard_data.get("live_orders", [])
        context.inventory_status = dashboard_data.get("inventory_status", {})
        context.request_metadata["context_type"] = "dashboard_management"
        
    except Exception as e:
        logger.error("Failed to load dashboard context: %s", e)
    
    return context


async def load_conversation_history(
    context: RichContext,
    session_id: str,
    chat_context: ChatContext,
    business_id: Optional[int] = None
) -> List[Dict]:
    """Load conversation history for a session"""
    try:
        supabase = context.db
        
        # Build query
        query = supabase.table('messages').select('*').eq('session_id', session_id)
        
        # Scope by chat context
        if chat_context == ChatContext.GLOBAL:
            query = query.is_('business_id', None)
        elif chat_context in [ChatContext.DEDICATED, ChatContext.DASHBOARD]:
            if business_id:
                query = query.eq('business_id', business_id)
            else:
                return []
        
        response = query.order('created_at', desc=True).limit(20).execute()
        messages = response.data if response.data else []
        
        history = []
        for msg in reversed(messages):
            history.append({
                "role": "user" if msg['sender_type'] == "customer" else "assistant",
                "content": msg['content'],
                "timestamp": msg['created_at'] if msg['created_at'] else None
            })
        
        return history
        
    except Exception as e:
        logger.error("Failed to load conversation history: %s", e)
        return []
