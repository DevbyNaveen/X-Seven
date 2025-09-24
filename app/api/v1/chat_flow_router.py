"""
Chat Flow Router - Intelligent Routing for Three Chat Types
Implements Dedicated, Dashboard, and Global chat flows with modern architecture
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Literal
from dataclasses import dataclass
from enum import Enum
import logging

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.api.v1.crewai_langgraph_integration import CrewAILangGraphIntegrator
from app.api.v1.redis_persistence import RedisPersistenceManager
from app.config.database import get_supabase_client

logger = logging.getLogger(__name__)


class ChatFlowType(Enum):
    """Three types of chat flows"""
    DEDICATED = "dedicated"      # Business-specific conversations
    DASHBOARD = "dashboard"      # Business management interface
    GLOBAL = "global"           # Multi-business assessment & comparison


@dataclass
class ChatFlowContext:
    """Context for chat flow routing"""
    flow_type: ChatFlowType
    business_id: Optional[str] = None
    user_id: Optional[str] = None
    user_role: Optional[str] = None
    permissions: List[str] = None
    business_category: Optional[str] = None
    location_context: Optional[Dict[str, Any]] = None
    search_criteria: Optional[Dict[str, Any]] = None


class ChatFlowRouter:
    """Intelligent router for the three chat flow types"""
    
    def __init__(self):
        self.integrator = CrewAILangGraphIntegrator()
        self.redis_manager = RedisPersistenceManager()
        self.supabase = get_supabase_client()
        
        # Flow handlers
        self.flow_handlers = {
            ChatFlowType.DEDICATED: DedicatedChatHandler(self.integrator, self.redis_manager, self.supabase),
            ChatFlowType.DASHBOARD: DashboardChatHandler(self.integrator, self.redis_manager, self.supabase),
            ChatFlowType.GLOBAL: GlobalChatHandler(self.integrator, self.redis_manager, self.supabase)
        }
        
        logger.info("✅ Chat Flow Router initialized with all three flow types")
    
    async def route_chat_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Route chat request to appropriate flow handler"""
        try:
            # Determine flow type from request
            flow_context = await self._determine_flow_type(request)
            
            # Get appropriate handler
            handler = self.flow_handlers[flow_context.flow_type]
            
            # Process request with handler
            response = await handler.handle_chat_request(request, flow_context)
            
            # Add routing metadata
            response["flow_type"] = flow_context.flow_type.value
            response["routing_metadata"] = {
                "handler_used": handler.__class__.__name__,
                "business_id": flow_context.business_id,
                "user_role": flow_context.user_role,
                "routed_at": datetime.now().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Chat routing error: {e}")
            raise HTTPException(status_code=500, detail=f"Chat routing failed: {str(e)}")
    
    async def _determine_flow_type(self, request: Dict[str, Any]) -> ChatFlowContext:
        """Determine which chat flow type to use"""
        
        # Check for explicit flow type in request
        if "flow_type" in request:
            flow_type = ChatFlowType(request["flow_type"])
        else:
            # Intelligent detection based on request context
            flow_type = await self._detect_flow_type(request)
        
        # Build context
        context = ChatFlowContext(
            flow_type=flow_type,
            business_id=request.get("business_id"),
            user_id=request.get("user_id"),
            user_role=request.get("user_role"),
            permissions=request.get("permissions", []),
            business_category=request.get("business_category"),
            location_context=request.get("location_context"),
            search_criteria=request.get("search_criteria")
        )
        
        return context
    
    async def _detect_flow_type(self, request: Dict[str, Any]) -> ChatFlowType:
        """Intelligently detect flow type from request context"""
        
        # Dashboard indicators
        if any(keyword in request.get("message", "").lower() for keyword in [
            "dashboard", "manage", "admin", "analytics", "settings", "configure",
            "update menu", "staff", "business hours", "pricing"
        ]):
            return ChatFlowType.DASHBOARD
        
        # Dedicated chat indicators
        if request.get("business_id") and not request.get("compare_businesses"):
            return ChatFlowType.DEDICATED
        
        # Global chat indicators (default for comparison and discovery)
        if any(keyword in request.get("message", "").lower() for keyword in [
            "compare", "find", "best", "recommend", "search", "nearby", "options"
        ]):
            return ChatFlowType.GLOBAL
        
        # Default based on context
        if request.get("business_id") and request.get("user_role") in ["owner", "manager", "admin"]:
            return ChatFlowType.DASHBOARD
        elif request.get("business_id"):
            return ChatFlowType.DEDICATED
        else:
            return ChatFlowType.GLOBAL


class BaseChatHandler:
    """Base class for chat flow handlers"""
    
    def __init__(self, integrator: CrewAILangGraphIntegrator, 
                 redis_manager: RedisPersistenceManager, supabase):
        self.integrator = integrator
        self.redis_manager = redis_manager
        self.supabase = supabase
    
    async def handle_chat_request(self, request: Dict[str, Any], 
                                context: ChatFlowContext) -> Dict[str, Any]:
        """Handle chat request - to be implemented by subclasses"""
        raise NotImplementedError


class DedicatedChatHandler(BaseChatHandler):
    """Handler for dedicated business-specific conversations"""
    
    async def handle_chat_request(self, request: Dict[str, Any], 
                                context: ChatFlowContext) -> Dict[str, Any]:
        """Handle dedicated business chat"""
        logger.info(f"Processing dedicated chat for business {context.business_id}")
        
        try:
            # Validate business context
            if not context.business_id:
                raise ValueError("Business ID required for dedicated chat")
            
            # Get or create conversation
            conversation_id = await self._get_or_create_conversation(request, context)
            
            # Enhance context with business-specific data
            enhanced_context = await self._enhance_business_context(context)
            
            # Process message with business-specific agent
            response = await self.integrator.process_message_with_agent(
                conversation_id=conversation_id,
                message=request["message"],
                user_id=context.user_id
            )
            
            # Add dedicated chat specific features
            response.update({
                "chat_type": "dedicated",
                "business_info": enhanced_context.get("business_info", {}),
                "available_services": enhanced_context.get("services", []),
                "booking_available": enhanced_context.get("booking_enabled", False),
                "business_hours": enhanced_context.get("hours", {}),
                "contact_info": enhanced_context.get("contact", {})
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Dedicated chat error: {e}")
            return {
                "response": "I'm having trouble accessing business information. Please try again.",
                "error": str(e),
                "chat_type": "dedicated",
                "conversation_id": request.get("conversation_id")
            }
    
    async def _get_or_create_conversation(self, request: Dict[str, Any], 
                                        context: ChatFlowContext) -> str:
        """Get existing or create new dedicated conversation"""
        conversation_id = request.get("conversation_id")
        
        if conversation_id:
            # Validate existing conversation
            existing_context = await self.integrator.get_conversation_context(conversation_id)
            if existing_context:
                return conversation_id
        
        # Create new dedicated conversation
        return await self.integrator.create_enhanced_conversation(
            conversation_type="dedicated",
            initial_context={
                "business_id": context.business_id,
                "business_category": context.business_category,
                "dedicated_mode": True
            },
            user_id=context.user_id,
            business_id=context.business_id
        )
    
    async def _enhance_business_context(self, context: ChatFlowContext) -> Dict[str, Any]:
        """Enhance context with business-specific data"""
        try:
            # Get business data from database
            business_response = self.supabase.table("businesses").select("*").eq("id", context.business_id).execute()
            
            if business_response.data:
                business = business_response.data[0]
                
                return {
                    "business_info": {
                        "name": business.get("name"),
                        "category": business.get("category"),
                        "description": business.get("description"),
                        "rating": business.get("rating", 0),
                        "price_range": business.get("price_range")
                    },
                    "services": business.get("services", []),
                    "hours": business.get("hours", {}),
                    "contact": {
                        "phone": business.get("phone"),
                        "email": business.get("email"),
                        "address": business.get("address")
                    },
                    "booking_enabled": business.get("booking_enabled", False),
                    "features": business.get("features", [])
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error enhancing business context: {e}")
            return {}


class DashboardChatHandler(BaseChatHandler):
    """Handler for business management dashboard conversations"""
    
    async def handle_chat_request(self, request: Dict[str, Any], 
                                context: ChatFlowContext) -> Dict[str, Any]:
        """Handle dashboard management chat"""
        logger.info(f"Processing dashboard chat for business {context.business_id}")
        
        try:
            # Validate permissions
            if not await self._validate_dashboard_permissions(context):
                raise ValueError("Insufficient permissions for dashboard access")
            
            # Get or create dashboard conversation
            conversation_id = await self._get_or_create_dashboard_conversation(request, context)
            
            # Enhance context with management data
            management_context = await self._enhance_management_context(context)
            
            # Process with dashboard-specific capabilities
            response = await self.integrator.process_message_with_agent(
                conversation_id=conversation_id,
                message=request["message"],
                user_id=context.user_id
            )
            
            # Add dashboard-specific features
            response.update({
                "chat_type": "dashboard",
                "management_capabilities": management_context.get("capabilities", []),
                "business_analytics": await self._get_business_analytics(context.business_id),
                "pending_actions": management_context.get("pending_actions", []),
                "quick_actions": self._get_quick_actions(context),
                "dashboard_widgets": await self._get_dashboard_widgets(context.business_id)
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Dashboard chat error: {e}")
            return {
                "response": "I'm having trouble accessing dashboard features. Please check your permissions.",
                "error": str(e),
                "chat_type": "dashboard",
                "conversation_id": request.get("conversation_id")
            }
    
    async def _validate_dashboard_permissions(self, context: ChatFlowContext) -> bool:
        """Validate user has dashboard access permissions"""
        # Check user role
        if context.user_role in ["owner", "manager", "admin"]:
            return True
        
        # Check specific permissions
        required_permissions = ["dashboard_access", "business_management"]
        return any(perm in context.permissions for perm in required_permissions)
    
    async def _get_or_create_dashboard_conversation(self, request: Dict[str, Any], 
                                                  context: ChatFlowContext) -> str:
        """Get or create dashboard conversation"""
        conversation_id = request.get("conversation_id")
        
        if conversation_id:
            existing_context = await self.integrator.get_conversation_context(conversation_id)
            if existing_context and existing_context.get("conversation_type") == "dashboard":
                return conversation_id
        
        # Create new dashboard conversation
        return await self.integrator.create_enhanced_conversation(
            conversation_type="dashboard",
            initial_context={
                "business_id": context.business_id,
                "user_role": context.user_role,
                "permissions": context.permissions,
                "dashboard_mode": True,
                "management_features": True
            },
            user_id=context.user_id,
            business_id=context.business_id
        )
    
    async def _enhance_management_context(self, context: ChatFlowContext) -> Dict[str, Any]:
        """Enhance context with management capabilities"""
        capabilities = []
        
        # Role-based capabilities
        if context.user_role == "owner":
            capabilities.extend([
                "full_business_management", "financial_reports", "staff_management",
                "business_settings", "analytics_access", "marketing_tools"
            ])
        elif context.user_role == "manager":
            capabilities.extend([
                "operational_management", "staff_scheduling", "customer_management",
                "inventory_management", "basic_analytics"
            ])
        elif context.user_role == "admin":
            capabilities.extend([
                "system_administration", "user_management", "configuration",
                "technical_support", "advanced_analytics"
            ])
        
        return {
            "capabilities": capabilities,
            "pending_actions": await self._get_pending_actions(context.business_id),
            "recent_activity": await self._get_recent_activity(context.business_id)
        }
    
    async def _get_business_analytics(self, business_id: str) -> Dict[str, Any]:
        """Get business analytics data"""
        # This would fetch real analytics from database
        return {
            "daily_visitors": 45,
            "weekly_bookings": 23,
            "customer_satisfaction": 4.7,
            "revenue_trend": "increasing",
            "popular_services": ["haircut", "styling", "color"]
        }
    
    async def _get_pending_actions(self, business_id: str) -> List[Dict[str, Any]]:
        """Get pending management actions"""
        return [
            {"action": "approve_staff_schedule", "priority": "high", "due": "today"},
            {"action": "review_customer_feedback", "priority": "medium", "due": "this_week"},
            {"action": "update_menu_prices", "priority": "low", "due": "next_week"}
        ]
    
    async def _get_recent_activity(self, business_id: str) -> List[Dict[str, Any]]:
        """Get recent business activity"""
        return [
            {"activity": "New booking received", "time": "10 minutes ago"},
            {"activity": "Staff member checked in", "time": "1 hour ago"},
            {"activity": "Customer review posted", "time": "2 hours ago"}
        ]
    
    def _get_quick_actions(self, context: ChatFlowContext) -> List[Dict[str, Any]]:
        """Get available quick actions"""
        return [
            {"action": "view_todays_bookings", "label": "Today's Bookings", "icon": "calendar"},
            {"action": "check_staff_status", "label": "Staff Status", "icon": "users"},
            {"action": "view_recent_reviews", "label": "Recent Reviews", "icon": "star"},
            {"action": "update_business_hours", "label": "Update Hours", "icon": "clock"}
        ]
    
    async def _get_dashboard_widgets(self, business_id: str) -> List[Dict[str, Any]]:
        """Get dashboard widgets data"""
        return [
            {
                "widget": "revenue_chart",
                "title": "Revenue Trend",
                "data": {"current_month": 5420, "last_month": 4890, "trend": "up"}
            },
            {
                "widget": "booking_status",
                "title": "Today's Bookings",
                "data": {"total": 12, "confirmed": 10, "pending": 2}
            },
            {
                "widget": "customer_satisfaction",
                "title": "Customer Satisfaction",
                "data": {"rating": 4.7, "reviews_count": 89, "trend": "stable"}
            }
        ]


class GlobalChatHandler(BaseChatHandler):
    """Handler for global multi-business assessment and comparison"""
    
    async def handle_chat_request(self, request: Dict[str, Any], 
                                context: ChatFlowContext) -> Dict[str, Any]:
        """Handle global assessment chat"""
        logger.info("Processing global chat for multi-business assessment")
        
        try:
            # Get or create global conversation
            conversation_id = await self._get_or_create_global_conversation(request, context)
            
            # Enhance context with global data
            global_context = await self._enhance_global_context(context, request)
            
            # Process with multi-business capabilities
            response = await self.integrator.process_message_with_agent(
                conversation_id=conversation_id,
                message=request["message"],
                user_id=context.user_id
            )
            
            # Add global chat specific features
            response.update({
                "chat_type": "global",
                "businesses_found": len(global_context.get("businesses", [])),
                "comparison_results": global_context.get("comparison_results", []),
                "search_filters": global_context.get("active_filters", {}),
                "recommendations": await self._generate_recommendations(global_context),
                "map_data": global_context.get("map_data", {}),
                "price_comparison": global_context.get("price_comparison", {})
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Global chat error: {e}")
            return {
                "response": "I'm having trouble searching businesses. Please try again.",
                "error": str(e),
                "chat_type": "global",
                "conversation_id": request.get("conversation_id")
            }
    
    async def _get_or_create_global_conversation(self, request: Dict[str, Any], 
                                               context: ChatFlowContext) -> str:
        """Get or create global conversation"""
        conversation_id = request.get("conversation_id")
        
        if conversation_id:
            existing_context = await self.integrator.get_conversation_context(conversation_id)
            if existing_context and existing_context.get("conversation_type") == "global":
                return conversation_id
        
        # Create new global conversation
        return await self.integrator.create_enhanced_conversation(
            conversation_type="global",
            initial_context={
                "global_mode": True,
                "comparison_enabled": True,
                "multi_business_search": True,
                "search_criteria": context.search_criteria or {},
                "location_context": context.location_context or {}
            },
            user_id=context.user_id
        )
    
    async def _enhance_global_context(self, context: ChatFlowContext, 
                                    request: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance context with global business data"""
        try:
            # Extract search criteria from message
            search_criteria = await self._extract_search_criteria(request["message"])
            
            # Search businesses based on criteria
            businesses = await self._search_businesses(search_criteria)
            
            # Perform comparisons if multiple businesses found
            comparison_results = []
            if len(businesses) > 1:
                comparison_results = await self._compare_businesses(businesses, search_criteria)
            
            return {
                "businesses": businesses,
                "search_criteria": search_criteria,
                "comparison_results": comparison_results,
                "active_filters": search_criteria,
                "map_data": await self._generate_map_data(businesses),
                "price_comparison": await self._generate_price_comparison(businesses)
            }
            
        except Exception as e:
            logger.error(f"Error enhancing global context: {e}")
            return {"businesses": [], "error": str(e)}
    
    async def _extract_search_criteria(self, message: str) -> Dict[str, Any]:
        """Extract search criteria from user message"""
        criteria = {
            "category": None,
            "location": None,
            "price_range": None,
            "rating_min": None,
            "features": [],
            "distance_km": 10
        }
        
        message_lower = message.lower()
        
        # Category detection
        if any(word in message_lower for word in ["restaurant", "food", "dining"]):
            criteria["category"] = "food_hospitality"
        elif any(word in message_lower for word in ["beauty", "salon", "hair", "spa"]):
            criteria["category"] = "beauty_personal_care"
        elif any(word in message_lower for word in ["car", "auto", "mechanic"]):
            criteria["category"] = "automotive_services"
        
        # Price range detection
        if any(word in message_lower for word in ["cheap", "budget", "affordable"]):
            criteria["price_range"] = "$"
        elif any(word in message_lower for word in ["expensive", "luxury", "premium"]):
            criteria["price_range"] = "$$$"
        elif any(word in message_lower for word in ["mid-range", "moderate"]):
            criteria["price_range"] = "$$"
        
        # Rating detection
        if "highly rated" in message_lower or "best" in message_lower:
            criteria["rating_min"] = 4.0
        elif "good" in message_lower:
            criteria["rating_min"] = 3.5
        
        return criteria
    
    async def _search_businesses(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search businesses based on criteria"""
        try:
            query = self.supabase.table("businesses").select("*")
            
            # Apply filters
            if criteria.get("category"):
                query = query.eq("category", criteria["category"])
            
            if criteria.get("rating_min"):
                query = query.gte("rating", criteria["rating_min"])
            
            if criteria.get("price_range"):
                query = query.eq("price_range", criteria["price_range"])
            
            # Execute query
            response = query.limit(20).execute()
            
            return response.data or []
            
        except Exception as e:
            logger.error(f"Error searching businesses: {e}")
            return []
    
    async def _compare_businesses(self, businesses: List[Dict[str, Any]], 
                                criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Compare businesses and generate comparison results"""
        comparisons = []
        
        for business in businesses[:5]:  # Compare top 5
            score = 0
            highlights = []
            
            # Rating score
            rating = business.get("rating", 0)
            score += rating * 20  # Max 100 points for 5-star rating
            
            if rating >= 4.5:
                highlights.append("Excellent rating")
            elif rating >= 4.0:
                highlights.append("Great rating")
            
            # Price score (inverse for budget-conscious)
            price_range = business.get("price_range", "$$")
            if criteria.get("price_range") == "$" and price_range == "$":
                score += 20
                highlights.append("Budget-friendly")
            elif criteria.get("price_range") == "$$$" and price_range == "$$$":
                score += 20
                highlights.append("Premium service")
            
            # Features score
            features = business.get("features", [])
            if "parking" in features:
                score += 5
                highlights.append("Parking available")
            if "wifi" in features:
                score += 5
                highlights.append("Free WiFi")
            
            comparisons.append({
                "business_id": business["id"],
                "name": business["name"],
                "score": min(score, 100),  # Cap at 100
                "highlights": highlights,
                "rating": rating,
                "price_range": price_range,
                "category": business.get("category"),
                "address": business.get("address")
            })
        
        # Sort by score
        comparisons.sort(key=lambda x: x["score"], reverse=True)
        
        return comparisons
    
    async def _generate_recommendations(self, global_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate personalized recommendations"""
        businesses = global_context.get("businesses", [])
        comparison_results = global_context.get("comparison_results", [])
        
        recommendations = []
        
        if comparison_results:
            # Top recommendation
            top_business = comparison_results[0]
            recommendations.append({
                "type": "top_choice",
                "business_id": top_business["business_id"],
                "title": f"Top Choice: {top_business['name']}",
                "reason": f"Highest score ({top_business['score']}/100) with {', '.join(top_business['highlights'][:2])}"
            })
            
            # Budget recommendation
            budget_options = [b for b in comparison_results if b.get("price_range") == "$"]
            if budget_options:
                budget_choice = budget_options[0]
                recommendations.append({
                    "type": "budget_friendly",
                    "business_id": budget_choice["business_id"],
                    "title": f"Budget Option: {budget_choice['name']}",
                    "reason": "Great value for money with good ratings"
                })
            
            # Premium recommendation
            premium_options = [b for b in comparison_results if b.get("price_range") == "$$$"]
            if premium_options:
                premium_choice = premium_options[0]
                recommendations.append({
                    "type": "premium_choice",
                    "business_id": premium_choice["business_id"],
                    "title": f"Premium Option: {premium_choice['name']}",
                    "reason": "Luxury experience with top-tier service"
                })
        
        return recommendations
    
    async def _generate_map_data(self, businesses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate map data for businesses"""
        markers = []
        
        for business in businesses:
            if business.get("latitude") and business.get("longitude"):
                markers.append({
                    "id": business["id"],
                    "name": business["name"],
                    "lat": business["latitude"],
                    "lng": business["longitude"],
                    "rating": business.get("rating", 0),
                    "price_range": business.get("price_range", "$$"),
                    "category": business.get("category")
                })
        
        return {
            "markers": markers,
            "center": self._calculate_map_center(markers),
            "zoom_level": 12
        }
    
    def _calculate_map_center(self, markers: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate center point for map"""
        if not markers:
            return {"lat": 0, "lng": 0}
        
        avg_lat = sum(marker["lat"] for marker in markers) / len(markers)
        avg_lng = sum(marker["lng"] for marker in markers) / len(markers)
        
        return {"lat": avg_lat, "lng": avg_lng}
    
    async def _generate_price_comparison(self, businesses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate price comparison data"""
        price_ranges = {}
        
        for business in businesses:
            price_range = business.get("price_range", "$$")
            if price_range not in price_ranges:
                price_ranges[price_range] = []
            
            price_ranges[price_range].append({
                "name": business["name"],
                "rating": business.get("rating", 0),
                "category": business.get("category")
            })
        
        return {
            "price_ranges": price_ranges,
            "average_ratings_by_price": {
                range_key: sum(b["rating"] for b in businesses) / len(businesses)
                for range_key, businesses in price_ranges.items()
                if businesses
            }
        }


# Global router instance
_chat_flow_router = None

def get_chat_flow_router() -> ChatFlowRouter:
    """Get global chat flow router instance"""
    global _chat_flow_router
    if _chat_flow_router is None:
        _chat_flow_router = ChatFlowRouter()
    return _chat_flow_router
