"""Context builders for different chat contexts"""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.config.settings import settings
from app.config.database import get_supabase_client
from app.core.ai.types import RichContext, ChatContext
from app.core.ai.role_mapper import RoleMapper

logger = logging.getLogger(__name__)


class BusinessContextBuilder:
    """Builder for retrieving and formatting business context"""
    
    def __init__(self):
        """Initialize the business context builder"""
        self.supabase = get_supabase_client()
    
    async def build_business_context(self, business_id: str, include_menu: bool = True) -> Dict[str, Any]:
        """Build context for a specific business"""
        try:
            # Validate business ID format (should be a UUID)
            if not isinstance(business_id, str) or len(business_id) < 10:
                logger.error(f"Invalid business ID format: {business_id}")
                return {"error": "Invalid business ID format"}
            
            # Load business information
            business_response = self.supabase.table('businesses').select('*').eq('id', business_id).execute()
            
            if not hasattr(business_response, 'data') or not business_response.data:
                logger.error(f"Business not found: {business_id}")
                return {"error": "Business not found"}
                
            business = business_response.data[0]
            
            # Build basic business context
            context = {
                "business_id": business_id,
                "business_name": business.get('name', 'Unknown Business'),
                "business_category": business.get('business_category', 'general'),
                "business_description": business.get('description', ''),
                "is_active": business.get('is_active', True),
                "timestamp": datetime.now().isoformat()
            }
            
            # Add email and phone if available
            if 'email' in business:
                context['business_email'] = business['email']
            if 'phone' in business:
                context['business_phone'] = business['phone']
            
            # Add business hours if available
            try:
                hours_response = self.supabase.table('business_hours').select('*').eq('business_id', business_id).execute()
                if hasattr(hours_response, 'data') and hours_response.data:
                    context['business_hours'] = hours_response.data
            except Exception as e:
                logger.warning(f"Failed to load business hours: {e}")
            
            # Add menu items if requested
            if include_menu:
                try:
                    menu_response = self.supabase.table('menu_items').select('*').eq('business_id', business_id).eq('is_available', True).limit(10).execute()
                    
                    if hasattr(menu_response, 'data') and menu_response.data:
                        menu_items = [
                            {
                                "name": item.get('name', ''),
                                "description": item.get('description', ''),
                                "price": float(item.get('price', 0)),
                                "category": item.get('category', '')
                            }
                            for item in menu_response.data
                        ]
                        context['menu_items'] = menu_items
                        context['menu_count'] = len(menu_items)
                except Exception as e:
                    logger.warning(f"Failed to load menu items: {e}")
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to build business context: {e}")
            return {"error": str(e)}
    
    async def build_voice_business_context(self, business_id: str) -> Dict[str, Any]:
        """Build voice-optimized context for a specific business"""
        try:
            # Get base business context
            context = await self.build_business_context(business_id)
            
            # Add voice-specific fields
            context['channel'] = 'voice'
            context['requires_voice_optimization'] = True
            context['speech_optimized'] = True
            
            # Add standard greeting
            business_name = context.get('business_name', 'our business')
            context['greeting'] = f"Thank you for calling {business_name}. How may I assist you today?"
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to build voice business context: {e}")
            return {"error": str(e), "channel": "voice"}


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
                            "price": float(item.get('price') or 0)
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
            query = query.is_('business_id', 'null')
        elif chat_context in [ChatContext.DEDICATED, ChatContext.DASHBOARD]:
            if business_id:
                query = query.eq('business_id', business_id)
            else:
                return []
        
        response = query.order('created_at', desc=True).limit(20).execute()
        messages = response.data if response.data else []
        
        history = []
        for msg in reversed(messages):
            # Use dynamic role mapping for flexible sender type handling
            role = RoleMapper.get_chat_role(msg.get('sender_type', 'customer'))
            history.append({
                "role": role,
                "content": msg['content'],
                "timestamp": msg['created_at'] if msg['created_at'] else None,
                "sender_type": msg.get('sender_type', 'unknown')  # Include original type for debugging
            })
        
        return history
        
    except Exception as e:
        logger.error("Failed to load conversation history: %s", e)
        return []
